# -*- coding: utf-8 -*-
"""Track B：完整 Skill 评测（LLM-in-the-loop），两种模式：

- parse（默认，架构对齐）：LLM 只负责把 raw listing + 价格锚解析为结构化输入 JSON，
  确定性引擎 jianlou.evaluate() 计算结论 —— 与 SKILL.md 的分工一致（LLM 不算账）。
- direct（消融）：LLM 直接手算输出结论卡片 —— 用于归因"为什么需要确定性脚本层"。

后端：~/.bailian/config.json 活动 profile（DashScope token-plan compatible-mode）。
jue Phase 0 教训：enable_thinking=False + 空响应重试。

用法：python eval/run_eval.py [--mode parse|direct] [--model M] [--workers 4] [--limit N]
"""
from __future__ import annotations
import argparse, concurrent.futures as cf, json, pathlib, re, sys, time
import urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill" / "scripts"))
from jianlou import LABELS, load_jsonl, evaluate  # noqa: E402

SKILL_DIR = ROOT / "skill"

def bailian_profile():
    p = pathlib.Path.home() / ".bailian" / "config.json"
    cfg = json.loads(p.read_text(encoding="utf-8"))
    prof = cfg.get(cfg.get("active_config", ""), {})
    if not prof.get("api_key") or not prof.get("base_url"):
        raise SystemExit("no bailian profile")
    return prof

def endpoint(prof):
    base = prof["base_url"].rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    if "token-plan" in base:
        return base + "/compatible-mode/v1/chat/completions"
    return base + "/v1/chat/completions"

def refs():
    return [(SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"),
            "\n\n# references/fraud-patterns.md\n" + (SKILL_DIR / "references" / "fraud-patterns.md").read_text(encoding="utf-8"),
            "\n\n# references/valuation-anchors.md\n" + (SKILL_DIR / "references" / "valuation-anchors.md").read_text(encoding="utf-8")]

PARSE_CONTRACT = """

# 评测输出契约（必须遵守）
你现在执行上述 Skill 的"模式 A"第 1 步：解析标的。价格锚已由搜索提供（见用户消息），无需再搜索，无需给出结论。
只输出一个 JSON 对象（不要 markdown 围栏、不要解释），即 scripts/jianlou.py card 命令的输入：
{"item": {"title": "", "category": "3c数码|家具|家电|服饰|图书|母婴|运动|其他",
          "condition": "全新|几乎全新|轻微使用痕迹|明显使用痕迹|故障/配件机|未知",
          "accessories_missing": [], "defects": [], "warranty_months_left": 0,
          "distance_km": 0, "pickup": "easy|medium|hard"},
 "ask": {"price": 0, "shipping_fee": null, "deposit": null,
         "offplatform_contact": false, "account_age_days": null,
         "images_real": null, "story": null, "urgent_pressure": false},
 "anchors": [{"kind": "sold|used|new", "low": 0, "high": 0, "source": "", "date": ""}]}
解析规则：
- 成色/距离/要价/邮费/定金按原文如实提取；原文未提及的字段用默认值（距离0、账号null、实拍null）；成色无法判断用"未知"；原文明确说"成色未知/说不清"时必须用"未知"，不得自行推断为故障机。
- pickup 推断：自己搬/轿车可装=easy；需SUV/面包车/中等搬运=medium；需两人抬/拆装/找车拉=hard。
- 引导加微信/QQ/脱离平台 -> offplatform_contact=true；网图/渲染图/非实拍 -> images_real=false；实拍 -> true。
- 骗局叙事（海关扣押/罚没/内部渠道/抵债/富二代/盲盒等）原文摘入 story；催促/手慢无 -> urgent_pressure=true。
- anchors 原样照抄提供的价格锚，source/date 缺失时保留空字符串，不得编造。"""

DIRECT_CONTRACT = """

# 评测输出契约（必须遵守）
你现在执行上述 Skill 的"模式 A：捡漏判断"。价格锚已由搜索提供（见用户消息），无需再搜索。
只输出一个 JSON 对象（不要 markdown 围栏、不要解释），字段：
{"verdict": "worth_go|watch|pass|avoid|abstain",
 "confidence": "high|medium|low",
 "fair_value": number|null, "total_cost": number|null, "net_rate": number|null,
 "flags": ["RF_...或SF_..."],
 "anchors_used": [{"source": "...", "date": "..."}],
 "advice": "一句话"}
判定规则与阈值严格按 Skill 与 references 执行：硬红旗->avoid；无有效锚(缺来源/日期)或成色未知->abstain；
净漏值率>=25%且置信非low->worth_go；10%~25%->watch；<10%->pass。"""

def system_prompt(mode):
    return "".join(refs()) + (PARSE_CONTRACT if mode == "parse" else DIRECT_CONTRACT)

def render_anchors(anchors):
    if not anchors:
        return "【价格锚】未搜索到可靠价格锚。"
    lines = ["【价格锚】（搜索提供，注意核对来源与日期是否齐全）"]
    for a in anchors:
        src = a.get("source") or "未记录来源"
        date = a.get("date") or "未记录日期"
        lines.append(f"- {a.get('kind')} 锚：¥{a.get('low')}–{a.get('high')}（来源：{src}；日期：{date}）")
    return "\n".join(lines)

def call(prof, model, sysmsg, usermsg, retries=3):
    body = {"model": model, "messages": [{"role": "system", "content": sysmsg},
                                          {"role": "user", "content": usermsg}],
            "temperature": 0.1, "enable_thinking": False}
    data = json.dumps(body).encode("utf-8")
    for i in range(retries):
        try:
            req = urllib.request.Request(endpoint(prof), data=data, method="POST", headers={
                "Authorization": f"Bearer {prof['api_key']}", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            txt = resp["choices"][0]["message"]["content"] or ""
            if txt.strip():
                return txt
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and i < retries - 1:
                time.sleep(3 * (i + 1)); continue
            raise
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 * (i + 1))
    return ""

def parse_json(txt):
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt.strip(), flags=re.S)
    m = re.search(r"\{.*\}", txt, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def score(cases, preds):
    n = len(cases); correct = 0
    confusion = {g: {p: 0 for p in LABELS} for g in LABELS}
    scam_total = scam_hit = fake_fp = abstain_total = abstain_ok = 0
    trace_ok = trace_total = 0
    details = []
    for c, pr in zip(cases, preds):
        gold = c["gold"]
        pred = (pr or {}).get("verdict")
        if pred not in LABELS:
            pred = "parse_error"
        ok = pred == gold
        correct += ok
        if gold in confusion and pred in LABELS:
            confusion[gold][pred] += 1
        if gold == "avoid":
            scam_total += 1; scam_hit += (pred == "avoid"); fake_fp += (pred == "worth_go")
        if gold == "abstain":
            abstain_total += 1; abstain_ok += (pred == "abstain")
        for a in (pr or {}).get("anchors_used") or []:
            trace_total += 1; trace_ok += bool(a.get("source") and a.get("date"))
        details.append({"id": c["id"], "gold": gold, "pred": pred, "ok": ok,
                        "flags": (pr or {}).get("flags"), "net_rate": (pr or {}).get("net_rate")})
    metrics = {"n": n, "accuracy": round(correct / n, 4),
               "scam_recall": round(scam_hit / scam_total, 4) if scam_total else None,
               "fake_fp_rate": round(fake_fp / scam_total, 4) if scam_total else None,
               "abstain_correct": round(abstain_ok / abstain_total, 4) if abstain_total else None,
               "traceability": round(trace_ok / trace_total, 4) if trace_total else 1.0,
               "confusion": confusion}
    gates = {"accuracy>=0.85": metrics["accuracy"] >= 0.85,
             "scam_recall>=0.90": (metrics["scam_recall"] or 0) >= 0.90,
             "fake_fp_rate<=0.10": (metrics["fake_fp_rate"] or 0) <= 0.10,
             "abstain_correct==1.0": (metrics["abstain_correct"] or 0) == 1.0,
             "traceability==1.0": metrics["traceability"] == 1.0}
    return {"metrics": metrics, "gates": gates, "pass": all(gates.values()), "details": details}

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["parse", "direct"], default="parse")
    ap.add_argument("--model", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--data", default=str(ROOT / "data" / "eval" / "jianlou-mini.jsonl"))
    args = ap.parse_args()
    prof = bailian_profile()
    model = args.model or prof.get("default_text_model", "qwen3.8-max")
    cases = load_jsonl(args.data)
    if args.limit:
        cases = cases[:args.limit]
    sysmsg = system_prompt(args.mode)
    print(f"Track B[{args.mode}]: {len(cases)} cases, model={model}", flush=True)

    def work(c):
        user = f"【listing 原文】\n{c['raw_text']}\n\n{render_anchors(c['input'].get('anchors') or [])}"
        txt = call(prof, model, sysmsg, user)
        pr = parse_json(txt)
        if args.mode == "parse":
            card = evaluate(pr) if isinstance(pr, dict) and "item" in pr else None
            return c["id"], txt, pr, card
        return c["id"], txt, pr, pr

    results = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for cid, txt, pr, card in ex.map(work, cases):
            results[cid] = {"raw": txt, "parsed": pr, "card": card}
            print(f"  {cid}: {(card or {}).get('verdict', 'PARSE_ERROR')}", flush=True)
    preds = [results[c["id"]]["card"] for c in cases]
    rep = score(cases, preds)
    rep["model"] = model; rep["mode"] = args.mode
    outdir = ROOT / "eval" / "results"; outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    (outdir / f"trackB-{args.mode}-{stamp}-raw.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "reports" / f"m0-trackB-{args.mode}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep["metrics"], ensure_ascii=False, indent=2))
    print("GATES:", json.dumps(rep["gates"], ensure_ascii=False), "PASS" if rep["pass"] else "FAIL")
    sys.exit(0 if rep["pass"] else 1)

if __name__ == "__main__":
    main()