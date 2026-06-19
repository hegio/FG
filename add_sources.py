import json, sys

def add_live_sources():
    try:
        with open('海豚影视', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 读取 海豚影视 失败: {e}")
        return False

    new_sources = [
        {
            "name": "🐬海角黄色",
            "type": 0,
            "ua": "okhttp",
            "url": "https://ghfast.top/https://raw.githubusercontent.com/FGBLH/fgrjk2/main/haijiao669"
        },
        {
            "name": "🐬zilong大陆TV",
            "type": 0,
            "ua": "okhttp",
            "url": "https://ghfast.top/https://raw.githubusercontent.com/zilong7728/Collect-IPTV/main/best_sorted.m3u8"
        }
    ]

    existed = {i.get('name', '') for i in data.get('lives', [])}
    added = 0
    for src in new_sources:
        if src['name'] not in existed:
            data.setdefault('lives', []).append(src)
            print(f"[INFO] Added {src['name']}")
            added += 1
        else:
            print(f"[WARN] 已存在 {src['name']}")

    if added:
        with open('海豚影视', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"[INFO] 共新增 {added} 条直播源")
        return True
    return False

if __name__ == '__main__':
    sys.exit(0 if add_live_sources() else 0)
