#!/usr/bin/env python3
"""
Skill 质量检测工具 - 自动扫描并评估 skills 质量
只使用 Python 标准库，无第三方依赖
"""

import os
import sys
import re
import json
import argparse
import stat
from datetime import datetime
from pathlib import Path


# ============================================================
# 常量定义
# ============================================================

# 执行类任务关键词
EXEC_KEYWORDS = [
    '自动化', '脚本', '执行', '运行', '部署', '扫描', '生成', '创建',
    'API', '浏览器', 'automat', 'script', 'execute', 'run', 'deploy',
    'scan', 'generate', 'create', 'upload', 'download', 'install',
    'fetch', 'post', 'send', 'convert', 'extract', 'build', 'compile',
]

# 泛化词（扣分）
VAGUE_WORDS = [
    '所有', '任何', '任意', '一切', 'everything', 'anything', 'all kinds',
    'any kind', 'whatever', '全部',
]

# 容错关键词（Prompt 型）
FALLBACK_KEYWORDS = [
    '如果失败', 'fallback', '降级', '备选', '出错时', '错误处理',
    '异常', 'if fail', 'error handling', 'retry', '重试', '回退',
]

# 评级映射
def get_rating(score):
    """根据分数返回星级评级"""
    if score >= 90:
        return '⭐⭐⭐⭐⭐'
    elif score >= 75:
        return '⭐⭐⭐⭐'
    elif score >= 60:
        return '⭐⭐⭐'
    elif score >= 40:
        return '⭐⭐'
    else:
        return '⭐'


# ============================================================
# 解析工具
# ============================================================

def parse_yaml_frontmatter(content):
    """从 SKILL.md 中提取 YAML frontmatter"""
    if not content.startswith('---'):
        return None, content
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None, content
    yaml_text = parts[1].strip()
    body = parts[2].strip()
    # 简单解析 YAML（不引入 PyYAML）
    meta = {}
    current_key = None
    current_val_lines = []
    for line in yaml_text.split('\n'):
        # 多行值（以 > 或 | 开头的续行）
        if current_key and (line.startswith('  ') or line.startswith('\t')):
            current_val_lines.append(line.strip())
            continue
        # 保存上一个 key
        if current_key:
            meta[current_key] = ' '.join(current_val_lines).strip()
            current_key = None
            current_val_lines = []
        m = re.match(r'^(\w[\w-]*):\s*(.*)', line)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val in ('>', '|', '>-', '|-'):
                current_key = key
                current_val_lines = []
            else:
                meta[key] = val
    if current_key:
        meta[current_key] = ' '.join(current_val_lines).strip()
    return meta, body


def is_exec_task(description):
    """判断 description 描述的是否为执行类任务"""
    desc_lower = description.lower()
    count = sum(1 for kw in EXEC_KEYWORDS if kw.lower() in desc_lower)
    return count >= 2  # 至少命中2个执行类关键词


def count_pattern(content, pattern):
    """统计正则匹配次数"""
    return len(re.findall(pattern, content, re.IGNORECASE))


# ============================================================
# 五维评分函数
# ============================================================

def score_matching(skill_dir, meta, body, has_scripts):
    """维度1：问题-方案匹配度（20分）"""
    desc = meta.get('description', '')
    reasons = []
    needs_exec = is_exec_task(desc)

    if has_scripts and needs_exec:
        score = 19
        reasons.append('执行类任务且有 scripts/，方案匹配')
    elif not has_scripts and not needs_exec:
        score = 19
        reasons.append('指导类任务且纯 Prompt，方案匹配')
    elif has_scripts and not needs_exec:
        score = 14
        reasons.append('有 scripts/ 但任务偏指导类，略过度工程化')
    else:
        score = 8
        reasons.append('执行类任务但缺少 scripts/，方案不匹配')

    return min(score, 20), '; '.join(reasons)


def score_completeness(skill_dir, meta, body, has_scripts):
    """维度2：完成度（20分）"""
    score = 0
    reasons = []

    # SKILL.md 存在且有 YAML 头
    if meta is not None:
        score += 5
        reasons.append('YAML frontmatter 完整')
    else:
        reasons.append('缺少 YAML frontmatter')

    # 脚本文件检查
    scripts_dir = os.path.join(skill_dir, 'scripts')
    if has_scripts:
        script_files = _list_files(scripts_dir)
        non_empty = [f for f in script_files if os.path.getsize(f) > 10]
        if non_empty:
            score += 5
            reasons.append(f'{len(non_empty)} 个非空脚本文件')
        else:
            reasons.append('scripts/ 下文件为空或过小')

        # shebang 和可执行权限
        shebang_ok = 0
        exec_ok = 0
        for f in non_empty:
            try:
                with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                    first_line = fh.readline()
                if first_line.startswith('#!'):
                    shebang_ok += 1
                fstat = os.stat(f)
                if fstat.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                    exec_ok += 1
            except OSError:
                pass
        if non_empty:
            ratio = (shebang_ok + exec_ok) / (len(non_empty) * 2)
            sub = int(5 * ratio)
            score += sub
            if sub >= 4:
                reasons.append('脚本有 shebang 和可执行权限')
            elif sub >= 2:
                reasons.append('部分脚本缺少 shebang 或可执行权限')
            else:
                reasons.append('脚本缺少 shebang 和可执行权限')
    else:
        # 纯 Prompt 型，脚本项给基础分
        score += 5
        reasons.append('纯 Prompt 型，无需脚本')

    # 辅助文件
    refs_dir = os.path.join(skill_dir, 'references')
    if os.path.isdir(refs_dir) and _list_files(refs_dir):
        score += 3
        reasons.append('有 references/ 辅助文件')
    # 也检查其他常见辅助目录
    for d in ['templates', 'examples', 'assets', 'config']:
        if os.path.isdir(os.path.join(skill_dir, d)):
            score += 1
            reasons.append(f'有 {d}/ 目录')
            break

    # 未完成标记检查（只检测真正标记，排除引用和字符串）
    todo_count = 0
    for f in _list_all_text_files(skill_dir):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                for line in fh:
                    stripped = line.strip()
                    # 跳过引号包裹的（字符串/文档引用）
                    if re.search(r'["\'].*\b(TODO|FIXME)\b.*["\']', stripped):
                        continue
                    # 跳过表格行中的引用
                    if stripped.startswith('|') and stripped.endswith('|'):
                        continue
                    # 检查真正的 TODO/FIXME 标记（行首注释或独立标记）
                    if re.search(r'#\s*(TODO|FIXME|HACK|XXX)\b', stripped, re.IGNORECASE):
                        todo_count += 1
                    elif re.match(r'^(TODO|FIXME|HACK|XXX)\b', stripped, re.IGNORECASE):
                        todo_count += 1
        except OSError:
            pass
    if todo_count > 0:
        deduct = min(todo_count * 2, 5)
        score -= deduct
        reasons.append(f'发现 {todo_count} 个未完成标记（扣{deduct}分）')

    return max(0, min(score, 20)), '; '.join(reasons)


def score_error_handling(skill_dir, meta, body, has_scripts):
    """维度3：容错性（20分）"""
    if not has_scripts:
        # 纯 Prompt 型：检查容错指导
        full_text = (body or '') + ' ' + (meta.get('description', '') if meta else '')
        skill_md_path = os.path.join(skill_dir, 'SKILL.md')
        try:
            with open(skill_md_path, 'r', encoding='utf-8', errors='ignore') as f:
                full_text += f.read()
        except OSError:
            pass
        hits = sum(1 for kw in FALLBACK_KEYWORDS if kw.lower() in full_text.lower())
        if hits >= 3:
            return 16, f'Prompt 中有 {hits} 处容错指导'
        elif hits >= 1:
            return 12, f'Prompt 中有 {hits} 处容错指导，建议增加'
        else:
            return 6, '纯 Prompt 且无容错指导'

    # 有脚本：分析错误处理
    scripts_dir = os.path.join(skill_dir, 'scripts')
    total_funcs = 0
    total_try = 0
    total_lines = 0
    shell_checks = 0
    reasons = []

    for f in _list_files(scripts_dir):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except OSError:
            continue

        lines = content.split('\n')
        total_lines += len(lines)

        if f.endswith('.py'):
            total_funcs += count_pattern(content, r'^\s*def\s+')
            total_try += count_pattern(content, r'^\s*try\s*:')
            # ImportError 处理加分
            if 'ImportError' in content:
                total_try += 1
        elif f.endswith('.sh') or f.endswith('.bash'):
            if 'set -e' in content:
                shell_checks += 3
            shell_checks += count_pattern(content, r'\|\|\s')
            shell_checks += count_pattern(content, r'if\s+\[')
            total_funcs += max(count_pattern(content, r'^\s*\w+\s*\(\)\s*\{'), 1)
            total_try += shell_checks

    denominator = max(total_funcs, 1)
    coverage = total_try / denominator
    if coverage > 0.7:
        score = 16 + min(int(coverage * 4), 4)
        reasons.append(f'错误处理覆盖率 {coverage:.0%}')
    elif coverage > 0.3:
        score = 10 + int((coverage - 0.3) / 0.4 * 5)
        reasons.append(f'错误处理覆盖率 {coverage:.0%}，建议增加')
    elif coverage > 0:
        score = 5 + int(coverage / 0.3 * 5)
        reasons.append(f'错误处理覆盖率低 {coverage:.0%}')
    else:
        score = 3
        reasons.append('未发现错误处理代码')

    return min(score, 20), '; '.join(reasons)


def score_description(skill_dir, meta, body, has_scripts):
    """维度4：Description 精度（20分）"""
    score = 0
    reasons = []

    desc = meta.get('description', '') if meta else ''
    if not desc:
        return 2, '缺少 description 字段'

    score += 5
    reasons.append('description 存在')

    # 长度检查
    desc_len = len(desc)
    if 50 <= desc_len <= 300:
        score += 5
        reasons.append(f'长度 {desc_len} 字符，适中')
    elif 30 <= desc_len < 50:
        score += 3
        reasons.append(f'长度 {desc_len} 字符，偏短')
    elif 300 < desc_len <= 500:
        score += 3
        reasons.append(f'长度 {desc_len} 字符，偏长')
    elif desc_len < 30:
        score += 1
        reasons.append(f'长度仅 {desc_len} 字符，太短')
    else:
        score += 1
        reasons.append(f'长度 {desc_len} 字符，太长')

    # 中文触发词
    if re.search(r'[\u4e00-\u9fff]{2,}', desc):
        score += 5
        reasons.append('包含中文关键词')
    else:
        reasons.append('缺少中文触发词')

    # 英文触发词
    if re.search(r'[a-zA-Z]{3,}', desc):
        score += 5
        reasons.append('包含英文关键词')
    else:
        reasons.append('缺少英文触发词')

    # 泛化词扣分
    vague_hits = [w for w in VAGUE_WORDS if w.lower() in desc.lower()]
    if vague_hits:
        deduct = min(len(vague_hits) * 2, 5)
        score -= deduct
        reasons.append(f'包含泛化词 {vague_hits}（扣{deduct}分）')

    return max(0, min(score, 20)), '; '.join(reasons)


def score_token_efficiency(skill_dir, meta, body, has_scripts):
    """维度5：Token 效率（20分）"""
    reasons = []
    skill_md = os.path.join(skill_dir, 'SKILL.md')

    try:
        size = os.path.getsize(skill_md)
    except OSError:
        return 0, 'SKILL.md 不存在'

    size_kb = size / 1024
    if size_kb < 2:
        score = 20
        reasons.append(f'SKILL.md {size}B（<2KB，极佳）')
    elif size_kb < 5:
        score = 15 + int((5 - size_kb) / 3 * 4)
        reasons.append(f'SKILL.md {size_kb:.1f}KB（2-5KB，良好）')
    elif size_kb < 8:
        score = 10 + int((8 - size_kb) / 3 * 4)
        reasons.append(f'SKILL.md {size_kb:.1f}KB（5-8KB，一般）')
    elif size_kb < 15:
        score = 5 + int((15 - size_kb) / 7 * 4)
        reasons.append(f'SKILL.md {size_kb:.1f}KB（8-15KB，偏大）')
    else:
        score = max(0, int(4 - (size_kb - 15) / 10))
        reasons.append(f'SKILL.md {size_kb:.1f}KB（>15KB，过大）')

    # 渐进式披露加分
    has_external = False
    for d in ['references', 'templates', 'examples', 'docs']:
        if os.path.isdir(os.path.join(skill_dir, d)):
            has_external = True
            break
    if has_external:
        score = min(score + 3, 20)
        reasons.append('有外部参考文件（渐进式披露）')

    # 重复内容检查（简单：检查连续相似行）
    try:
        with open(skill_md, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        seen = set()
        dup_count = 0
        for line in lines:
            stripped = line.strip()
            if len(stripped) > 30:
                if stripped in seen:
                    dup_count += 1
                seen.add(stripped)
        if dup_count >= 3:
            score = max(score - 3, 0)
            reasons.append(f'发现 {dup_count} 行重复内容')
    except OSError:
        pass

    return min(score, 20), '; '.join(reasons)


# ============================================================
# 文件工具
# ============================================================

def _list_files(directory):
    """列出目录下所有文件（递归）"""
    result = []
    try:
        for root, dirs, files in os.walk(directory):
            for f in files:
                result.append(os.path.join(root, f))
    except OSError:
        pass
    return result


def _list_all_text_files(skill_dir):
    """列出 skill 目录下所有文本文件"""
    text_exts = {'.py', '.sh', '.bash', '.md', '.txt', '.json', '.yaml', '.yml', '.toml'}
    result = []
    for f in _list_files(skill_dir):
        if any(f.endswith(ext) for ext in text_exts):
            result.append(f)
    return result


# ============================================================
# 核心评估
# ============================================================

def evaluate_skill(skill_dir):
    """评估单个 skill，返回评分结果字典"""
    skill_name = os.path.basename(skill_dir.rstrip('/'))
    skill_md_path = os.path.join(skill_dir, 'SKILL.md')

    result = {
        'name': skill_name,
        'path': skill_dir,
        'scores': {},
        'total': 0,
        'rating': '',
        'suggestions': [],
    }

    # 读取 SKILL.md
    if not os.path.isfile(skill_md_path):
        result['total'] = 0
        result['rating'] = '⭐'
        result['suggestions'].append('缺少 SKILL.md 文件')
        result['scores'] = {
            'matching': (0, '无 SKILL.md'),
            'completeness': (0, '无 SKILL.md'),
            'error_handling': (0, '无 SKILL.md'),
            'description': (0, '无 SKILL.md'),
            'efficiency': (0, '无 SKILL.md'),
        }
        return result

    try:
        with open(skill_md_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except OSError as e:
        result['suggestions'].append(f'读取 SKILL.md 失败: {e}')
        return result

    meta, body = parse_yaml_frontmatter(content)
    if meta is None:
        meta = {}

    has_scripts = os.path.isdir(os.path.join(skill_dir, 'scripts'))

    # 五维评分
    s1, r1 = score_matching(skill_dir, meta, body, has_scripts)
    s2, r2 = score_completeness(skill_dir, meta, body, has_scripts)
    s3, r3 = score_error_handling(skill_dir, meta, body, has_scripts)
    s4, r4 = score_description(skill_dir, meta, body, has_scripts)
    s5, r5 = score_token_efficiency(skill_dir, meta, body, has_scripts)

    result['scores'] = {
        'matching': (s1, r1),
        'completeness': (s2, r2),
        'error_handling': (s3, r3),
        'description': (s4, r4),
        'efficiency': (s5, r5),
    }
    result['total'] = s1 + s2 + s3 + s4 + s5
    result['rating'] = get_rating(result['total'])

    # 生成改进建议
    if s1 < 15:
        result['suggestions'].append('检查实现方案是否与任务类型匹配')
    if s2 < 15:
        result['suggestions'].append('补全缺失文件，移除未完成标记')
    if s3 < 15:
        result['suggestions'].append('增加错误处理和 fallback 机制')
    if s4 < 15:
        result['suggestions'].append('优化 description：确保中英文触发词覆盖，避免泛化')
    if s5 < 15:
        result['suggestions'].append('精简 SKILL.md，将详细内容移至 references/')

    return result


def scan_skills(scan_dir):
    """扫描目录下所有 skills"""
    results = []
    try:
        entries = sorted(os.listdir(scan_dir))
    except OSError as e:
        print(f'❌ 无法读取目录 {scan_dir}: {e}', file=sys.stderr)
        sys.exit(1)

    for entry in entries:
        full_path = os.path.join(scan_dir, entry)
        if os.path.isdir(full_path) and not entry.startswith('.'):
            # 检查是否为 skill（有 SKILL.md）
            if os.path.isfile(os.path.join(full_path, 'SKILL.md')):
                try:
                    result = evaluate_skill(full_path)
                    results.append(result)
                except Exception as e:
                    results.append({
                        'name': entry,
                        'path': full_path,
                        'total': 0,
                        'rating': '⭐',
                        'scores': {},
                        'suggestions': [f'评估出错: {e}'],
                    })
    return results


# ============================================================
# 输出格式化
# ============================================================

def format_markdown(results, scan_dir=None):
    """生成 Markdown 格式报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        '# 🔍 Skills 质量审查报告',
        f'日期：{now}',
    ]
    if scan_dir:
        lines.append(f'扫描目录：`{scan_dir}`')
    lines.append(f'扫描数量：{len(results)} 个')
    lines.append('')

    if not results:
        lines.append('未发现任何 skill。')
        return '\n'.join(lines)

    # 按总分排序
    results_sorted = sorted(results, key=lambda r: r['total'], reverse=True)

    # 汇总表
    lines.append('## 📊 汇总评分')
    lines.append('')
    lines.append('| # | Skill | 匹配 | 完成 | 容错 | 精度 | 效率 | 总分 | 评级 |')
    lines.append('|---|-------|------|------|------|------|------|------|------|')
    for i, r in enumerate(results_sorted, 1):
        s = r['scores']
        m = s.get('matching', (0, ''))[0]
        c = s.get('completeness', (0, ''))[0]
        e = s.get('error_handling', (0, ''))[0]
        d = s.get('description', (0, ''))[0]
        t = s.get('efficiency', (0, ''))[0]
        lines.append(f'| {i} | {r["name"]} | {m} | {c} | {e} | {d} | {t} | {r["total"]} | {r["rating"]} |')

    # 统计
    lines.append('')
    lines.append('## 📈 统计')
    totals = [r['total'] for r in results]
    avg = sum(totals) / len(totals) if totals else 0
    excellent = sum(1 for t in totals if t >= 90)
    good = sum(1 for t in totals if 75 <= t < 90)
    pass_ = sum(1 for t in totals if 60 <= t < 75)
    poor = sum(1 for t in totals if t < 60)
    lines.append(f'- 平均分：{avg:.1f}')
    lines.append(f'- 优秀(90+)：{excellent} 个')
    lines.append(f'- 良好(75-89)：{good} 个')
    lines.append(f'- 合格(60-74)：{pass_} 个')
    lines.append(f'- 较差(<60)：{poor} 个')

    # 逐个评审
    lines.append('')
    lines.append('## 📝 逐个评审')
    for r in results_sorted:
        lines.append(f'### {r["name"]} — {r["total"]}分 {r["rating"]}')
        s = r['scores']
        for key, label in [('matching', '匹配度'), ('completeness', '完成度'),
                           ('error_handling', '容错性'), ('description', '精度'),
                           ('efficiency', '效率')]:
            val = s.get(key, (0, ''))
            lines.append(f'- {label} {val[0]}/20：{val[1]}')
        if r['suggestions']:
            lines.append(f'- 💡 改进建议：{"；".join(r["suggestions"])}')
        lines.append('')

    return '\n'.join(lines)


def format_json(results, scan_dir=None):
    """生成 JSON 格式报告"""
    report = {
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'scan_dir': scan_dir,
        'count': len(results),
        'results': [],
    }
    for r in results:
        item = {
            'name': r['name'],
            'path': r['path'],
            'total': r['total'],
            'rating': r['rating'],
            'scores': {},
            'suggestions': r['suggestions'],
        }
        for key in ['matching', 'completeness', 'error_handling', 'description', 'efficiency']:
            val = r['scores'].get(key, (0, ''))
            item['scores'][key] = {'score': val[0], 'reason': val[1]}
        report['results'].append(item)

    # 统计
    totals = [r['total'] for r in results]
    report['stats'] = {
        'average': round(sum(totals) / len(totals), 1) if totals else 0,
        'excellent': sum(1 for t in totals if t >= 90),
        'good': sum(1 for t in totals if 75 <= t < 90),
        'pass': sum(1 for t in totals if 60 <= t < 75),
        'poor': sum(1 for t in totals if t < 60),
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='🔍 Skill 质量检测工具 - 自动评估 skills 质量并输出报告',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  python3 check_quality.py --scan-dir /root/.openclaw/skills/
  python3 check_quality.py --skill /root/.openclaw/skills/my-skill/
  python3 check_quality.py --scan-dir /root/.openclaw/skills/ --format json --output /tmp/report.json
'''
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--scan-dir', help='扫描目录下所有 skills')
    group.add_argument('--skill', help='评估单个 skill 目录')
    parser.add_argument('--format', choices=['markdown', 'json'], default='markdown',
                        help='输出格式（默认 markdown）')
    parser.add_argument('--output', '-o', help='输出文件路径（默认打印到终端）')

    args = parser.parse_args()

    # 执行扫描
    if args.scan_dir:
        scan_dir = os.path.abspath(args.scan_dir)
        if not os.path.isdir(scan_dir):
            print(f'❌ 目录不存在: {scan_dir}', file=sys.stderr)
            sys.exit(1)
        results = scan_skills(scan_dir)
        if not results:
            print(f'⚠️ 目录 {scan_dir} 下未发现任何 skill（含 SKILL.md 的子目录）', file=sys.stderr)
            sys.exit(0)
    else:
        skill_dir = os.path.abspath(args.skill)
        if not os.path.isdir(skill_dir):
            print(f'❌ 目录不存在: {skill_dir}', file=sys.stderr)
            sys.exit(1)
        results = [evaluate_skill(skill_dir)]
        scan_dir = None

    # 格式化输出
    if args.format == 'json':
        output = format_json(results, scan_dir)
    else:
        output = format_markdown(results, scan_dir)

    # 写入或打印
    if args.output:
        try:
            output_path = os.path.abspath(args.output)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(output)
            print(f'✅ 报告已写入: {output_path}')
        except OSError as e:
            print(f'❌ 写入失败: {e}', file=sys.stderr)
            sys.exit(1)
    else:
        print(output)


if __name__ == '__main__':
    main()
