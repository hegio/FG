import re

input_file = '港台大陆'
output_file = 'playlist.m3u'

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
except UnicodeDecodeError:
    # 如果 UTF-8 失败，尝试其他编码
    with open(input_file, 'r', encoding='gbk') as f:
        lines = f.readlines()

output = ['#EXTM3U x-tvg-url=""']
current_group = '未分类'
count = 0

for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # 检测分组标记 (,#genre#)
    if ',#genre#' in line:
        current_group = line.replace(',#genre#', '').strip()
        continue
    
    # 跳过 YouTube 链接（IPTV 软件不支持）
    if 'youtube.com' in line or 'youtu.be' in line:
        continue
    
    # 处理 "名称,URL" 格式
    # 注意：URL 中可能包含逗号，所以要找到第一个 http 位置
    if ',http' in line or ',p2p://' in line or ',rtmp://' in line or ',rtsp://' in line:
        # 找到协议开始的位置
        for protocol in ['http://', 'https://', 'p2p://', 'rtmp://', 'rtsp://']:
            if protocol in line:
                idx = line.find(',' + protocol)
                if idx != -1:
                    name = line[:idx].strip()
                    url = line[idx+1:].strip()
                    
                    # 清理名称中的多余空格
                    name = re.sub(r'\s+', ' ', name)
                    
                    # 写入标准 M3U 格式
                    output.append(f'#EXTINF:-1 group-title="{current_group}",{name}')
                    output.append(url)
                    count += 1
                    break

with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(output))

print(f"Converted {count} channels to M3U format")
print(f"First 20 lines of output:")
for line in output[:20]:
    print(line)
