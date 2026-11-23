# -*- coding: utf-8 -*-
"""生成 jianlou-mini 评测集（30 例，五类配平）。运行: python build_cases.py"""
import json, pathlib

def A(kind, low, high, source, date):
    return {"kind": kind, "low": low, "high": high, "source": source, "date": date}

def item(title, cat, cond, dist, pickup="easy", acc=None, defects=None, war=0):
    return {"title": title, "category": cat, "condition": cond, "distance_km": dist,
            "pickup": pickup, "accessories_missing": acc or [], "defects": defects or [],
            "warranty_months_left": war}

def ask(price, ship=None, dep=None, off=False, acct=None, img=None, story=None, urgent=False):
    return {"price": price, "shipping_fee": ship, "deposit": dep, "offplatform_contact": off,
            "account_age_days": acct, "images_real": img, "story": story, "urgent_pressure": urgent}

def C(id, cat, gold, raw, it, ak, anchors):
    return {"id": id, "category": cat, "gold": gold, "raw_text": raw,
            "input": {"item": it, "ask": ak, "anchors": anchors}}

S = "闲鱼二手行情搜索"
D = "2026-11-20"
cases = [
# ---- 真漏 worth_go x6 ----
C("w1","true_bargain","worth_go","搬家带不走，宜家书桌免费送，几乎全新，滨江某小区自提，离我3公里，自己搬就行。账号注册500天，实拍图。",
  item("宜家书桌","家具","几乎全新",3), ask(0,acct=500,img=True), [A("used",150,250,S,D)]),
C("w2","true_bargain","worth_go","小米空气净化器2，50元出，轻微使用痕迹，滤芯刚换，同城自提2公里，实拍。",
  item("小米空气净化器2","家电","轻微使用痕迹",2), ask(50,acct=800,img=True), [A("used",200,300,S,D)]),
C("w3","true_bargain","worth_go","好孩子婴儿推车80元，几乎全新，宝宝大了用不上，5公里自提，需要SUV后备箱装，实拍图。",
  item("好孩子婴儿推车","母婴","几乎全新",5,"medium"), ask(80,acct=600,img=True), [A("used",300,450,S,D)]),
C("w4","true_bargain","worth_go","Kindle Paperwhite4 150元，轻微使用痕迹，屏幕完美，带原装线，同城1公里面交。",
  item("Kindle Paperwhite4","3c数码","轻微使用痕迹",1), ask(150,acct=900,img=True), [A("used",350,450,S,D)]),
C("w5","true_bargain","worth_go","实木餐椅两把免费送，明显使用痕迹但结实，5公里自提，轿车可装。",
  item("实木餐椅×2","家具","明显使用痕迹",5), ask(0,acct=400,img=True), [A("used",100,160,S,D)]),
C("w6","true_bargain","worth_go","戴森V8吸尘器300元，轻微使用痕迹，缺充电器（另配了通用充），2公里自提，实拍，账号500天。",
  item("戴森V8吸尘器","家电","轻微使用痕迹",2,acc=["充电器"]), ask(300,acct=500,img=True), [A("used",700,900,S,D)]),
# ---- 小漏 watch x5 ----
C("m1","modest","watch","美的电饭煲90元，轻微使用痕迹，内胆涂层完好，3公里自提。",
  item("美的电饭煲","家电","轻微使用痕迹",3), ask(90,acct=300,img=True), [A("used",120,160,S,D)]),
C("m2","modest","watch","办公椅120元，明显使用痕迹，网布完好，8公里自提，需面包车。",
  item("办公椅","家具","明显使用痕迹",8,"medium"), ask(120,acct=300,img=True), [A("used",250,350,S,D)]),
C("m3","modest","watch","Switch续航版900元，轻微使用痕迹，带底座和一对joycon，1公里面交。",
  item("Switch续航版","3c数码","轻微使用痕迹",1), ask(900,acct=700,img=True), [A("used",1300,1500,S,D)]),
C("m4","modest","watch","小天鹅洗衣机350元，明显使用痕迹，功能正常，12公里自提，要两个人抬。",
  item("小天鹅洗衣机","家电","明显使用痕迹",12,"hard"), ask(350,acct=450,img=True), [A("used",700,900,S,D)]),
C("m5","modest","watch","捷安特公路车780元，轻微使用痕迹，缺码表，2公里自提。",
  item("捷安特公路车","运动","轻微使用痕迹",2,acc=["码表"]), ask(780,acct=600,img=True), [A("used",1000,1300,S,D)]),
# ---- 无漏 pass x5 ----
C("p1","no_bargain","pass","iPhone13 128G 2200元，轻微使用痕迹，电池85%，1公里面交。",
  item("iPhone13 128G","3c数码","轻微使用痕迹",1), ask(2200,acct=800,img=True), [A("used",2400,2700,S,D)]),
C("p2","no_bargain","pass","旧布艺沙发免费送，明显使用痕迹，45公里外，要自己找车搬。",
  item("旧布艺沙发","家具","明显使用痕迹",45,"hard"), ask(0,acct=300,img=True), [A("used",150,250,S,D)]),
C("p3","no_bargain","pass","三体全集40元，几乎全新，同城自提3公里。",
  item("三体全集","图书","几乎全新",3), ask(40,acct=200,img=True), [A("used",40,60,S,D)]),
C("p4","no_bargain","pass","格力空调挂机800元，明显使用痕迹，5公里，拆机费已含，自己找车拉。",
  item("格力空调挂机","家电","明显使用痕迹",5,"hard"), ask(800,acct=500,img=True), [A("used",1200,1500,S,D)]),
C("p5","no_bargain","pass","AOC 27寸显示器520元，轻微使用痕迹，无坏点，2公里自提。",
  item("AOC 27寸显示器","3c数码","轻微使用痕迹",2), ask(520,acct=650,img=True), [A("used",550,700,S,D)]),
# ---- 骗局 avoid x5 ----
C("s1","scam","avoid","出国了iPhone15 Pro免费送！富二代盲盒清仓，手机平板都有，加微信进群抢，先到先得手慢无！",
  item("iPhone15 Pro","3c数码","几乎全新",2), ask(0,off=True,acct=10,img=True,story="富二代盲盒清仓",urgent=True), [A("used",5500,6500,S,D)]),
C("s2","scam","avoid","戴森吹风机50元急出！账号刚注册3天，图片是网图，详情加微信聊，平台不常上。",
  item("戴森吹风机","家电","几乎全新",3), ask(50,off=True,acct=3,img=False), [A("used",1500,2000,S,D)]),
C("s3","scam","avoid","MacBook Air M1 800元，海关扣押罚没物资，内部渠道处理，数量不多先款先得。",
  item("MacBook Air M1","3c数码","几乎全新",4), ask(800,acct=20,img=True,story="海关扣押罚没内部渠道"), [A("used",3500,4200,S,D)]),
C("s4","scam","avoid","RTX4070显卡100元秒杀！图是官方渲染图，新号，要的赶紧私信。",
  item("RTX4070显卡","3c数码","全新",1), ask(100,acct=2,img=False,urgent=True), [A("used",2800,3300,S,D)]),
C("s5","scam","avoid","黄金项链免费送，内部渠道抵债物资，先付200元定金留货，明天面交。",
  item("黄金项链","其他","全新",2), ask(0,dep=200,acct=15,img=True,story="内部渠道抵债"), [A("used",3000,4000,S,D)]),
# ---- 假免费 avoid x5 ----
C("f1","fake_free","avoid","儿童安全座椅免费送，几乎全新，就是到付邮费60元，偏远地区不发。",
  item("儿童安全座椅","母婴","几乎全新",0), ask(0,ship=60,acct=100,img=True), [A("used",150,250,S,D)]),
C("f2","fake_free","avoid","空气炸锅免费送，轻微使用痕迹，邮费到付35元，谢绝还价。",
  item("空气炸锅","家电","轻微使用痕迹",0), ask(0,ship=35,acct=80,img=True), [A("used",80,120,S,D)]),
C("f3","fake_free","avoid","品牌沙发免费送，好多人要，先付100元定金给你留着，周末自提。",
  item("品牌沙发","家具","几乎全新",6), ask(0,dep=100,acct=200,img=True), [A("used",300,500,S,D)]),
C("f4","fake_free","avoid","专柜名牌包免费送，支持验货，新号，加QQ详聊，微信满了。",
  item("名牌包","服饰","几乎全新",3), ask(0,off=True,acct=5,img=True), [A("used",1500,2500,S,D)]),
C("f5","fake_free","avoid","打印机免费送，轻微使用痕迹，到付邮费25元，墨盒还有墨。",
  item("打印机","3c数码","轻微使用痕迹",0), ask(0,ship=25,acct=150,img=True), [A("used",60,90,S,D)]),
# ---- 边界拒答 abstain x4 ----
C("a1","edge_abstain","abstain","老式组合音响一套免费送，不知道值多少，懂的来，5公里自提。",
  item("老式组合音响","其他","明显使用痕迹",5), ask(0,acct=300,img=True), []),
C("a2","edge_abstain","abstain","二手床垫免费拿，成色说不清，自己来看，2公里。",
  item("二手床垫","家具","未知",2), ask(0,acct=300,img=None), [A("used",100,200,S,D)]),
C("a3","edge_abstain","abstain","戴森吹风机300元，几乎全新。搜到个参考价1500-2000但没记来源和日期。",
  item("戴森吹风机","家电","几乎全新",2), ask(300,acct=400,img=True), [A("used",1500,2000,"","")]),
C("a4","edge_abstain","abstain","微单相机免费送，成色未知，功能不知道好不好，3公里自提。",
  item("微单相机","3c数码","未知",3), ask(0,acct=300,img=True), [A("used",1500,2500,S,D)]),
]

out = pathlib.Path(__file__).parent / "jianlou-mini.jsonl"
out.write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cases) + "\n", encoding="utf-8")
print(f"wrote {len(cases)} cases -> {out}")