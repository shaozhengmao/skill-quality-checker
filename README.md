# Skill Quality Checker

🔍 **Skill 质量检测工具** - 自动化评估已安装 skills 的质量，输出评分报告和改进建议。

## 功能特性

- ✅ **五维评分体系**：问题-方案匹配度、完成度、容错性、Description精度、Token效率
- ✅ **自动化检测**：无需人工干预，一键扫描所有 skills
- ✅ **详细报告**：Markdown / JSON 格式输出，包含具体改进建议
- ✅ **零依赖**：只使用 Python 标准库，无需安装第三方包

## 快速开始

### 扫描所有 skills

```bash
python3 scripts/check_quality.py --scan-dir ~/.claude/skills/
```

### 评估单个 skill

```bash
python3 scripts/check_quality.py --skill ~/.claude/skills/my-skill/
```

### 输出到文件

```bash
# Markdown 格式
python3 scripts/check_quality.py --scan-dir ~/.claude/skills/ --format markdown --output report.md

# JSON 格式
python3 scripts/check_quality.py --scan-dir ~/.claude/skills/ --format json --output report.json
```

## 评分维度（满分100）

| 维度 | 分值 | 核心检查点 |
|------|------|------------|
| 问题-方案匹配度 | 20 | 任务类型与实现方案是否匹配 |
| 完成度 | 20 | 文件完整性、格式规范、无 TODO |
| 容错性 | 20 | 错误处理、fallback 机制 |
| Description 精度 | 20 | 触发词覆盖、长度适中、不泛化 |
| Token 效率 | 20 | 文件大小、渐进式披露 |

## 评级标准

| 评级 | 分数范围 | 说明 |
|------|----------|------|
| ⭐⭐⭐⭐⭐ | 90-100 | 优秀 |
| ⭐⭐⭐⭐ | 75-89 | 良好 |
| ⭐⭐⭐ | 60-74 | 合格 |
| ⭐⭐ | 40-59 | 较差 |
| ⭐ | 0-39 | 很差 |

## 报告示例

```markdown
# 🔍 Skills 质量审查报告
日期：2026-03-06 19:09
扫描数量：3 个

## 📊 汇总评分

| # | Skill | 匹配 | 完成 | 容错 | 精度 | 效率 | 总分 | 评级 |
|---|-------|------|------|------|------|------|------|------|
| 1 | pdf-editor | 19 | 18 | 16 | 18 | 17 | 88 | ⭐⭐⭐⭐ |
| 2 | docx | 18 | 16 | 14 | 15 | 15 | 78 | ⭐⭐⭐⭐ |
| 3 | my-skill | 14 | 12 | 8 | 10 | 10 | 54 | ⭐⭐ |

## 📝 逐个评审

### pdf-editor — 88分 ⭐⭐⭐⭐
- 匹配度 19/20：执行类任务且有 scripts/，方案匹配
- 完成度 18/20：YAML frontmatter 完整; 3 个非空脚本文件
- 容错性 16/20：错误处理覆盖率 75%
- 精度 18/20：长度适中，包含中英文触发词
- 效率 17/20：SKILL.md 4.2KB，有外部参考文件
```

## 详细评分标准

详见 [references/scoring-criteria.md](references/scoring-criteria.md)，包含：

- 各维度的详细评分规则
- 扣分项说明
- 示例分析

## 目录结构

```
skill-quality-checker/
├── SKILL.md                    # Skill 定义文件
├── scripts/
│   └── check_quality.py        # 质量检测脚本
└── references/
    └── scoring-criteria.md     # 详细评分标准
```

## 注意事项

- 脚本只用 Python 标准库，无需额外安装
- 评分为启发式静态分析，供参考，不替代人工审查
- 如果扫描目录不存在或为空，脚本会给出明确提示

## 作为 Skill 使用

本工具已封装为 Skill，可在 CatPaw 中直接使用：

```
检查 my-skill 质量
评估所有 skills
生成 skill 质量报告
```

## License

[MIT License](LICENSE)

