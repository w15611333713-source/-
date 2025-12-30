import os
import re
import json
import time
import requests
import fitz  # pymupdf

# ==================== 配置区域 ====================
API_KEY = "sk-i3juhegqbmDqOirXvyRKZHH7bzlyowe265ay0LL99hoJW2uB"
# 使用 8k 模型通常够用了（省钱），如果论文特别长报错，可以改回 32k
MODEL_NAME = "moonshot-v1-8k"
BASE_URL = "https://api.moonshot.cn/v1/chat/completions"
TARGET_FOLDER = r"C:\Users\27666\Desktop\多传感融合定位11.28文献"


# =================================================

def get_pdf_content_efficient(filepath):
    """
    【省钱读取策略】
    只读 前3页 (找标题/年份/国家) + 后2页 (找参考文献年份/页脚)
    """
    try:
        doc = fitz.open(filepath)
        total_pages = len(doc)
        text = ""

        # 页面索引：去重排序
        indices = list(range(min(3, total_pages))) + list(range(max(0, total_pages - 2), total_pages))
        indices = sorted(list(set(indices)))

        for i in indices:
            text += doc[i].get_text()

        # 顺便获取元数据里的年份，作为“硬参考”
        meta_year = "Unknown"
        if doc.metadata.get('creationDate'):
            match = re.search(r'20\d{2}', doc.metadata['creationDate'])
            if match:
                meta_year = match.group()

        doc.close()
        return text[:15000], meta_year  # 限制长度
    except Exception:
        return "", "Unknown"


def extract_year_by_regex(text):
    """
    【Python 硬逻辑】用正则暴力找年份，防止AI看花眼
    """
    # 匹配常见版权格式: © 2015, published 2023, 2021 Elsevier
    matches = re.findall(r'(?:©|published|copyright|received|accepted).*?(20\d{2})', text, re.IGNORECASE)

    if matches:
        # 统计出现频率最高的年份
        from collections import Counter
        # 过滤掉未来的年份 (比如2030)
        valid_years = [y for y in matches if int(y) <= 2025]
        if valid_years:
            return Counter(valid_years).most_common(1)[0][0]

    # 兜底：找文中所有的 20xx
    all_years = re.findall(r'(20[0-2]\d)', text)
    if all_years:
        # 取第一页出现的年份，通常比较靠谱
        return all_years[0]

    return "Unknown"


def ask_kimi_simple(text, hint_year):
    """
    普通对话模式（不联网），省钱
    """
    prompt = f"""
    【任务】：从论文文本中提取：标题、年份、第一作者国家。

    【已知线索】：
    - Python代码检测到的年份可能是：{hint_year} (仅供参考，请你核对)

    【要求】：
    1. **标题 (Title)**：提取完整英文标题，去换行，保持原样，不要简写。
    2. **年份 (Year)**：
       - 优先寻找 "Published: 20xx" 或 "© 20xx"。
       - 如果 Python 检测的年份合理，就用它；如果不合理（比如检测到 2026），请修正。
    3. **国家 (Country)**：第一作者单位的国家 (中文)。
    4. **IF**: 既然不联网，就根据你的知识库估算一个大致数值，如果不确定直接填 "0.0"。

    【输出格式】：
    必须返回 JSON：
    {{
        "year": "2023",
        "country": "中国",
        "title": "Full Title Here",
        "if_val": "0.0"
    }}

    文本片段：
    {text}
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个输出JSON的学术助手。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1  # 低温保真
    }

    try:
        resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=60)
        data = resp.json()
        if "error" in data:
            print(f"  [API Error] {data['error']['message']}")
            return None
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"  [请求失败] {e}")
        return None


def extract_json(text):
    try:
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            return json.loads(match.group())
    except:
        pass
    return None


def clean_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.replace('\n', ' ').strip()
    if len(name) > 180: name = name[:180]
    return name


def main():
    if not os.path.exists(TARGET_FOLDER):
        print("文件夹不存在")
        return

    print(f"--- 启动省钱精准版 (Python硬核年份 + AI识别标题) ---")
    files = [f for f in os.listdir(TARGET_FOLDER) if f.lower().endswith('.pdf')]

    for filename in files:
        old_path = os.path.join(TARGET_FOLDER, filename)

        # 简单跳过已处理
        if re.match(r'^\d{4}_[\d\.]+_', filename):
            continue

        print(f"\n📄 分析: {filename}")

        # 1. 读取文本 & Python 猜年份
        text, meta_year = get_pdf_content_efficient(old_path)
        if not text: continue

        # 用正则再猜一次年份
        regex_year = extract_year_by_regex(text)

        # 决定给 AI 的提示年份 (正则优先，元数据其次)
        hint_year = regex_year if regex_year != "Unknown" else meta_year

        # 2. AI 识别
        print(f"    (Python预判年份: {hint_year}) -> 发送给 AI...", end="", flush=True)
        response = ask_kimi_simple(text, hint_year)
        print(" 完成")

        if not response: continue

        # 3. 解析
        data = extract_json(response)
        if not data:
            print(f"    [X] 格式错误: {response[:50]}...")
            continue

        final_year = str(data.get("year", hint_year))  # 如果AI没找到，就用Python猜的
        country = str(data.get("country", "未知"))
        title = str(data.get("title", "Unknown Title"))
        if_val = str(data.get("if_val", "0.0"))

        # 4. 双重校验年份 (防止 AI 还是犯傻)
        # 如果 Python 算出是 2016，AI 说是 2026，且 2016 在文中出现过，强行信 Python
        if hint_year != "Unknown" and final_year != hint_year:
            # 简单的逻辑：取较小的那个（通常 OCR 容易把 2015 认成 2016，或者 2016 认成 2026）
            # 或者信 Python
            if hint_year in text:
                final_year = hint_year

        # 5. 重命名
        new_base = f"{final_year}_{if_val}_{country}_{title}"
        final_name = clean_filename(new_base) + ".pdf"
        new_path = os.path.join(TARGET_FOLDER, final_name)

        try:
            if old_path != new_path:
                os.rename(old_path, new_path)
                print(f"    [√] {final_name}")
            else:
                print("    [-] 名称无需修改")
        except Exception as e:
            print(f"    [!] 失败: {e}")

        time.sleep(0.5)


if __name__ == "__main__":
    main()