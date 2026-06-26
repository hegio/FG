import os, re
def convert_to_m3u(src, dst):
    if not os.path.isfile(src):
        print(f"[WARN] {src} 不存在，跳过")
        return
    with open(src, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    out = ['#EXTM3U x-tvg-url=""']
    group = '未分类'
    cnt = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ',#genre#' in line:
            group = line.replace(',#genre#', '').strip()
            continue
        for proto in [',http://', ',https://', ',p2p://', ',rtmp://', ',rtsp://']:
            if proto in line:
                idx = line.find(proto)
                name = line[:idx].strip()
                url  = line[idx+1:].strip()
                name = re.sub(r'\s+', ' ', name)
                out.append(f'#EXTINF:-1 group-title="{group}",{name}')
                out.append(url)
                cnt += 1
                break
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f"[DONE] {src} → {dst} ({cnt} 条）")

convert_to_m3u("zilongTV", "zilongTV.m3u")
convert_to_m3u("海豚无18加555", "haitun.m3u")
