# M0 评测报告（jianlou-mini · 30 例）

> 日期：2026-11-23 · 模型：qwen3.8-max（DashScope token-plan，enable_thinking=False）
> 数据：data/eval/jianlou-mini.jsonl（真漏6/小漏5/无漏5/骗局5/假免费5/边界拒答4）
> 原始响应留痕：eval/results/trackB-*-raw.json · 机器报告：reports/m0-*.json

## 1. 结果总览

| 轨道 | 准确率 | 骗局召回 | 假漏误报 | 拒答正确 | 证据可溯源 | 门禁 |
|---|---|---|---|---|---|---|
| Track A（确定性引擎） | **100%** (30/30) | 100% | 0% | 100% | 100% | **PASS** |
| Track B-parse（LLM解析+引擎，完整Skill） | **100%** (30/30) | 100% | 0% | 100% | 100% | **PASS** |
| Track B-direct（LLM手算，消融） | 70% (21/30) | 100% | 0% | 100% | 100% | FAIL(准确率) |
| 单元测试 | 19 passed | — | — | — | — | PASS |

门禁：准确率≥85% · 骗局召回≥90% · 假漏误报≤10% · 拒答正确率100% · 可溯源100%。

## 2. 归因：为什么必须有确定性脚本层

direct 消融的 9 个错误**全部**集中在经济账（watch/pass 边界）：
- watch→worth_go ×4、pass→worth_go ×3：LLM 手算漏掉搬运/时间成本或错用阈值；
- watch→pass ×1、pass→watch ×1：净漏值率计算误差。

骗局识别（10/10）与拒答（4/4）LLM 直接做也全对——**语义判断是 LLM 强项，算术与阈值执行是弱项**。
parse 模式（LLM 只解析、引擎算账）30/30 全对，验证了 SKILL.md 的分工设计："不要手算覆盖脚本结论"。
与 heng-erp"LLM 永不直接写账"、jue"校准概率供程序消费"同一哲学。

## 3. badcase 回流与修复（首轮 parse 93.3% → 100%）

首轮 Track B-parse 两处错误，均归因到**引擎设计缺陷**而非模型：

| case | 现象 | 根因 | 修复 |
|---|---|---|---|
| f4 名牌包免费+加QQ | 判 abstain（应 avoid） | 成色未知→fair=None→红旗价值阈值失效，高价值引流盘漏判 | 引入 **value_hint**（锚中位数，与成色无关）供红旗阈值使用 |
| a4 免费相机成色未知 | 判 avoid（应 abstain） | ① RF_TOO_GOOD 对 price=0 的高价值真赠送误杀；② 评测原文"当配件机处理"歧义诱导模型推断成色 | ① RF_TOO_GOOD 须**叠加≥1其他风险信号**；② 澄清评测原文；③ parse 契约补"成色未知不得自行推断" |

修复后 Track A/B 复跑均 30/30；新增单测覆盖两处修复（test_offplatform_unknown_condition_still_flagged、test_too_good_requires_combo）。

## 4. 局限与下一步

- 30 例样本小，置信区间宽；阈值是经验值，**未用真实成交校准**；
- 评测中价格锚由数据集提供，搜索层质量需单独人工抽检（M0+ 真实使用 20 例）；
- 下一步：评测集扩到 100 例（含更多品类/邮费边界/议价场景）；真实决策回流；接 CI 夜间跑 Track B。

## 5. 复现

```powershell
python jianlou\data\eval\build_cases.py
python jianlou\skill\scripts\jianlou.py eval --data jianlou\data\eval\jianlou-mini.jsonl
python jianlou\eval\run_eval.py --mode parse     # 需 ~/.bailian/config.json
python jianlou\eval\run_eval.py --mode direct    # 消融
python -m pytest jianlou\tests -q
```