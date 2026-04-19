"""
DB エンジンとセッション管理。

DATABASE_URL 環境変数で接続先を切り替え可能:
  - SQLite (開発):  sqlite:///./data/proofreader.db
  - PostgreSQL (本番): postgresql://user:pass@host:5432/proofreader
  - MySQL:        mysql+pymysql://user:pass@host/proofreader
"""

import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/proofreader.db")

# SQLiteの場合はファイル置き場を先に作っておく
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

# SQLite特有のオプション
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)


def init_db() -> None:
    """起動時にテーブルを作成する（既存テーブルは維持）。"""
    # modelsをインポートしてSQLModel.metadataに登録
    import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    """FastAPIの依存として使うセッション。context managerで使う想定。"""
    return Session(engine)
