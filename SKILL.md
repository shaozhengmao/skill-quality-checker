---
name: skill-quality-checker
description: >
  Skill 质量检测工具。对已安装的 skills 进行自动化质量评估，按5个维度打分
  （问题-方案匹配度、完成度、容错性、Description精度、Token效率），输出评分报告和改进建议。
  触发词：检查skill质量、评估skill、skill质量报告、skill review、审查skill。
---

# Skill 质量检测工具

自动评估已安装 skills 的质量，输出评分报告。

## 使用方式

运行脚本扫描并评分：

```bash
# 扫描所有 skills
python3 {SKILL_DIR}/scripts/check_quality.py --scan-dir /root/.openclaw/skills/

# 扫描单个 skill
python3 {SKILL_DIR}/scripts/check_quality.py --skill /root/.openclaw/skills/some-skill/

# 输出 markdown 报告到文件
python3 {SKILL_DIR}/scripts/check_quality.py --scan-dir /root/.openclaw/skills/ --format markdown --output /tmp/report.md

# 输出 JSON
python3 {SKILL_DIR}/scripts/check_quality.py --scan-dir /root/.openclaw/skills/ --format json --output /tmp/report.json
```

`{SKILL_DIR}` 替换为本 skill 的实际路径（即 SKILL.md 所在目录）。

## 评分维度（满分100）

| 维度             | 分值 | 核心检查点             |
|----------------|----|-------------------|
| 问题-方案匹配度       | 20 | 任务类型与实现方案是否匹配     |
| 完成度            | 20 | 文件完整性、格式规范、无 TODO |
| 容错性            | 20 | 错误处理、fallback 机制  |
| Description 精度 | 20 | 触发词覆盖、长度适中、不泛化    |
| Token 效率       | 20 | 文件大小、渐进式披露        |

评级：⭐⭐⭐⭐⭐(90+) ⭐⭐⭐⭐(75-89) ⭐⭐⭐(60-74) ⭐⭐(<60)

## 工作流程

1. 运行 `check_quality.py`，获取评分报告
2. 阅读报告中的改进建议
3. 如需详细评分标准，参考 `references/scoring-criteria.md`

## 注意事项

- 脚本只用 Python 标准库，无需额外安装
- 评分为启发式静态分析，供参考，不替代人工审查
- 如果扫描目录不存在或为空，脚本会给出明确提示
