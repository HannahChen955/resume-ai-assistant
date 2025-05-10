#!/usr/bin/env python3

import os
import re
import fitz  # PyMuPDF
from docx import Document
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv
import json
import uuid
from pdf2image import convert_from_path
from PIL import Image
import pytesseract
from scripts.config import settings

# ✅ 环境变量
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ 路径配置
INPUT_DIR = "data/resumes"
OUTPUT_DIR = "data/resumes_extract_enhanced"
MODEL = "gpt-3.5-turbo-1106"

# ✅ 黑名单关键词
BLACKLIST = ["个人简历", "猎聘", "BOSS直聘", "客户名称", "项目名称", "original", "standard"]

# ========== 工具函数 ==========

def extract_pdf_text(file_path):
    try:
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    except Exception as e:
        print(f"❌ PDF读取失败：{file_path} | {e}")
        return None

def extract_docx_text(file_path):
    try:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        print(f"❌ DOCX读取失败：{file_path} | {e}")
        return None

def extract_via_ocr(pdf_path):
    try:
        print(f"📸 尝试 OCR 识别：{os.path.basename(pdf_path)}")
        images = convert_from_path(pdf_path, dpi=300)
        if not images:
            return None
        return pytesseract.image_to_string(images[0], lang='chi_sim')
    except Exception as e:
        print(f"⚠️ OCR 提取失败：{e}")
        return None

def enhance_text(text):
    text = re.sub(r'(Confidential:|Disclaimer:|This report has been prepared).*?(executives concerned\.|verification\.)', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'\b[a-zA-Z0-9]{20,}\b', '', text)
    text = re.sub(r'(~{2,}|-{2,}|={2,}|\+{2,})', '', text)
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def gpt_extract_fields(text):
    snippet = text[:600]
    prompt = f"""
请从以下文本中识别以下字段（若缺失请写 null）：
- 姓名
- 应聘职位
- 手机号
- 邮箱
仅返回标准 JSON，不要附加说明。

文本如下：
\"\"\"
{snippet}
\"\"\"
    """
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=300
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"^```(json)?|```$", "", content)
        return json.loads(content) if content else {}
    except Exception as e:
        print(f"⚠️ GPT字段提取失败：{e}")
        return {}

def extract_name_fallback(filename, text):
    base = os.path.splitext(os.path.basename(filename))[0]
    name_candidates = re.findall(r'[\u4e00-\u9fa5]{2,4}', base)
    for name in name_candidates:
        if name not in BLACKLIST:
            return name
    head_text = text[:50]
    name_candidates = re.findall(r'[\u4e00-\u9fa5]{2,4}', head_text)
    for name in name_candidates:
        if name not in BLACKLIST:
            return name
    return "未知姓名"

def insert_header_block(text, fields):
    block = ["=" * 30]
    for key in ['姓名', '应聘职位', '手机号', '邮箱']:
        if fields.get(key):
            block.append(f"{key}：{fields[key]}")
    block.append("=" * 30)
    block.append("")
    return "\n".join(block) + text

def generate_filename(fields):
    name = fields.get("姓名") or "未知姓名"
    position = fields.get("应聘职位") or "未知职位"
    for kw in BLACKLIST:
        name = name.replace(kw, "")
        position = position.replace(kw, "")
    name = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", name)
    position = re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", position)
    uid = str(uuid.uuid4())[:8]
    return f"{name}_{position}_{uid}.txt"

# ========== 主流程 ==========

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.pdf', '.docx'))]
    success, fail = 0, 0

    for filename in tqdm(files, desc="Extracting with AI enhancement"):
        try:
            path = os.path.join(INPUT_DIR, filename)
            ext = filename.lower().split('.')[-1]

            text = None
            if ext == "pdf":
                text = extract_pdf_text(path)
                if not text or not text.strip():
                    print(f"⚠️ PyMuPDF 提取失败，切换 OCR：{filename}")
                    text = extract_via_ocr(path)
            elif ext == "docx":
                text = extract_docx_text(path)
            else:
                print(f"⏭️ 跳过：不支持的格式 {filename}")
                continue

            if not text or not text.strip():
                print(f"⚠️ 空文本占位：{filename}")
                text = "[文件读取失败或内容为空]"

            text = enhance_text(text)
            fields = gpt_extract_fields(text) or {}

            # ✅ 只有当 GPT 没提取出姓名时再 fallback
            if not fields.get("姓名"):
                fields["姓名"] = extract_name_fallback(filename, text)

            output_text = insert_header_block(text, fields)
            output_name = generate_filename(fields)
            output_path = os.path.join(OUTPUT_DIR, output_name)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"✅ 输出：{output_name}")
            success += 1

        except Exception as e:
            print(f"❌ 处理失败：{filename} | {e}")
            fail += 1

    print(f"\n🎯 完成：共 {len(files)} 份 | 成功：{success} | 失败：{fail}")

if __name__ == "__main__":
    main()
