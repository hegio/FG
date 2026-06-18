import base64
import json
import re
import urllib.parse
import os

def parse_m3u_to_channels(filename, prefix=""):
    """解析 M3U 文件提取频道"""
    if not os.path.exists(filename):
        return []
    
    channels = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('#EXTINF:-1'):
                # 提取频道名
                name_match = re.search(r',(.*)$', line)
                if name_match:
                    name = name_match.group(1)
                    # 查找下一行 URL
                    next_line_index = i + 1
                    while next_line_index < len(lines):
                        next_line = lines[next_line_index].strip()
                        if next_line and not next_line.startswith('#'):
                            if next_line.startswith(('http', 'rtmp', 'rtsp', 'p2p')):
                                final_name = f"{prefix} {name}" if prefix else name
                                channels.append((final_name, next_line))
                            break
                        next_line_index += 1
    except Exception as e:
        print(f"Error parsing {filename}: {e}")
    
    return channels

def parse_vmess_link(link):
    """解析 vmess 链接"""
    try:
        b64_data = link[8:]
        b64_data += '=' * (4 - len(b64_data) % 4)
        json_str = base64.b64decode(b64_data).decode('utf-8')
        data = json.loads(json_str)
        server = data.get('add', '')
        port = data.get('port', 443)
        ps = data.get('ps', 'VMess')
        return f"{ps} | {server}:{port}"
    except:
        return None

def parse_subscription_file(filename):
    """解析订阅文件（Base64 或明文）"""
    if not os.path.exists(filename):
        return []
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    
    # 尝试 Base64 解码
    try:
        padding = 4 - len(content) % 4
        if padding != 4:
            content += '=' * padding
        decoded = base64.b64decode(content).decode('utf-8')
        lines = [l.strip() for l in decoded.split('\n') if l.strip()]
    except:
        lines = [l.strip() for l in content.split('\n') if l.strip()]
    
    channels = []
    for line in lines:
        if line.startswith('vmess://'):
            name = parse_vmess_link(line)
            if name:
                channels.append((name, line))
        elif line.startswith(('vless://', 'trojan://', 'ss://')):
            # 简化处理，提取域名
            try:
                if line.startswith('vless://'):
                    server = line.split('@')[1].split(':')[0]
                    name = f"VLESS | {server}"
                elif line.startswith('trojan://'):
                    server = line.split('@')[1].split(':')[0]
                    name = f"Trojan | {server}"
                elif line.startswith('ss://'):
                    name = f"Shadowsocks | {line.split('@')[1].split(':')[0]}"
                channels.append((name, line))
            except:
                continue
    
    return channels

def extract_lives_from_json(filename):
    """从 JSON 配置中提取 lives 列表"""
    if not os.path.exists(filename):
        return []
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        channels = []
        for live in data.get('lives', []):
            url = live.get('url', '')
            name = live.get('name', '')
            if url and name:
                channels.append((name, url))
        
        return channels
    except Exception as e:
        print(f"Error extracting lives from {filename}: {e}")
        return []

# 收集所有频道
all_channels = []

# 从 M3U 文件解析
m3u_files = [
    ("zilongTV", "🐬"),
    ("海豚无18加555", "🐬"),
]

for file_name, prefix in m3u_files:
    if os.path.exists(file_name):
        channels = parse_m3u_to_channels(file_name, prefix)
        all_channels.extend(channels)
        print(f"Parsed {len(channels)} channels from {file_name}")

# 从 JSON 配置提取直播源
json_files = ["海豚无18加555", "海豚666"]
for file_name in json_files:
    if os.path.exists(file_name):
        channels = extract_lives_from_json(file_name)
        all_channels.extend(channels)
        print(f"Extracted {len(channels)} live sources from {file_name}")

# 生成标准 M3U 文件
with open('FgPlayList.m3u', 'w', encoding='utf-8') as f:
    f.write('#EXTM3U\n')
    f.write('#EXTINF:-1 tvg-name="🐬海豚影视综合",🐬海豚影视综合\n')
    f.write('http://localhost/placeholder\n')
    
    # 写入所有频道
    for name, url in all_channels:
        # 清理名称中的特殊字符
        clean_name = re.sub(r'[|\\/*?:<>"]', '', name)
        f.write(f'#EXTINF:-1 tvg-name="{clean_name}",{clean_name}\n')
        f.write(f'{url}\n')

print(f"✓ Generated FgPlayList.m3u with {len(all_channels)} channels")
