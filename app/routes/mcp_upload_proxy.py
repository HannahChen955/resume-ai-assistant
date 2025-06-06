from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import base64
import tempfile
import shutil
import requests
import os
from urllib.parse import urlparse
import aiohttp

app = FastAPI()

# ✅ 启用跨域（调试阶段可用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定义后端主API的URL
BACKEND_UPLOAD_URL = "http://localhost:8001/upload_resume"

# ✅ 接口 1：支持 multipart/form-data 或 JSON base64 上传
@app.post("/resume-upload-gpt-webhook")
async def proxy_resume_upload(request: Request):
    content_type = request.headers.get("content-type", "")
    tmp_path = None

    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            if "file" not in form:
                return {"error": "Missing 'file' in form data for multipart upload"}
            upload_file = form["file"]
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                shutil.copyfileobj(upload_file.file, tmp)
                tmp_path = tmp.name
            files = {"file": (upload_file.filename, open(tmp_path, "rb"), upload_file.content_type)}
            resp = requests.post(BACKEND_UPLOAD_URL, files=files)
            resp.raise_for_status()
            return {"proxy": "multipart", "code": resp.status_code, "result": resp.json()}

        elif "application/json" in content_type:
            body = await request.json()
            filename = body.get("fileName", "resume.pdf")
            b64data = body.get("fileContent", "")
            if not b64data:
                return {"error": "Missing 'fileContent' in JSON body"}
            try:
                file_bytes = base64.b64decode(b64data)
            except Exception as e:
                return {"error": f"Base64 decode failed: {e}"}
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            files = {"file": (filename, open(tmp_path, "rb"), "application/octet-stream")}
            resp = requests.post(BACKEND_UPLOAD_URL, files=files)
            resp.raise_for_status()
            return {"proxy": "json-base64", "code": resp.status_code, "result": resp.json()}

        elif "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            file_url = form.get("file_url")
            filename = form.get("file_name", "resume.pdf")
            if not file_url:
                return {"error": "Missing 'file_url' in form data"}
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as resp:
                    resp.raise_for_status()
                    content = await resp.read()
                    content_type = resp.headers.get('Content-Type', 'application/octet-stream')
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            files = {"file": (filename, open(tmp_path, "rb"), content_type)}
            resp = requests.post(BACKEND_UPLOAD_URL, files=files)
            resp.raise_for_status()
            return {"proxy": "url-form", "code": resp.status_code, "result": resp.json()}

        else:
            return {"error": f"Unsupported content-type: {content_type}"}

    except Exception as e:
        return {"error": f"Exception occurred: {e}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ✅ 接口 2：支持通过 URL 下载简历后转发上传
@app.post("/resume-upload-url")
async def proxy_upload_from_url(request: Request):
    tmp_path = None
    try:
        data = await request.json()
        file_url = data.get("file_url")
        custom_name = data.get("file_name")
        if not file_url:
            return {"error": "Missing 'file_url' in request body"}
        parsed = urlparse(file_url)
        filename = custom_name or os.path.basename(parsed.path) or "resume.pdf"
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as resp:
                resp.raise_for_status()
                downloaded_content_type = resp.headers.get('Content-Type', 'application/octet-stream')
                content = await resp.read()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        files = {"file": (filename, open(tmp_path, "rb"), downloaded_content_type)}
        resp = requests.post(BACKEND_UPLOAD_URL, files=files)
        resp.raise_for_status()
        return {"proxy": "url-download", "code": resp.status_code, "result": resp.json()}

    except Exception as e:
        return {"error": f"Exception occurred: {e}"}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)