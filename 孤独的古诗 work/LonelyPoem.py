# 代码 6A  LonelyPoem.py
# 微实例 6A：孤独的古诗词

s = "众鸟高飞尽，孤云独去闲。相看两不厌，只有敬亭山。"
s = s.replace("，", "").replace("。", "")
if len(s) == len(set(s)):
    print(True)
else:
    print(False)
