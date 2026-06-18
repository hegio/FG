#!/usr/bin/env python3
import os, json, base64, re, urllib.parse

# --------------------------------------------------------------
# 1️⃣ 解析普通 M3U（如 zilongTV、海豚无18加555）
# --------------------------------------------------------------
def parse_m3u(file_path, prefix=""):
    if not os.path.isfile(file_path):
        return []
    channels = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF:-1'):
            # 取名称
            name_match = re.search(r',(.*)$', line)
            name = name_match.group(1).strip() if name_match else "未知"
            # 下一行应为 URL
            j = i + 1
            while j < len(lines):
                nxt = lines[j].strip()
                if nxt and not nxt.startswith('#'):
                    if nxt.startswith(('http','rtmp','rtsp','p2p')):
                        full_name = f"{prefix} {name}" if prefix else name
                        channels.append((full_name, nxt))
                    break
                j += 1
        i += 1
    return channels

# --------------------------------------------------------------
# 2️⃣ 解析 GHK / 鱼壳海豚 JSON（结构统一为 {"lives":[{...}]})
# --------------------------------------------------------------
def extract_from_json(file_path):
    if not os.path.isfile(file_path):
        return []
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 兼容可能的字段名：url / link / stream
    result = []
    for item in data.get('lives', []):
        url = item.get('url') or item.get('link') or item.get('stream')
        name = item.get('name') or item.get('title') or '未知'
        if url:
            result.append((name, url))
    return result

# --------------------------------------------------------------
# 3️⃣ 收集全部频道
# --------------------------------------------------------------
all_channels = []

# ① M3U 文件
m3u_sources = [
    ("zilongTV", "🐬"),
    ("海豚无18加555", "🐬"),
]
for fname, prefix in m3u_sources:
    if os.path.isfile(fname):
        ch = parse_m3u(fname, prefix)
        all_channels.extend(ch)
        print(f"[INFO] {fname}: 解析到 {len(ch)} 条频道")

# ② JSON（海豚666、鱼壳海豚）
json_sources = ["海豚666", "鱼壳海豚"]
for fname in json_sources:
    if os.path.isfile(fname):
        ch = extract_from_json(fname)
        all_channels.extend(ch)
        print(f"[INFO] {fname}: 解析到 {len(ch)} 条直播源")

# --------------------------------------------------------------
# 4️⃣ 写入符合 EVILANGEL.m3u 格式的文件
# --------------------------------------------------------------
out_path = "FgPlayList.m3u"
with open(out_path, "w", encoding="utf-8") as out:
    out.write("#EXTM3U\n")
    # 这里自定义一个总的 “海豚综合” 项（随意，可自行修改）
    out.write('#EXTINF:-1 tvg-name="🐬海豚影视综合",🐬海豚影视综合\n')
    out.write("http://127.0.0.1/placeholder\n")
    
    for name, url in all_channels:
        # 清理名称中可能的非法字符（| \ / * ? : < > "）
        clean_name = re.sub(r'[|\\/*?:<>"]', '', name)
        out.write(f'#EXTINF:-1 tvg-name="{clean_name}",{clean_name}\n')
        out.write(f'{url}\n')

print(f"[DONE] 生成 {out_path}，共计 {len(all_channels)} 条频道")
