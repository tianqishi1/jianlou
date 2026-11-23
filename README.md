# jianlou（捡漏）

**免费/低价闲置"值不值得去拿"的判断引擎**：可解释、可拒答、带证据。Codex Skill 形态，零第三方依赖（Python 3.10+）。

> 设计文档：[产品设计方案](docs/产品设计方案.md) · [技术实现方案](docs/技术实现方案.md) · [M0 评测报告](docs/benchmarks/m0-eval.md)
> 可行性论证：D:\codex\捡漏Skill可行性评估报告.md（v2.1）

## 核心

```
净漏值率 = (公允价 − 总成本) / 公允价
总成本 = 要价 + 邮费 + 定金 + 搬运交通 + 时间
分级：值得去拿(≥25%) / 观望(10–25%) / 放弃(<10%) / 别去(硬红旗) / 无法评估(拒答)
```

**LLM 只解析不算账**（评测实证：手算 70% vs 解析+引擎 100%）。硬红线：锚必须带来源+日期、硬红旗一票否决、永不代付、本体零爬虫。

## 快速开始

```powershell
# 安装 Skill 到 Codex
Copy-Item -Recurse D:\codex\jianlou\skill $env:USERPROFILE\.codex\skills\jianlou

# 引擎 CLI
python skill\scripts\jianlou.py selftest
python skill\scripts\jianlou.py card --input case.json
python skill\scripts\jianlou.py eval --data data\eval\jianlou-mini.jsonl

# 完整 Skill 评测（LLM-in-the-loop，需 ~/.bailian/config.json）
python eval\run_eval.py --mode parse

# 单测
python -m pytest tests -q
```

## M0 评测（2026-11-23，qwen3.8-max）

| 轨道 | 准确率 | 骗局召回 | 假漏误报 | 拒答 | 门禁 |
|---|---|---|---|---|---|
| 确定性引擎 | 100% | 100% | 0% | 100% | PASS |
| 完整 Skill（解析+引擎） | 100% | 100% | 0% | 100% | PASS |
| LLM 手算（消融） | 70% | 100% | 0% | 100% | FAIL |

## 路线

M0 Skill（本仓库）→ M1 微信 AI 工具小程序（同一引擎，流量主变现，吃 2026 成长计划）+ 一城付费简报验证订阅 → M2 按数据决策。不做聚合型 App、不爬闲鱼/微信、不代付。

## 许可

Apache-2.0（建议，发布前补 LICENSE）。