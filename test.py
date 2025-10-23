import sys, json
p = r"D:\实验室\数据集\代码\ScenarioChat-main\backgrounds.json"  # 换成你的 --data 路径
try:
    print("Try strict json.load ...")
    with open(p, "r", encoding="utf-8") as f:
        json.load(f)
    print("OK: JSON valid")
except Exception as e:
    print("ERROR:", e)
    with open(p, "r", encoding="utf-8") as f:
        s = f.read()
    pos = 423414  # 你日志里的 char 偏移（char 423414）
    start = max(0, pos-200)
    end   = min(len(s), pos+200)
    print("Context around error:\n", s[start:end])
