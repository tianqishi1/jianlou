---
name: jianlou
description: 捡漏判断引擎：免费/低价闲置与赠送物品值不值得去拿。用户给出闲置 listing（截图/链接/文字，如闲鱼免费送、豆瓣小组、同城赠送、搬家白送）并问"值不值/是不是漏/有没有坑/帮我捡漏"时使用；也用于断舍离赠送文案与安全交付。不做全网爬虫聚合、不代付、不做二手交易撮合。
metadata:
  short-description: 捡漏估值判断 + 避坑 + 赠送助手
---

# 捡漏（jianlou）

把"免费/低价的东西值不值得去拿"做成**可解释、可拒答、带证据**的判断。核心公式：

```
净漏值率 = (公允价 − 总成本) / 公允价
总成本 = 要价 + 邮费 + 定金 + 搬运交通成本 + 时间成本
```

**免费 ≠ 值得**：搬运、距离、瑕疵、骗局风险都要计入。判断分级：`值得去拿 / 观望 / 放弃 / 别去(骗局) / 无法评估(拒答)`。

## 硬约束（不可违反）

1. **每个价格锚必须带来源+日期**；搜不到可靠锚 → 输出"无法评估"，绝不硬给结论。
2. **命中硬红旗 → "别去"**，优先于一切漏值计算（红旗清单见 references/fraud-patterns.md）。
3. **永不代付、永不代拍、永不建议任何预付**（定金/预留费/到付高额邮费都是硬红旗）。
4. Skill 本体**不爬闲鱼/微信**、不收集账号密码；只处理用户提供的数据与公开页面（见 references/data-sources.md）。
5. 输出必带免责声明；不承诺"保真/保抢到/保证赚钱"。
6. 阈值是经验值：与 references/valuation-anchors.md 保持一致，改动须同步脚本并跑评测。

## 工作流

### 模式 A：捡漏判断（主模式）

1. **解析标的**：从用户截图/文字/链接提取：品类、型号、成色、配件缺项、明示瑕疵、保修剩余、要价、邮费/定金、位置距离、自提难度、卖家信号（账号年龄、是否实拍、是否引导加微信/QQ、叙事话术、催促）。读图用宿主视觉能力。信息不足先问关键项（成色/距离/要价），其余标"未知"。
2. **搜价格锚**：用宿主搜索找 1–3 个锚（近期成交 > 二手行情 > 全新价×0.6 折算），每个锚记录来源+日期。搜不到 → 直接"无法评估"。
3. **确定性计算**：把结构化结果写成 JSON（schema 见下），运行：
   ```bash
   python {skill_dir}/scripts/jianlou.py card --input case.json
   ```
   脚本输出卡片 JSON（公允价/总成本/净漏值率/红旗/分级/置信度）。**不要手算覆盖脚本结论**；对脚本结论有异议时检查输入字段是否解析错误。
4. **输出捡漏卡片**：按 assets/card-template.md 渲染给用户（结论先行、证据列全、行动具体）。

输入 JSON schema（脚本 `card` 命令）：
```json
{"item": {"title": "", "category": "3c数码|家具|家电|服饰|图书|母婴|运动|其他",
          "condition": "全新|几乎全新|轻微使用痕迹|明显使用痕迹|故障/配件机|未知",
          "accessories_missing": [], "defects": [], "warranty_months_left": 0,
          "distance_km": 0, "pickup": "easy|medium|hard"},
 "ask": {"price": 0, "shipping_fee": null, "deposit": null,
         "offplatform_contact": false, "account_age_days": null,
         "images_real": null, "story": null, "urgent_pressure": false},
 "anchors": [{"kind": "sold|used|new", "low": 0, "high": 0, "source": "", "date": ""}]}
```

### 模式 B：断舍离赠送助手（供给侧）

用户要送/低价出自己的闲置：拍照描述 → 生成如实的赠送文案（成色/瑕疵/自提条件写清）→ 渠道建议（闲鱼免费送/豆瓣同城小组/小区群，见 data-sources.md）→ 回复模板 → 安全交付清单（公共场所、不入户、不预收对方任何费用）。全部由用户本人发布，Skill 不代发。

### 模式 C：定时巡检（可选，宿主支持时）

用户要求"每天帮我盯某类免费/低价好物"：用宿主 automation/定时任务驱动，按 data-sources.md 的**绿区源**低频巡检 → 对每条候选走模式 A → 命中 criteria 的卡片汇总成简报。不承诺分钟级实时；闲鱼站内监控只能由用户自部署外部工具后把结果喂给本 Skill。

## 参考（按需读取）

- references/fraud-patterns.md — 骗局模式库与红旗规则（判"别去"前必读）
- references/valuation-anchors.md — 分品类估值锚、成色/配件/搬运折价经验值与阈值
- references/data-sources.md — 数据源分级与合规边界（绿/黄/红区）
- assets/card-template.md — 捡漏卡片输出模板

## 评测

改动规则/阈值后必须跑：`python {skill_dir}/scripts/jianlou.py eval --data <repo>/data/eval/jianlou-mini.jsonl`，门禁：准确率≥85%、骗局召回≥90%、假漏误报≤10%、拒答正确率100%、证据可溯源100%。badcase 回流为新评测用例。