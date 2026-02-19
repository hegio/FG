import os
import re

def convert_file(input_file, output_file):
    """将简易格式转换为标准M3U格式"""
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
        
        # 跳过 YouTube 链接
        if 'youtube.com' in line or 'youtu.be' in line:
            continue
        
        # 处理 "名称,URL" 格式（支持 http/https/p2p/rtmp/rtsp）
        for protocol in [',http://', ',https://', ',p2p://', ',rtmp://', ',rtsp://']:
            if protocol in line:
                idx = line.find(protocol)
                name = line[:idx].strip()
                url = line[idx+1:].strip()
                
                # 清理名称
                name = re.sub(r'\s+', ' ', name)
                
                output.append(f'#EXTINF:-1 group-title="{current_group}",{name}')
                output.append(url)
                count += 1
                break
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output))
    
    print(f"✓ Converted {input_file} -> {output_file} ({count} channels)")
    return True

# 转换两个文件
# 方案A：分别生成独立的m3u文件（推荐，便于管理）
convert_file("港台大陆", "playlist.m3u")
convert_file("安博", "anbo.m3u")  # 安博专用文件

# 方案B：合并为一个文件（如需合并，取消下面注释）
# convert_file("港台大陆", "temp1.m3u")
# convert_file("安博", "temp2.m3u")
# os.system("cat temp1.m3u temp2.m3u | grep -v '^#EXTM3U' > combined.m3u")
# os.system("echo '#EXTM3U x-tvg-url=\\\"\\\"' | cat - combined.m3u > playlist.m3u && rm combined.m3u temp1.m3u temp2.m3u")

print("Conversion completed")
