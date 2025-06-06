from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import subprocess
import shutil
import uuid
import os
import threading
import unicodedata

router = APIRouter()

# 📁 设置目录路径
UPLOAD_DIR = Path("~/Documents/recruitment_rag_system/data/resumes").expanduser()
EXTRACT_SCRIPT = Path("scripts/extract_text_openai.py")
INDEX_SCRIPT = Path("scripts/index_resumes_openai.py")

def sanitize_filename(name: str) -> str:
    """转换为 ASCII 并去除特殊符号"""
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii')
    name = name.replace(' ', '_')
    return name or "resume"

@router.post("/upload_resume", summary="上传简历文件（后台异步处理）")
async def upload_resume(file: UploadFile = File(...)):
    try:
        # ✅ 确保上传目录存在
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # ✅ 清洗文件名并生成唯一保存名
        raw_name = Path(file.filename).stem
        ext = Path(file.filename).suffix
        safe_name = sanitize_filename(raw_name)
        filename = f"{safe_name}_{uuid.uuid4().hex[:8]}{ext}"
        save_path = UPLOAD_DIR / filename

        # ✅ 写入文件
        with open(save_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)

        print(f"📥 文件已保存到: {save_path}")

        # ✅ 后台执行 extract + index 脚本
        def background_process():
            try:
                print("🧠 执行 extract_text_openai.py")
                subprocess.run(["python", str(EXTRACT_SCRIPT)], check=True)
                print("🔍 执行 index_resumes_openai.py")
                subprocess.run(["python", str(INDEX_SCRIPT)], check=True)
                print("✅ 简历处理完成")
            except Exception as e:
                print(f"❌ 后台任务失败: {e}")

        threading.Thread(target=background_process).start()

        return {
            "status": "success",
            "filename": filename,
            "message": "简历上传成功，处理任务已在后台启动"
        }

    except Exception as e:
        return {
            "status": "error",
            "step": "upload",
            "message": str(e)
        }