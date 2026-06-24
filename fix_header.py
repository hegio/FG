import json, os

src = "鱼壳海豚"
dst = "鱼壳海豚_修正.json"

if not os.path.isfile(src):
    print(f"[WARN] {src} 不存在，跳过修正")
    exit(0)

# 读取原文件
with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 修正头部配置（参考海豚666.json）
# ⭐ 关键：明确指定 spider.jar 的绝对路径
data["spider"] = "/storage/emulated/0/TvBox/spider.jar"
data["wallpaper"] = "http://tool.teyonds.com/api"
data["logo"] = "https://img.freepik.com/free-vector/cute-dolphin-swimming-cartoon-vector-icon-illustration-animal-nature-icon-isolated-flat-vector_138676-12582.jpg?semt=ais_hybrid&w=740&q=80"

# 保存为修正版
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"[DONE] 已生成 {dst}")
print(f"[INFO] spider.jar 路径已设置为: /storage/emulated/0/TvBox/spider.jar")
