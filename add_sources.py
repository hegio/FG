import json
import sys

def add_live_sources():
    try:
        with open('海豚影视', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading 海豚影视: {e}")
        return False

    # 定义要添加的外部直播源（格式：名称, URL）
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

    # 获取现有名称列表，避免重复添加
    existing_names = {item.get('name', '') for item in data.get('lives', [])}
    
    added_count = 0
    for source in new_sources:
        if source['name'] not in existing_names:
            data['lives'].append(source)
            print(f"✓ Added: {source['name']}")
            added_count += 1
        else:
            print(f"⚠️  Already exists: {source['name']}")

    if added_count > 0:
        # 保存回文件（保持格式美观）
        with open('海豚影视', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"✓ Total {added_count} new sources added to 海豚影视")
        return True
    else:
        print("No new sources to add")
        return False

if __name__ == "__main__":
    success = add_live_sources()
    sys.exit(0 if success else 0)  # 即使没新增也不报错
