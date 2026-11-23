# -*- coding: utf-8 -*-
"""引擎单测：红旗 / 估值 / 拒答 / 边界。运行: python -m pytest tests/ -q"""
import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "skill" / "scripts"))
from jianlou import evaluate, fair_value, value_hint, valid_anchors  # noqa: E402

BASE = {
    "item": {"title": "宜家书桌", "category": "家具", "condition": "几乎全新",
             "distance_km": 3, "pickup": "easy", "accessories_missing": [],
             "defects": [], "warranty_months_left": 0},
    "ask": {"price": 0, "shipping_fee": None, "deposit": None,
            "offplatform_contact": False, "account_age_days": 500,
            "images_real": True, "story": None, "urgent_pressure": False},
    "anchors": [{"kind": "used", "low": 150, "high": 250, "source": "s", "date": "2026-11-20"}],
}


def _mut(**ask):
    c = copy.deepcopy(BASE)
    c["ask"].update(ask)
    return c


def test_free_local_worth_go():
    assert evaluate(BASE)["verdict"] == "worth_go"


def test_no_anchor_abstain():
    c = copy.deepcopy(BASE); c["anchors"] = []
    assert evaluate(c)["verdict"] == "abstain"


def test_anchor_without_source_invalid():
    c = copy.deepcopy(BASE); c["anchors"][0]["source"] = ""
    assert evaluate(c)["verdict"] == "abstain"
    assert valid_anchors(c["anchors"]) == []


def test_unknown_condition_abstain():
    c = copy.deepcopy(BASE); c["item"]["condition"] = "未知"
    assert evaluate(c)["verdict"] == "abstain"


def test_deposit_hard_flag():
    card = evaluate(_mut(deposit=100))
    assert card["verdict"] == "avoid"
    assert any(f["id"] == "RF_DEPOSIT" for f in card["flags"])


def test_shipping_scam():
    card = evaluate(_mut(price=0, shipping_fee=60))
    assert card["verdict"] == "avoid"
    assert any(f["id"] == "RF_SHIPPING" for f in card["flags"])


def test_reasonable_shipping_not_flagged():
    # 邮费 10 元低于阈值，不构成邮费盘
    card = evaluate(_mut(price=0, shipping_fee=10))
    assert not any(f["id"] == "RF_SHIPPING" for f in card["flags"])


def test_offplatform_high_value():
    c = _mut(offplatform_contact=True)
    c["anchors"] = [{"kind": "used", "low": 1500, "high": 2500, "source": "s", "date": "d"}]
    card = evaluate(c)
    assert card["verdict"] == "avoid"


def test_offplatform_low_value_soft_only():
    # 低价值物品脱离平台只是软红旗，不直接判死
    card = evaluate(_mut(offplatform_contact=True))
    assert card["verdict"] != "avoid"
    assert any(f["id"] == "SF_OFFPLATFORM_LOW" for f in card["flags"])


def test_offplatform_unknown_condition_still_flagged():
    # value_hint 修复：成色未知时高价值引流盘仍须判 avoid
    c = _mut(offplatform_contact=True)
    c["item"]["condition"] = "未知"
    c["anchors"] = [{"kind": "used", "low": 1500, "high": 2500, "source": "s", "date": "d"}]
    assert evaluate(c)["verdict"] == "avoid"


def test_story_keyword():
    card = evaluate(_mut(story="海关扣押罚没物资"))
    assert card["verdict"] == "avoid"


def test_fake_images():
    assert evaluate(_mut(images_real=False))["verdict"] == "avoid"


def test_too_good_requires_combo():
    # 真免费高价值（无其他风险信号）不触发 RF_TOO_GOOD
    c = copy.deepcopy(BASE)
    c["anchors"] = [{"kind": "used", "low": 1500, "high": 2500, "source": "s", "date": "d"}]
    c["item"]["condition"] = "几乎全新"
    card = evaluate(c)
    assert not any(f["id"] == "RF_TOO_GOOD" for f in card["flags"])
    assert card["verdict"] == "worth_go"
    # 叠加新号后触发
    c["ask"]["account_age_days"] = 3
    assert evaluate(c)["verdict"] == "avoid"


def test_normal_price_pass():
    assert evaluate(_mut(price=190))["verdict"] == "pass"


def test_modest_watch():
    assert evaluate(_mut(price=160))["verdict"] == "watch"


def test_distance_kills_free_sofa():
    c = copy.deepcopy(BASE)
    c["item"].update(condition="明显使用痕迹", distance_km=45, pickup="hard")
    c["anchors"] = [{"kind": "used", "low": 150, "high": 250, "source": "s", "date": "d"}]
    assert evaluate(c)["verdict"] == "pass"


def test_condition_and_accessory_math():
    c = copy.deepcopy(BASE)
    c["item"].update(condition="轻微使用痕迹", accessories_missing=["充电器"])
    fair, _ = fair_value(c["item"], c["anchors"])
    assert abs(fair - 200 * 0.85 * 0.97) < 0.01


def test_value_hint_independent_of_condition():
    assert value_hint(BASE["anchors"]) == 200.0
    assert value_hint([]) is None


def test_new_anchor_discount():
    c = copy.deepcopy(BASE)
    c["anchors"] = [{"kind": "new", "low": 1000, "high": 1000, "source": "s", "date": "d"}]
    assert value_hint(c["anchors"]) == 600.0