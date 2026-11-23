#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jianlou（捡漏）确定性引擎 + CLI。零第三方依赖，Python 3.10+。

职责边界（与 SKILL.md 一致）：
- LLM/宿主负责：语义解析 listing、搜索价格锚、读图；
- 本脚本负责：估值数学、红旗规则、分级判定、拒答、评测断言。
所有阈值均为经验值，须用自有案例校准（见 references/valuation-anchors.md）。

用法：
  python jianlou.py card --input case.json          # 结构化输入 -> 捡漏卡片 JSON
  python jianlou.py eval --data cases.jsonl         # 确定性引擎评测（Track A）
  python jianlou.py selftest                        # 内置冒烟用例
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

LABELS = ("worth_go", "watch", "pass", "avoid", "abstain")
LABEL_ZH = {
    "worth_go": "值得去拿", "watch": "观望", "pass": "放弃",
    "avoid": "别去", "abstain": "无法评估",
}

# ---- 经验参数（references/valuation-anchors.md 有说明与校准要求） ----
CONDITION_FACTOR = {
    "全新": 1.10, "几乎全新": 1.00, "轻微使用痕迹": 0.85,
    "明显使用痕迹": 0.65, "故障/配件机": 0.30,
}
NEW_TO_USED = 0.60          # 只有全新锚时折算二手公允价的经验系数
ACCESSORY_PENALTY = 0.03    # 每缺一项配件 -3%，封顶 -15%
DEFECT_PENALTY = 0.08       # 每处明示瑕疵 -8%，封顶 -30%
WARRANTY_BONUS = 0.005      # 每剩 1 个月保修 +0.5%，封顶 +6%
PICKUP_COST = {"easy": 0.0, "medium": 30.0, "hard": 80.0}
DISTANCE_FREE_KM = 10.0     # 10km 内不计额外交通成本
DISTANCE_PER_KM = 2.0       # 超出部分 2 元/km
TRANSPORT_CAP = 150.0
TIME_COST = 15.0            # 自提时间机会成本（经验值）
WORTH_GO_RATE = 0.25        # 净漏值率 >=25% -> 值得去拿
WATCH_RATE = 0.10           # 10%~25% -> 观望
SHIPPING_MIN_FLAG = 12.0    # 邮费红旗下限
SHIPPING_RATIO_FLAG = 0.25  # 邮费 > max(12, 25%*公允价) -> 邮费盘
TOO_GOOD_RATIO = 0.05       # 要价 <=5% 公允价且高价值 -> 引流/骗局嫌疑
TOO_GOOD_MIN_VALUE = 500.0
OFFPLATFORM_MIN_VALUE = 300.0
NEW_ACCOUNT_DAYS = 30
STORY_KEYWORDS = ("海关", "扣押", "罚没", "内部渠道", "抵债", "富二代", "盲盒", "走私")

RED_FLAGS = {
    "RF_DEPOSIT": "要求预付定金/预留费（任何形式预付都是硬红旗）",
    "RF_SHIPPING": "免费/低价但邮费显著高于合理运费（邮费盘）",
    "RF_OFFPLATFORM": "高价值物品引导脱离平台交易（微信/QQ），叠加新号风险更高",
    "RF_TOO_GOOD": "要价<=5%价值且高价值，并叠加其他风险信号（脱离平台/新号/盗图/叙事/催促/定金）",
    "RF_FAKE_IMG": "非实拍/盗图",
    "RF_STORY": "命中骗局叙事关键词（海关扣押/内部渠道/抵债/富二代/盲盒等）",
}
SOFT_FLAGS = {
    "SF_NEW_ACCOUNT": "新注册账号（<30 天）",
    "SF_DISTANCE": "自提距离 >30km",
    "SF_URGENT": "催促立即决定/制造紧迫感",
    "SF_OFFPLATFORM_LOW": "低价值物品引导脱离平台（降级为软红旗）",
}


def _num(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def valid_anchors(anchors):
    """证据可溯源：每个锚必须带非空 source 与 date，否则视为无效。"""
    out = []
    for a in anchors or []:
        if _num(a.get("low"), -1) < 0 or _num(a.get("high"), -1) < 0:
            continue
        if not str(a.get("source") or "").strip() or not str(a.get("date") or "").strip():
            continue
        out.append(a)
    return out


def fair_value(item, anchors):
    """返回 (公允价, 锚说明) 或 (None, 原因)。"""
    va = valid_anchors(anchors)
    if not va:
        return None, "无有效价格锚（缺来源/日期或为空）"
    sold = [a for a in va if a.get("kind") == "sold"]
    used = [a for a in va if a.get("kind") == "used"]
    new = [a for a in va if a.get("kind") == "new"]
    pick, basis = None, ""
    if sold:
        pick = sold[0]; basis = "近期成交锚"
    elif used:
        pick = used[0]; basis = "二手行情锚"
    elif new:
        pick = new[0]; basis = "全新锚×0.60 折算"
    base = (_num(pick["low"]) + _num(pick["high"])) / 2.0
    if basis.startswith("全新"):
        base *= NEW_TO_USED
    cond = item.get("condition", "未知")
    if cond not in CONDITION_FACTOR:
        return None, "成色未知，无法估值"
    factor = CONDITION_FACTOR[cond]
    acc_pen = min(ACCESSORY_PENALTY * len(item.get("accessories_missing") or []), 0.15)
    def_pen = min(DEFECT_PENALTY * len(item.get("defects") or []), 0.30)
    war_bonus = min(WARRANTY_BONUS * max(0, int(_num(item.get("warranty_months_left")))), 0.06)
    fair = base * factor * (1.0 - acc_pen - def_pen + war_bonus)
    desc = f"{basis} {pick.get('source')}({pick.get('date')}) 区间¥{_num(pick['low']):.0f}-{_num(pick['high']):.0f} × 成色{factor:.2f} × 修正{1 - acc_pen - def_pen + war_bonus:.2f}"
    return round(fair, 2), desc


def value_hint(anchors):
    """与成色无关的价值提示（锚中位数，全新锚×0.6）：成色未知时红旗阈值仍可用。"""
    va = valid_anchors(anchors)
    if not va:
        return None
    for kind in ("sold", "used", "new"):
        pick = [a for a in va if a.get("kind") == kind]
        if pick:
            mid = (_num(pick[0]["low"]) + _num(pick[0]["high"])) / 2.0
            return mid * NEW_TO_USED if kind == "new" else mid
    return None


def red_flags(item, ask, fair, hint=None):
    hard, soft = [], []
    f = hint if hint is not None else (fair if fair is not None else 0.0)
    price = _num(ask.get("price"))
    shipping = ask.get("shipping_fee")
    deposit = _num(ask.get("deposit"))
    story = str(ask.get("story") or "")
    acct = ask.get("account_age_days")
    off = bool(ask.get("offplatform_contact"))
    if deposit > 0:
        hard.append(("RF_DEPOSIT", f"定金¥{deposit:.0f}"))
    if shipping is not None and _num(shipping) > max(SHIPPING_MIN_FLAG, SHIPPING_RATIO_FLAG * f):
        hard.append(("RF_SHIPPING", f"邮费¥{_num(shipping):.0f} > max(12, 25%×公允价¥{f:.0f})"))
    if off and (f >= OFFPLATFORM_MIN_VALUE or (acct is not None and _num(acct) < NEW_ACCOUNT_DAYS)):
        hard.append(("RF_OFFPLATFORM", f"引导脱离平台 + 公允价¥{f:.0f}/账号{acct}天"))
    elif off:
        soft.append(("SF_OFFPLATFORM_LOW", "低价值物品引导脱离平台"))
    if ask.get("images_real") is False:
        hard.append(("RF_FAKE_IMG", "非实拍/盗图"))
    hit = [k for k in STORY_KEYWORDS if k in story]
    if hit:
        hard.append(("RF_STORY", "叙事关键词: " + "/".join(hit)))
    other_risk = (off or (acct is not None and _num(acct) < NEW_ACCOUNT_DAYS)
                  or ask.get("images_real") is False or bool(hit)
                  or bool(ask.get("urgent_pressure")) or deposit > 0)
    if f >= TOO_GOOD_MIN_VALUE and price <= TOO_GOOD_RATIO * f and other_risk:
        hard.append(("RF_TOO_GOOD", f"要价¥{price:.0f} <= 5%×价值¥{f:.0f} 且叠加其他风险信号"))
    if acct is not None and _num(acct) < NEW_ACCOUNT_DAYS:
        soft.append(("SF_NEW_ACCOUNT", f"账号{acct}天"))
    if _num(item.get("distance_km")) > 30:
        soft.append(("SF_DISTANCE", f"{_num(item.get('distance_km')):.0f}km"))
    if ask.get("urgent_pressure"):
        soft.append(("SF_URGENT", "催促立即决定"))
    return hard, soft


def evaluate(inp):
    """结构化输入 -> 捡漏卡片（确定性）。"""
    item = inp.get("item") or {}
    ask = inp.get("ask") or {}
    anchors = inp.get("anchors") or []
    fair, basis = fair_value(item, anchors)
    hint = value_hint(anchors)
    hard, soft = red_flags(item, ask, fair, hint)
    flags = [{"id": i, "severity": "hard", "desc": RED_FLAGS[i], "evidence": e} for i, e in hard]
    flags += [{"id": i, "severity": "soft", "desc": SOFT_FLAGS[i], "evidence": e} for i, e in soft]

    card = {
        "verdict": None, "verdict_zh": None, "confidence": None,
        "fair_value": fair, "total_cost": None, "net_rate": None,
        "flags": flags, "anchors_used": valid_anchors(anchors),
        "valuation_basis": basis, "advice": "", "disclaimer": "估值仅供参考，交易自行决策；永不代付。",
    }
    if hard:
        card.update(verdict="avoid", verdict_zh=LABEL_ZH["avoid"], confidence="high",
                    advice="命中硬红旗，别去；如已联系，停止任何预付并保留证据。")
        return card
    if fair is None:
        card.update(verdict="abstain", verdict_zh=LABEL_ZH["abstain"], confidence="low",
                    advice=f"拒答：{basis}。补充可靠价格锚/成色信息后再评。")
        return card

    transport = min(PICKUP_COST.get(item.get("pickup", "easy"), 0.0)
                    + max(0.0, _num(item.get("distance_km")) - DISTANCE_FREE_KM) * DISTANCE_PER_KM,
                    TRANSPORT_CAP)
    total = _num(ask.get("price")) + _num(ask.get("shipping_fee")) + _num(ask.get("deposit")) + transport + TIME_COST
    net = (fair - total) / fair if fair > 0 else -1.0
    confidence = "high" if not soft else ("medium" if len(soft) == 1 else "low")
    if net >= WORTH_GO_RATE:
        verdict = "worth_go" if confidence != "low" else "watch"
    elif net >= WATCH_RATE:
        verdict = "watch"
    else:
        verdict = "pass"
    advice = {
        "worth_go": "净漏值充足且无硬红旗：尽快联系，约公共场所自提，先验货后搬运。",
        "watch": "有一定漏值但不充分：可议价或等降价；确认成色/配件后再决定。",
        "pass": "无漏值（价格正常或搬运/时间成本吃掉价值）：不建议专程去拿。",
    }[verdict]
    card.update(verdict=verdict, verdict_zh=LABEL_ZH[verdict], confidence=confidence,
                total_cost=round(total, 2), net_rate=round(net, 4), advice=advice)
    return card


# ---------------- 评测（Track A：确定性引擎） ----------------
def run_eval(cases):
    n = len(cases)
    correct = 0
    confusion = {g: {p: 0 for p in LABELS} for g in LABELS}
    scam_total = scam_hit = fake_fp = 0
    abstain_total = abstain_ok = 0
    trace_ok = trace_total = 0
    details = []
    for c in cases:
        gold = c["gold"]
        card = evaluate(c["input"])
        pred = card["verdict"]
        ok = pred == gold
        correct += ok
        confusion[gold][pred] += 1
        if gold == "avoid":
            scam_total += 1
            scam_hit += (pred == "avoid")
            fake_fp += (pred == "worth_go")
        if gold == "abstain":
            abstain_total += 1
            abstain_ok += (pred == "abstain")
        for a in card["anchors_used"]:
            trace_total += 1
            trace_ok += bool(a.get("source") and a.get("date"))
        details.append({"id": c["id"], "gold": gold, "pred": pred, "ok": ok,
                        "net_rate": card["net_rate"], "flags": [f["id"] for f in card["flags"]]})
    metrics = {
        "n": n,
        "accuracy": round(correct / n, 4) if n else 0,
        "scam_recall": round(scam_hit / scam_total, 4) if scam_total else None,
        "fake_fp_rate": round(fake_fp / scam_total, 4) if scam_total else None,
        "abstain_correct": round(abstain_ok / abstain_total, 4) if abstain_total else None,
        "traceability": round(trace_ok / trace_total, 4) if trace_total else 1.0,
        "confusion": confusion,
    }
    gates = {
        "accuracy>=0.85": metrics["accuracy"] >= 0.85,
        "scam_recall>=0.90": (metrics["scam_recall"] or 0) >= 0.90,
        "fake_fp_rate<=0.10": (metrics["fake_fp_rate"] if metrics["fake_fp_rate"] is not None else 0) <= 0.10,
        "abstain_correct==1.0": (metrics["abstain_correct"] or 0) == 1.0,
        "traceability==1.0": metrics["traceability"] == 1.0,
    }
    return {"metrics": metrics, "gates": gates, "pass": all(gates.values()), "details": details}


def load_jsonl(path):
    cases = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def selftest():
    base = {"item": {"title": "t", "category": "其他", "condition": "几乎全新", "distance_km": 3, "pickup": "easy"},
            "ask": {"price": 0}, "anchors": [{"kind": "used", "low": 150, "high": 250, "source": "s", "date": "2026-11-01"}]}
    assert evaluate(base)["verdict"] == "worth_go"
    import copy
    c = copy.deepcopy(base); c["ask"]["deposit"] = 100
    assert evaluate(c)["verdict"] == "avoid"
    c = copy.deepcopy(base); c["anchors"] = []
    assert evaluate(c)["verdict"] == "abstain"
    c = copy.deepcopy(base); c["ask"]["price"] = 190
    assert evaluate(c)["verdict"] == "pass"
    c = copy.deepcopy(base); c["ask"] = {"price": 0, "shipping_fee": 60}
    assert evaluate(c)["verdict"] == "avoid"
    print("selftest OK (5 assertions)")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="jianlou deterministic engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("card"); p.add_argument("--input", required=True)
    p = sub.add_parser("eval"); p.add_argument("--data", required=True); p.add_argument("--out")
    sub.add_parser("selftest")
    args = ap.parse_args()
    if args.cmd == "card":
        inp = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
        print(json.dumps(evaluate(inp), ensure_ascii=False, indent=2))
    elif args.cmd == "eval":
        rep = run_eval(load_jsonl(args.data))
        txt = json.dumps(rep, ensure_ascii=False, indent=2)
        if args.out:
            pathlib.Path(args.out).write_text(txt, encoding="utf-8")
        print(txt)
        sys.exit(0 if rep["pass"] else 1)
    else:
        selftest()


if __name__ == "__main__":
    main()