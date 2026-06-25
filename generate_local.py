import json
import os

src = "鱼壳海豚"
dst = "鱼壳海豚_local.json"

if not os.path.isfile(src):
    print(f"[WARN] {src} 不存在，跳过生成 local 版本")
    exit(0)

with open(src, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Termux HTTP 服务器地址（端口 8080，与 WebHTV 9978 不冲突）
data["spider"] = "http://192.168.123.90:8080/spider.jar"
data["wallpaper"] = "http://tool.teyonds.com/api"
data["logo"] = "https://img.freepik.com/free-vector/cute-dolphin-swimming-cartoon-vector-icon-illustration-animal-nature-icon-isolated-flat-vector_138676-12582.jpg?semt=ais_hybrid&w=740&q=80"

with open(dst, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print(f"[DONE] 已生成 {dst}")
print(f"[INFO] spider 路径: http://192.168.123.90:8080/spider.jar")
print(f"[INFO] 请确保 Termux 中已运行: cd ~ && python -m http.server 8080")
