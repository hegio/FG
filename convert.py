import os
import re

def convert_to_m3u(input_file, output_file):
    """将简易格式转换为标准M3U格式（保留YouTube链接）"""
    if not os.path.exists(input_file):
        print(f"⚠️  {input_file} not found, skipping")
        return False
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except UnicodeDecodeError:
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
        
        # 【重要】取消 YouTube 链接过滤，保留所有链接
        # 处理 "名称,URL" 格式
        for protocol in [',http://', ',https://', ',p2p://', ',rtmp://', ',rtsp://']:
            if protocol in line:
                idx = line.find(protocol)
                name = line[:idx].strip()
                url = line[idx+1:].strip()
                
                # 清理名称中的多余空格
                name = re.sub(r'\s+', ' ', name)
                
                output.append(f'#EXTINF:-1 group-title="{current_group}",{name}')
                output.append(url)
                count += 1
                break
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"✓ Converted {input_file} -> {output_file} ({count} channels, 保留YouTube链接)")
    return True

# 只转换直播源文件
convert_to_m3u("港台大陆", "playlist.m3u")
convert_to_m3u("安博", "anbo.m3u")

# TVBox配置文件保持原样，不转换
print("✓ 海马影视 和 锋哥影视json 保持原样（TVBox配置）")
