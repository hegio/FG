import json

# 固定的 spider.jar 路径
SPIDER_PATH = "/storage/emulated/0/TvBox/spider.jar"

# 读取修正后的文件
with open('鱼壳海豚_修正.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 设置 spider 路径
data["spider"] = SPIDER_PATH

# 保存
with open('鱼壳海豚_修正.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"[DONE] 已设置 spider 路径为: {SPIDER_PATH}")
print(f"[INFO] 请确保将 spider.jar 文件放在该目录下")
