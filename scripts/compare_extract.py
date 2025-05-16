#!/usr/bin/env python3

"""
对比原始简历与提取后的简历内容（语义 + 关键信息字段）
输出 Markdown 报告，评估提取质量。
"""

import os
import re
import difflib
import json
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# 文件路径
BEFORE_DIR = "data/resumes"
AFTER_DIR = "data/resumes_extract_enhanced"
REPORT_PATH = "extract_compare_report.md"

# 判断相似度
def get_similarity_score(text1, text2) -> float:
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{
                "role": "user",
                "content": f"""请你判断下面两个文本是否属于同一个人的简历，只返回一个 0-100 的分数，越高表示越可能是：
【简历原始版】：
{text1}

【简历提取后】：
{text2}
"""
            }],
            temperature=0
        )
        score_text = response.choices[0].message.content.strip()
        score = float(re.findall(r"\d+", score_text)[0])
        return min(score, 100.0)
    except Exception as e:
        print("❌ 相似度计算失败:", e)
        return 0.0

# 读取文件内容
def read_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return ""

# 提取字段
def extract_fields(text: str):
    try:
        fields = {
            "姓名": None,
            "职位": None,
            "邮箱": None,
            "电话": None
        }
        if match := re.search(r"姓名[:：]?\s*(\S{1,6})", text):
            fields["姓名"] = match.group(1)
        if match := re.search(r"意向职位[:：]?\s*(\S{2,20})", text):
            fields["职位"] = match.group(1)
        if match := re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text):
            fields["邮箱"] = match.group(0)
        if match := re.search(r"(?:\+86[- ]?)?1[3-9]\d{9}", text):
            fields["电话"] = match.group(0)
        return fields
    except:
        return {}

# 查找最匹配的 after 文件
def find_best_match(before_text: str, after_texts: dict):
    scores = {
        path: get_similarity_score(before_text, after_text)
        for path, after_text in after_texts.items()
    }
    best_path = max(scores, key=scores.get)
    return best_path, scores[best_path]

# 主流程
def run_compare():
    before_files = [f for f in os.listdir(BEFORE_DIR) if f.lower().endswith((".pdf", ".doc", ".docx", ".txt"))]
    after_files = [f for f in os.listdir(AFTER_DIR) if f.endswith(".txt")]

    after_texts = {
        f: read_file(os.path.join(AFTER_DIR, f)) for f in after_files
    }

    report_lines = ["# ✅ 简历抽取比对报告\n"]

    for bf in tqdm(before_files):
        before_path = os.path.join(BEFORE_DIR, bf)
        before_text = read_file(before_path)

        best_after, score = find_best_match(before_text, after_texts)
        after_text = after_texts[best_after]
        fields = extract_fields(after_text)

        if not isinstance(fields, dict):
            fields = {}

        missing = [k for k, v in fields.items() if not v or v == "null"]

        report_lines.append(f"## 📄 {bf}")
        report_lines.append(f"- 匹配 After 文件: `{best_after}`")
        report_lines.append(f"- 相似度分数: **{score:.1f}**")
        report_lines.append(f"- 抽取字段: {json.dumps(fields, ensure_ascii=False)}")
        report_lines.append(f"- ❗缺失字段: {', '.join(missing) if missing else '无'}")
        report_lines.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"\n✅ 报告已生成：{REPORT_PATH}")

if __name__ == "__main__":
    run_compare()