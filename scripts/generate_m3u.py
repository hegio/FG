import os
import re
import urllib.request
import concurrent.futures

target_names = [
    "🐬综合直播 海豚影视交流群 TG：@hshsjk9",
    "🐬风云源 海豚影视永久免费如有收费的都是骗子",
    "🐬各大源合集",
    "🐬Nettv",
    "🐬电视家",
    "🐬地方直播2",
    "🐬薄荷直播",
    "🐬咪咕直播",
    "🐬juli",
    "🐬国际TV",
    "🐬live",
    "🐬裤佬TV2",
    "🐬Mytv",
    "🐬易发源 有🔞",
    "🐬港奥台国际",
    "🐬中港台直播源",
    "🐬4GTV(梯子任何节点)1080p",
    "🐬4GTV(免梯子)1080p",
    "🐬jackTV(梯子)",
    "develop202",
]

USE_3_LEVEL_DIRECTORY = True
NSFW_KEYWORDS = ["18+", "🔞", "adult", "福利", "成人", "av", "xxx", "sex", "erotic", "午夜", "18a"]
PROBE_TIMEOUT = 5
PROBE_MAX_WORKERS = 30

def fetch_content(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"抓取失败 {url}: {e}")
        return ""

def probe_url(url, timeout=PROBE_TIMEOUT):
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                _ = resp.read(1024)
                return True
        except:
            return False

def clean_group_name(name):
    return name.replace(" 有🔞", "").replace("有🔞", "").strip()

def is_nsfw(text):
    return any(kw in text.lower() for kw in NSFW_KEYWORDS)

def parse_m3u(content, main_group):
    channels = []
    lines = content.splitlines()
    current_inf = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            current_inf = line
        elif not line.startswith("#"):
            if current_inf:
                sub_group = ""
                m = re.search(r'group-title="([^"]+)"', current_inf)
                if m:
                    sub_group = m.group(1).strip()
                name = "未知频道"
                idx = current_inf.rfind(',')
                if idx != -1:
                    name = current_inf[idx+1:].strip()
                if is_nsfw(name) or is_nsfw(sub_group):
                    current_inf = None
                    continue
                clean_main = clean_group_name(main_group)
                group_title = f"{clean_main} - {sub_group}" if (USE_3_LEVEL_DIRECTORY and sub_group) else clean_main
                channels.append({"name": name, "url": line, "group_title": group_title})
                current_inf = None
    return channels

def parse_txt(content, main_group):
    channels = []
    current_genre = ""
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if "#genre#" in line:
            current_genre = line.split(",")[0].strip()
            continue
        parts = re.split(r'[,#$]', line, 1)
        if len(parts) == 2:
            name, url = parts[0].strip(), parts[1].strip()
            if url.startswith(("http://", "https://", "rtmp://", "rtsp://", "p2p://", "mitv://")):
                if is_nsfw(name) or is_nsfw(current_genre):
                    continue
                clean_main = clean_group_name(main_group)
                group_title = f"{clean_main} - {current_genre}" if (USE_3_LEVEL_DIRECTORY and current_genre) else clean_main
                channels.append({"name": name, "url": url, "group_title": group_title})
    return channels

def parse_source(content, main_group):
    if "#EXTM3U" in content or "#EXTINF" in content:
        return parse_m3u(content, main_group)
    return parse_txt(content, main_group)

def main():
    all_channels = []
    lives_url = "https://raw.githubusercontent.com/hegio/FG/main/Lv/lives.txt"
    print("下载 lives.txt...")
    lives_content = fetch_content(lives_url)
    if lives_content:
        sources = {}
        for line in lives_content.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(",", 1)
                if len(parts) == 2:
                    sources[parts[0].strip()] = parts[1].strip()
        matched = {}
        for target in target_names:
            if target in sources:
                matched[target] = sources[target]
            else:
                for s_name, s_url in sources.items():
                    if target in s_name or s_name in target:
                        matched[target] = s_url
                        break
        for target in target_names:
            if target not in matched:
                print(f"未找到: {target}")
                continue
            url = matched[target]
            print(f"处理: {target}")
            content = fetch_content(url)
            if content:
                chs = parse_source(content, target)
                all_channels.extend(chs)
                print(f"  提取 {len(chs)} 个")

    extra = "extra_sources.txt"
    if os.path.exists(extra):
        with open(extra, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split(",", 1)
                    if len(parts) == 2:
                        name, url = parts[0].strip(), parts[1].strip()
                        content = fetch_content(url)
                        if content:
                            chs = parse_source(content, name)
                            all_channels.extend(chs)

    seen = set()
    unique = []
    for ch in all_channels:
        key = (ch['group_title'], ch['name'], ch['url'])
        if key not in seen:
            seen.add(key)
            unique.append(ch)

    print(f"去重后 {len(unique)} 个，开始探测...")
    alive = []
    dead = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=PROBE_MAX_WORKERS) as pool:
        futures = {pool.submit(probe_url, ch['url']): ch for ch in unique}
        for future in concurrent.futures.as_completed(futures):
            ch = futures[future]
            try:
                if future.result():
                    alive.append(ch)
                else:
                    dead += 1
                    print(f"  [DEAD] {ch['name']}")
            except Exception as e:
                dead += 1
                print(f"  [DEAD] {ch['name']} - {e}")

    print(f"存活 {len(alive)} 个，失效 {dead} 个")
    with open("鱼豚无18b.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in alive:
            f.write(f'#EXTINF:-1 tvg-name="{ch["name"]}" group-title="{ch["group_title"]}",{ch["name"]}\n')
            f.write(f"{ch['url']}\n")
    print("完成")

if __name__ == "__main__":
    main()
