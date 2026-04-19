"""
PDFファイルの保存・読込ヘルパー。

DBにはパスだけを保存し、実体は `data/pdfs/<hash>.pdf` に配置する。
大きなPDFをBLOBでDBに突っ込むよりもパフォーマンスが良く、DBのバックアップも軽くなる。
"""

import hashlib
from pathlib import Path

PDF_DIR = Path("data/pdfs")


def ensure_storage() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)


def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_pdf(data: bytes, file_hash: str) -> str:
    """ハッシュ名でPDFを保存する。既存ファイルがあれば上書きしない。戻り値は相対パス。"""
    ensure_storage()
    path = PDF_DIR / f"{file_hash}.pdf"
    if not path.exists():
        path.write_bytes(data)
    return str(path)


def read_pdf(path: str) -> bytes:
    return Path(path).read_bytes()


def delete_pdf(path: str) -> None:
    p = Path(path)
    if p.exists():
        p.unlink()
