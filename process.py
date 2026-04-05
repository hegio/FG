import os
import re
import shutil

def convert_to_m3u(input_file, output_file):
    """将简易格式（名称,URL）转换为标准M3U格式"""
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
    
    print(f"✓ Converted {input_file} -> {output_file} ({count} channels)")
    return True

def copy_if_m3u8(input_file, output_file):
    """如果是标准M3U8文件，直接复制并重命名"""
    if not os.path.exists(input_file):
        print(f"⚠️  {input_file} not found")
        return False
    
    # 检查是否是标准M3U8
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        first_line = f.readline()
    
    if first_line.strip().startswith('#EXTM3U'):
        shutil.copy(input_file, output_file)
        print(f"✓ Copied M3U8 {input_file} -> {output_file}")
        return True
    else:
        # 如果不是标准M3U8，尝试转换
        print(f"ℹ️  {input_file} not standard M3U8, trying conversion...")
        return convert_to_m3u(input_file, output_file)

# 1. 转换简易格式直播源（名称,URL 格式）
convert_to_m3u("海豚影视无18加", "haitun.m3u")

# 2. 处理标准M3U8格式（直接复制为 .m3u）
copy_if_m3u8("zilong大陆TV", "zilong大陆TV.m3u")

# 处理 zilongTV（如果存在）
if os.path.exists("zilongTV"):
    copy_if_m3u8("zilongTV", "zilongTV.m3u")

# 3. 以下文件保持原样（不转换）：
# - 海豚影视 (TVBox JSON配置)
# - 锋哥影视json (TVBox JSON配置)  
# - 海角黄色 (节点订阅文件，供v2rayN等使用)
print("✓ 保持原样的文件：海豚影视, 锋哥影视json, 海角黄色")
