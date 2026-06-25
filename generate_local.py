import json
import os   # ← 新增这一行

src = "鱼壳海豚"
dst = "鱼壳海豚_local.json"

if not os.path.isfile(src):
    print(f"[WARN] {src} 不存在，跳过生成 local 版本")
    exit(0)

with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 设置本地 spider.jar 路径
data["spider"] = "/storage/emulated/0/TvBox/spider.jar"
data["wallpaper"] = "http://tool.teyonds.com/api"
data["logo"] = "https://img.freepik.com/free-vector/cute-dolphin-swimming-cartoon-vector-icon-illustration-animal-nature-icon-isolated-flat-vector_138676-12582.jpg?semt=ais_hybrid&w=740&q=80"

with open(dst, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"[DONE] 已生成 {dst}（本地挂载）")
print(f"[INFO] spider 路径: /storage/emulated/0/TvBox/spider.jar")
