"""
縦書きのテスト用PDFを生成するスクリプト。

AI校正とハイライト機能が縦書きPDFで動作するか検証するために使う。

含める誤り:
  - 誤変換: 「機関」を文脈的に誤った意味で使用
  - 脱字: 「ください」→「くさい」
  - 表記ゆれ: 「サーバー」と「サーバ」を混在
  - 類似文字: 「ンステム」

実行方法:
  source venv/bin/activate
  python scripts/generate_test_pdf_vertical.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "test_pdfs" / "test_vertical.pdf"


def draw_vertical_text(c, text: str, right_x: float, top_y: float, font_size: int, line_height: float):
    """縦書きテキストを描画。右から左に、上から下にレイアウト。"""
    c.setFont("HeiseiMin-W3", font_size)
    for line in text.split("\n"):
        # 縦書きでは縦方向に1文字ずつ下に配置していく
        y = top_y
        for ch in line:
            c.drawString(right_x, y, ch)
            y -= font_size * 1.3
        right_x -= line_height


def draw_vertical_text_mincho(c, text: str, right_x: float, top_y: float, font_size: int, line_width: float):
    c.setFont("HeiseiMin-W3", font_size)
    y = top_y
    current_x = right_x
    for ch in text:
        if ch == "\n":
            current_x -= line_width
            y = top_y
            continue
        c.drawString(current_x, y, ch)
        y -= font_size * 1.5


def build_page_1(c: canvas.Canvas):
    width, height = A4
    # タイトル（大きめ、縦書き）
    c.setFont("HeiseiKakuGo-W5", 22)
    title = "縦書きAI校正テスト"
    y = height - 80
    tx = width - 60
    for ch in title:
        c.drawString(tx, y, ch)
        y -= 30

    # 本文
    body = (
        "本書は縦書きにおけるAI校正の"
        "精度を検証するための文書である。"
        "\n\n"
        "近年、多くの企業が自社の機関を"
        "再編し、クラウド化を進めている。"
        "\n"
        "定期的なバックアップを行うこと"
        "が重要であり、運用チームは日々、"
        "監視作業を継続している。"
        "\n\n"
        "本書を活用し、運用スキルを確実に"
        "身につけてくさい。"
    )

    c.setFont("HeiseiMin-W3", 13)
    y = height - 120
    tx = width - 110
    line_width = 22
    for ch in body:
        if ch == "\n":
            tx -= line_width
            y = height - 120
            continue
        c.drawString(tx, y, ch)
        y -= 19
        if y < 80:
            tx -= line_width
            y = height - 120


def build_page_2(c: canvas.Canvas):
    width, height = A4
    c.setFont("HeiseiKakuGo-W5", 18)
    heading = "第二章 サーバ構成"
    y = height - 80
    tx = width - 60
    for ch in heading:
        c.drawString(tx, y, ch)
        y -= 24

    body = (
        "サーバの選定には、オンプレミス、"
        "クラウド、ハイブリッドの選択肢がある。"
        "\n\n"
        "第一章では「サーバー」と表記したが"
        "この章では「サーバ」と表記している。"
        "（表記ゆれの意図的な混在）"
        "\n\n"
        "アラートのしきい値は、運用チームと"
        "相談してチューニングする。"
        "ンステム全体の状態を継続的に監視する"
        "必要がある。"
    )

    c.setFont("HeiseiMin-W3", 13)
    y = height - 120
    tx = width - 110
    line_width = 22
    for ch in body:
        if ch == "\n":
            tx -= line_width
            y = height - 120
            continue
        c.drawString(tx, y, ch)
        y -= 19
        if y < 80:
            tx -= line_width
            y = height - 120


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=A4)
    c.setTitle("縦書きAI校正テスト")

    build_page_1(c)
    c.showPage()
    build_page_2(c)
    c.showPage()

    c.save()
    print(f"生成しました: {OUTPUT_PATH}")
    print()
    print("意図的に含めた誤り:")
    print("  1. 誤変換: 「機関を再編」")
    print("  2. 脱字: 「身につけてくさい」")
    print("  3. 表記ゆれ: 「サーバー」と「サーバ」")
    print("  4. 類似文字: 「ンステム」")


if __name__ == "__main__":
    main()
