# -*- coding: utf-8 -*-
"""生成 cctv_links.json:把(中文队A, 中文队B, 央视集锦URL)按 sorted 队名做 key。
key 用 Python sorted,与 build.py 查映射时的 sorted 规则一致,保证匹配。
数据来自 WebSearch 抓 sports.cctv.com「[世界杯]X组第N轮:…集锦」直链(人工核对非前瞻/阵容/赛后点评)。
维护:每轮赛后把新场的(队A,队B,url)追加到 ROWS,重跑本脚本即可。"""
import json, os

ROWS = [
    # A 组
    ("韩国", "捷克", "https://sports.cctv.com/2026/06/12/VIDENMU1qFc9S2oqIuyD3NAr260612.shtml"),
    ("墨西哥", "南非", "https://sports.cctv.com/2026/06/12/VIDEReng9vZ2YXWjyM8tOFKd260612.shtml"),
    ("墨西哥", "韩国", "https://sports.cctv.com/2026/06/19/VIDE19UP3LHNo3r6cyIKWvjk260619.shtml"),
    ("捷克", "南非", "https://sports.cctv.com/2026/06/19/VIDEodvtiFakLrJv3C1UgziD260619.shtml"),
    # B 组
    ("加拿大", "波黑", "https://sports.cctv.com/2026/06/13/VIDE2QfoimONhWtZSisth4tV260613.shtml"),
    ("卡塔尔", "瑞士", "https://sports.cctv.com/2026/06/14/VIDEMU2AXMe3v6QqUkpeMiGc260614.shtml"),
    ("加拿大", "卡塔尔", "https://sports.cctv.com/2026/06/19/VIDEt9WIeYbSFRY4WxMrBGDd260619.shtml"),
    ("瑞士", "波黑", "https://sports.cctv.com/2026/06/19/VIDEDusfm4mPA7vPcGqAYzDt260619.shtml"),
    ("波黑", "卡塔尔", "https://sports.cctv.com/2026/06/25/VIDEj9V3KUdbfwZ1ErA7Jtfc260625.shtml"),
    # C 组
    ("巴西", "摩洛哥", "https://sports.cctv.com/2026/06/14/VIDEpaNcrbDOOqpTJWgE7b2I260614.shtml"),
    ("巴西", "海地", "https://sports.cctv.com/2026/06/20/VIDEC0svK4fzorP1v6Q89tcb260620.shtml"),
    ("苏格兰", "摩洛哥", "https://sports.cctv.com/2026/06/20/VIDEyZrPI0ToHcdCqN9bX7lq260620.shtml"),
    ("苏格兰", "巴西", "https://sports.cctv.com/2026/06/25/VIDEF4PWGrVAclVVjSNAK4YV260625.shtml"),
    # D 组
    ("美国", "巴拉圭", "https://sports.cctv.com/2026/06/13/VIDEueLG2GVQNkiqn3ZHKjBh260613.shtml"),
    ("美国", "澳大利亚", "https://sports.cctv.com/2026/06/20/VIDEYoS9gKoh0SSo8XsbHvhH260620.shtml"),
    ("土耳其", "巴拉圭", "https://sports.cctv.com/2026/06/20/VIDEEt9vtd6jSkVXq403enBu260620.shtml"),
    # E 组
    ("德国", "库拉索", "https://sports.cctv.com/2026/06/15/VIDECzWXUAYZtcZbk9ffWLiq260615.shtml"),
    ("科特迪瓦", "厄瓜多尔", "https://sports.cctv.com/2026/06/15/VIDEN4FUvh7Hs1E6kdkXMqhI260615.shtml"),
    ("德国", "科特迪瓦", "https://sports.cctv.com/2026/06/21/VIDEhGkZasMiqaXTZ4PM5N31260621.shtml"),
    ("厄瓜多尔", "库拉索", "https://sports.cctv.com/2026/06/21/VIDEtb5fkpcMLFT4pJ4dTBt4260621.shtml"),
    # F 组
    ("荷兰", "日本", "https://sports.cctv.com/2026/06/15/VIDEcUZxccnoP1SvlbSgcUkb260615.shtml"),
    ("瑞典", "突尼斯", "https://sports.cctv.com/2026/06/15/VIDEUmNTvrVQoEu0bq6FJg47260615.shtml"),
    ("荷兰", "瑞典", "https://sports.cctv.com/2026/06/21/VIDEVGxQLzyCM8z0XdxK65Mr260621.shtml"),
    ("突尼斯", "日本", "https://sports.cctv.com/2026/06/21/VIDExS1VnyYCZiyLDArjiW8o260621.shtml"),
    # G 组
    ("比利时", "埃及", "https://sports.cctv.com/2026/06/16/VIDEhtuWbEo2Ujdc0hOGmcn6260616.shtml"),
    ("伊朗", "新西兰", "https://sports.cctv.com/2026/06/16/VIDEqtHOxjTNc7hKnj7WN6fM260616.shtml"),
    ("比利时", "伊朗", "https://sports.cctv.com/2026/06/22/VIDEs1UMxfySL5gjSqaOxvpV260622.shtml"),
    ("新西兰", "埃及", "https://sports.cctv.com/2026/06/22/VIDEAm0NpGbVvjXJHZ4PiPvu260622.shtml"),
    # H 组
    ("西班牙", "佛得角", "https://sports.cctv.com/2026/06/16/VIDEIDrfhNRF1MOOOJjs2RqU260616.shtml"),
    ("沙特阿拉伯", "乌拉圭", "https://sports.cctv.com/2026/06/16/VIDExuDUwXEDCrgrl79eDBV0260616.shtml"),
    ("西班牙", "沙特阿拉伯", "https://sports.cctv.com/2026/06/22/VIDEYQTTyM56yYSUrsV52cIH260622.shtml"),
    ("乌拉圭", "佛得角", "https://sports.cctv.com/2026/06/22/VIDEvjyeqpBRJNpqqw70d0T9260622.shtml"),
    # I 组
    ("法国", "塞内加尔", "https://sports.cctv.com/2026/06/17/VIDE7lTPsAs28n64VVchZUxe260617.shtml"),
    ("伊拉克", "挪威", "https://sports.cctv.com/2026/06/17/VIDECN5sP9QHWZ6GioarjPKI260617.shtml"),
    ("法国", "伊拉克", "https://sports.cctv.com/2026/06/23/VIDEj8fWQkAG7xHuUemcrP2s260623.shtml"),
    ("挪威", "塞内加尔", "https://sports.cctv.com/2026/06/23/VIDEI6nI8dfdW3y9HdlpB3T1260623.shtml"),
    # J 组
    ("阿根廷", "阿尔及利亚", "https://sports.cctv.com/2026/06/17/VIDEaUYCRpDCf4CeWXMPEEMF260617.shtml"),
    ("奥地利", "约旦", "https://sports.cctv.com/2026/06/17/VIDE1q84c5HegaBA27FNtDUl260617.shtml"),
    ("阿根廷", "奥地利", "https://sports.cctv.com/2026/06/23/VIDE3FIWibbohwASRMUAnNzV260623.shtml"),
    ("约旦", "阿尔及利亚", "https://sports.cctv.com/2026/06/23/VIDEqHHAx4GoQH6bo5Be2pWx260623.shtml"),
    # K 组
    ("葡萄牙", "刚果(金)", "https://sports.cctv.com/2026/06/18/VIDE6Vm2SJsk8Lt15O50C8e7260618.shtml"),
    ("乌兹别克斯坦", "哥伦比亚", "https://sports.cctv.com/2026/06/18/VIDExioP6t8FSsmbn3NYXgsS260618.shtml"),
    ("葡萄牙", "乌兹别克斯坦", "https://sports.cctv.com/2026/06/24/VIDEEBXEr1YvCXNLIAm5vEGf260624.shtml"),
    ("哥伦比亚", "刚果(金)", "https://sports.cctv.com/2026/06/24/VIDE3bIsW2u7F84ELnwzcyDH260624.shtml"),
    # L 组
    ("英格兰", "克罗地亚", "https://sports.cctv.com/2026/06/18/VIDEK9H9VtAhL3iFoOYWEMgw260618.shtml"),
    ("加纳", "巴拿马", "https://sports.cctv.com/2026/06/18/VIDEkfeHoGq8qgYZ1JLkR0uu260618.shtml"),
    ("英格兰", "加纳", "https://sports.cctv.com/2026/06/24/VIDE2e9onIzygusdR9qMBvXB260624.shtml"),
    ("巴拿马", "克罗地亚", "https://sports.cctv.com/2026/06/24/VIDEFdZ5EUIB6ZDJCXFWTsvE260624.shtml"),
    # C 组补(06-25)
    ("摩洛哥", "海地", "https://sports.cctv.com/2026/06/25/VIDE9J1E6Yz7Hdyzgu648uq7260625.shtml"),
    # 央视无标准"集锦"标题页、用整场回顾视频替代的(标题为"力克/小胜"等,仍是 [世界杯] 该场视频)
    ("澳大利亚", "土耳其", "https://sports.cctv.com/2026/06/14/VIDEPqw4902JL00BxqBqhNhQ260614.shtml"),
    ("苏格兰", "海地", "https://sports.cctv.com/2026/06/14/VIDEijmmmWtnwLJ8xbEov8WW260614.shtml"),
]

d = {}
for a, b, u in ROWS:
    d["|".join(sorted([a, b]))] = u

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cctv_links.json")
with open(out, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
print("wrote", len(d), "links ->", out)
