"""
SQLModel による DB スキーマ定義。

SQLite / PostgreSQL / MySQL で動くように、DB固有の機能は使わず、
SQLAlchemy の抽象型（JSON、Text等）を活用している。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ProofreadResult(SQLModel, table=True):
    """校正結果1件（= アップロードされたPDF1本に対する結果）"""

    __tablename__ = "proofread_results"

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    file_hash: str = Field(index=True, unique=True, description="PDF内容のSHA256")
    file_size: int = Field(description="バイト数")
    pdf_path: str = Field(description="保存先のファイルパス（相対パス）")
    created_at: datetime = Field(default_factory=_now_utc, index=True)

    total_chunks: int = 0
    total_corrections: int = 0
    total_unique_corrections: int = 0
    summary_high: int = 0
    summary_medium: int = 0
    summary_low: int = 0

    corrections: list["Correction"] = Relationship(
        back_populates="result",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Correction(SQLModel, table=True):
    """個別の指摘（グループ化済み）"""

    __tablename__ = "corrections"

    id: Optional[int] = Field(default=None, primary_key=True)
    result_id: int = Field(foreign_key="proofread_results.id", index=True)

    category: Optional[str] = None  # typo / notation / grammar
    severity: Optional[str] = None  # high / medium / low
    original: Optional[str] = None
    suggestion: Optional[str] = None
    explanation: Optional[str] = None
    count: int = 1
    pages: list[int] = Field(default_factory=list, sa_column=Column(JSON))
    order_index: int = 0  # 表示順を保持

    result: Optional[ProofreadResult] = Relationship(back_populates="corrections")
