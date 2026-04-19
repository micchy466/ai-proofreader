import os
import io
import json
import re
import base64
import traceback
from contextlib import asynccontextmanager

import boto3
from botocore.config import Config
from pypdf import PdfReader, PdfWriter
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv
from sqlalchemy import desc
from sqlmodel import Session, select

from prompt import SYSTEM_PROMPT, build_prompt
from db import engine, init_db
from models import Correction, ProofreadResult
from storage import compute_hash, read_pdf, save_pdf, delete_pdf

load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)

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


def extract_text_normalized(pdf_bytes: bytes) -> str:
    """PDFから全テキストを抽出し、空白・改行を除去した1つの文字列にする。

    縦書きPDFの行またぎ誤検知を検出するために使う。
    pypdfの抽出は縦書きでも基本的に文字の順序は保持される（行間の改行は入る）ため、
    空白類を除去すれば連続した本文に近い状態になる。
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "".join(p.extract_text() or "" for p in reader.pages)
        return re.sub(r"\s+", "", text)
    except Exception:
        return ""


def filter_false_positives(corrections: list[dict], normalized_text: str) -> tuple[list[dict], int]:
    """suggestion（修正案）が normalized_text にそのまま存在する場合、
    行またぎ等による誤検知とみなして除外する。

    戻り値: (残った指摘, 除外された件数)
    """
    if not normalized_text:
        return corrections, 0

    filtered = []
    removed = 0
    for c in corrections:
        original = (c.get("original") or "").strip()
        suggestion = (c.get("suggestion") or "").strip()

        # suggestionがoriginalの拡張（文字が増えている）かつ、
        # suggestionがPDF内にそのまま存在する場合は誤検知
        if suggestion and len(suggestion) > len(original):
            normalized_sugg = re.sub(r"\s+", "", suggestion)
            if normalized_sugg and normalized_sugg in normalized_text:
                print(
                    f"[filter] 誤検知を除外: '{original}' → '{suggestion}' "
                    f"(suggestion がPDFに既に存在)",
                    flush=True,
                )
                removed += 1
                continue

        filtered.append(c)

    return filtered, removed


def split_pdf(pdf_bytes: bytes, pages_per_chunk: int) -> list[tuple[bytes, int]]:
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


def group_corrections(corrections: list[dict]) -> list[dict]:
    severity_rank = {"high": 3, "medium": 2, "low": 1}
    groups: dict[tuple, dict] = {}

    for c in corrections:
        key = (c.get("category"), c.get("original"), c.get("suggestion"))
        page = c.get("page")

        if key not in groups:
            groups[key] = {
                "category": c.get("category"),
                "severity": c.get("severity"),
                "original": c.get("original"),
                "suggestion": c.get("suggestion"),
                "explanation": c.get("explanation", ""),
                "pages": [page] if page is not None else [],
            }
        else:
            group = groups[key]
            if page is not None and page not in group["pages"]:
                group["pages"].append(page)
            if severity_rank.get(c.get("severity"), 0) > severity_rank.get(group["severity"], 0):
                group["severity"] = c.get("severity")
            if len(c.get("explanation", "")) > len(group["explanation"]):
                group["explanation"] = c.get("explanation", "")

    result = list(groups.values())
    for g in result:
        g["pages"].sort()
        g["count"] = len(g["pages"])

    result.sort(
        key=lambda x: (
            -severity_rank.get(x["severity"], 0),
            -x["count"],
            x["pages"][0] if x["pages"] else 0,
        )
    )

    for idx, c in enumerate(result, start=1):
        c["id"] = idx

    return result


def result_to_dict(result: ProofreadResult, corrections: list[Correction]) -> dict:
    """DBエンティティをAPIレスポンス用のdictに変換。"""
    return {
        "id": result.id,
        "filename": result.filename,
        "file_hash": result.file_hash,
        "created_at": result.created_at.isoformat() if result.created_at else None,
        "total_chunks": result.total_chunks,
        "total_corrections": result.total_corrections,
        "total_unique_corrections": result.total_unique_corrections,
        "summary": {
            "high": result.summary_high,
            "medium": result.summary_medium,
            "low": result.summary_low,
        },
        "corrections": [
            {
                "id": c.order_index,
                "category": c.category,
                "severity": c.severity,
                "original": c.original,
                "suggestion": c.suggestion,
                "explanation": c.explanation,
                "count": c.count,
                "pages": c.pages or [],
            }
            for c in corrections
        ],
    }


@app.post("/proofread")
async def proofread_pdf(
    file: UploadFile = File(...),
    force: bool = False,
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDFファイルのみ対応しています")

    pdf_data = await file.read()
    file_hash = compute_hash(pdf_data)

    # 既に同じPDFが処理済みなら結果を再利用（コスト削減）
    # force=true の場合はキャッシュを無視し、古い結果を削除して再校正
    with Session(engine) as session:
        existing = session.exec(
            select(ProofreadResult).where(ProofreadResult.file_hash == file_hash)
        ).first()
        if existing and not force:
            corrections = sorted(existing.corrections, key=lambda c: c.order_index)
            print(f"[proofread] キャッシュヒット: hash={file_hash[:12]}...", flush=True)
            return {"cached": True, **result_to_dict(existing, corrections)}
        if existing and force:
            print(f"[proofread] 強制再校正のため古い結果を削除: id={existing.id}", flush=True)
            session.delete(existing)
            session.commit()

    # 分割して各チャンクを処理
    try:
        chunks = split_pdf(pdf_data, PAGES_PER_CHUNK)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDFの読み込みに失敗しました: {str(e)}")

    print(f"[proofread] 分割数={len(chunks)}, ファイル={file.filename}", flush=True)

    # PDFテキスト全体を事前抽出（誤検知フィルタ用）
    full_normalized_text = extract_text_normalized(pdf_data)

    all_corrections = []
    total_removed = 0
    for i, (chunk_bytes, page_offset) in enumerate(chunks):
        print(
            f"[proofread] {i + 1}/{len(chunks)} Bedrock送信中 (ページ{page_offset}〜)...",
            flush=True,
        )
        try:
            corrections = proofread_chunk(chunk_bytes, i, len(chunks), page_offset)

            # 誤検知フィルタ: suggestion がPDFに既に存在するものを除外
            filtered, removed = filter_false_positives(corrections, full_normalized_text)
            total_removed += removed

            print(
                f"[proofread] {i + 1}/{len(chunks)} 完了: {len(corrections)}件中{len(filtered)}件採用"
                f"（{removed}件を誤検知として除外）",
                flush=True,
            )
            all_corrections.extend(filtered)
        except Exception as e:
            print(f"[proofread] エラー詳細:\n{traceback.format_exc()}", flush=True)
            raise HTTPException(
                status_code=500,
                detail=f"処理エラー（{i + 1}/{len(chunks)}分割目）: {str(e)}",
            )

    if total_removed > 0:
        print(f"[proofread] 合計{total_removed}件の誤検知を自動除外", flush=True)

    grouped = group_corrections(all_corrections)

    # PDFをファイル保存
    pdf_path = save_pdf(pdf_data, file_hash)

    # DBに保存
    with Session(engine) as session:
        result = ProofreadResult(
            filename=file.filename,
            file_hash=file_hash,
            file_size=len(pdf_data),
            pdf_path=pdf_path,
            total_chunks=len(chunks),
            total_corrections=len(all_corrections),
            total_unique_corrections=len(grouped),
            summary_high=sum(1 for c in grouped if c.get("severity") == "high"),
            summary_medium=sum(1 for c in grouped if c.get("severity") == "medium"),
            summary_low=sum(1 for c in grouped if c.get("severity") == "low"),
        )
        session.add(result)
        session.flush()  # idを確定

        for g in grouped:
            session.add(Correction(
                result_id=result.id,
                category=g.get("category"),
                severity=g.get("severity"),
                original=g.get("original"),
                suggestion=g.get("suggestion"),
                explanation=g.get("explanation"),
                count=g.get("count", 1),
                pages=g.get("pages", []),
                order_index=g.get("id", 0),
            ))

        session.commit()
        session.refresh(result)
        corrections_list = sorted(result.corrections, key=lambda c: c.order_index)
        return {"cached": False, **result_to_dict(result, corrections_list)}


@app.get("/history")
def get_history(limit: int = 50):
    """過去の校正結果一覧を新しい順に返す。"""
    with Session(engine) as session:
        results = session.exec(
            select(ProofreadResult).order_by(desc(ProofreadResult.created_at)).limit(limit)
        ).all()
        return [
            {
                "id": r.id,
                "filename": r.filename,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "total_unique_corrections": r.total_unique_corrections,
                "total_corrections": r.total_corrections,
                "summary": {
                    "high": r.summary_high,
                    "medium": r.summary_medium,
                    "low": r.summary_low,
                },
            }
            for r in results
        ]


@app.get("/results/{result_id}")
def get_result(result_id: int):
    with Session(engine) as session:
        result = session.get(ProofreadResult, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="指定されたIDの結果が見つかりません")
        corrections = sorted(result.corrections, key=lambda c: c.order_index)
        return result_to_dict(result, corrections)


@app.get("/results/{result_id}/pdf")
def get_result_pdf(result_id: int):
    """保存されているPDFファイルを返す。"""
    with Session(engine) as session:
        result = session.get(ProofreadResult, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="指定されたIDの結果が見つかりません")
        try:
            data = read_pdf(result.pdf_path)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="PDFファイルが存在しません")
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{result.filename}"'},
        )


@app.delete("/results/{result_id}")
def delete_result(result_id: int):
    with Session(engine) as session:
        result = session.get(ProofreadResult, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="指定されたIDの結果が見つかりません")

        # 他の結果で同じPDFを参照していなければファイルも消す
        same_file_count = session.exec(
            select(ProofreadResult).where(ProofreadResult.file_hash == result.file_hash)
        ).all()
        should_delete_file = len(same_file_count) <= 1

        pdf_path = result.pdf_path
        session.delete(result)
        session.commit()

        if should_delete_file:
            delete_pdf(pdf_path)

        return {"deleted": True, "id": result_id}
