import os
import io
import json
import re
import base64
import traceback
import boto3
from botocore.config import Config
from pypdf import PdfReader, PdfWriter
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from prompt import SYSTEM_PROMPT, build_prompt

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bedrock = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    config=Config(read_timeout=600, connect_timeout=30, retries={"max_attempts": 2}),
)

MODEL_ID = os.getenv("BEDROCK_MODEL", "jp.anthropic.claude-sonnet-4-6")
PAGES_PER_CHUNK = 50


@app.get("/")
def read_root():
    return {"message": "AI校正アプリへようこそ"}


def split_pdf(pdf_bytes: bytes, pages_per_chunk: int) -> list[tuple[bytes, int]]:
    """
    PDFを指定ページ数で分割する。
    戻り値: [(chunkのPDFバイト, 元PDFでの開始ページ番号(1-indexed))]
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    chunks = []

    for start in range(0, total_pages, pages_per_chunk):
        writer = PdfWriter()
        end = min(start + pages_per_chunk, total_pages)
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        buffer = io.BytesIO()
        writer.write(buffer)
        chunks.append((buffer.getvalue(), start + 1))

    return chunks


def parse_json_response(raw_text: str) -> dict:
    """
    AIのレスポンスからJSONを抽出する。
    ```json ... ``` のコードブロックにも対応。
    """
    text = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    return json.loads(text)


def proofread_chunk(
    pdf_bytes: bytes, chunk_index: int, total_chunks: int, page_offset: int
) -> list[dict]:
    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    user_prompt = build_prompt(chunk_index, total_chunks, page_offset)

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 8192,
        "temperature": 0.0,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64,
                    },
                },
                {"type": "text", "text": user_prompt},
            ],
        }],
    })

    response = bedrock.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    raw_text = result["content"][0]["text"]

    try:
        parsed = parse_json_response(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"AIの出力がJSONとしてパースできません: {e}\n生の出力: {raw_text[:500]}")

    corrections = parsed.get("corrections", [])

    for c in corrections:
        if "page" not in c or not isinstance(c.get("page"), int):
            c["page"] = page_offset

    return corrections


@app.post("/proofread")
async def proofread_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルのみ対応しています")

    pdf_data = await file.read()

    try:
        chunks = split_pdf(pdf_data, PAGES_PER_CHUNK)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDFの読み込みに失敗しました: {str(e)}")

    print(f"[proofread] 分割数={len(chunks)}, ファイル={file.filename}", flush=True)

    all_corrections = []
    for i, (chunk_bytes, page_offset) in enumerate(chunks):
        print(
            f"[proofread] {i + 1}/{len(chunks)} Bedrock送信中 (ページ{page_offset}〜)...",
            flush=True,
        )
        try:
            corrections = proofread_chunk(chunk_bytes, i, len(chunks), page_offset)
            print(
                f"[proofread] {i + 1}/{len(chunks)} 完了: {len(corrections)}件の指摘",
                flush=True,
            )
            all_corrections.extend(corrections)
        except Exception as e:
            print(f"[proofread] エラー詳細:\n{traceback.format_exc()}", flush=True)
            raise HTTPException(
                status_code=500,
                detail=f"処理エラー（{i + 1}/{len(chunks)}分割目）: {str(e)}",
            )

    for idx, c in enumerate(all_corrections, start=1):
        c["id"] = idx

    summary = {
        "high": sum(1 for c in all_corrections if c.get("severity") == "high"),
        "medium": sum(1 for c in all_corrections if c.get("severity") == "medium"),
        "low": sum(1 for c in all_corrections if c.get("severity") == "low"),
    }

    return {
        "filename": file.filename,
        "total_chunks": len(chunks),
        "total_corrections": len(all_corrections),
        "summary": summary,
        "corrections": all_corrections,
    }
