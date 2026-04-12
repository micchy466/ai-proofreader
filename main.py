import os
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

@app.get("/")
def read_root():
    return {"message": "AI校正アプリへようこそ"}

@app.post("/proofread")
async def proofread_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルのみ対応しています")

    pdf_data = await file.read()
    pdf_base64 = base64.standard_b64encode(pdf_data).decode("utf-8")

    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_base64
                    }
                },
                {
                    "type": "text",
                    "text": "このPDFの本文テキストを抽出して校正してください。ノンブル、柱、ヘッダー、フッターは除外してください。誤字脱字、表記ゆれ、文法の誤りを指摘して修正案を提示してください。"
                }
            ]
        }]
    )

    return {
        "filename": file.filename,
        "result": response.content[0].text
    }