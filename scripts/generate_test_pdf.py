"""
AI校正アプリのテスト用PDFを生成するスクリプト。

意図的に以下のような誤りを含む短いPDFを作成し、AI校正の精度を低コストで検証する。

含まれる誤り（期待される指摘）:
  - 誤変換: 「期間」が正しい所で「機関」を使用
  - 脱字: 「ください」→「くさい」
  - 送り仮名: 「行なう」（本則は「行う」）
  - 表記ゆれ: 「サーバー」と「サーバ」を意図的に混在
  - 助詞誤り: 「を」→「お」
  - 類似文字: 「シ／ツ」の取り違え

含めない（指摘されたら誤検知）:
  - 専門用語、固有名詞
  - 文体の好みに依存する表現
  - 算用数字と漢数字の混在

実行方法:
  source venv/bin/activate
  python scripts/generate_test_pdf.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# 日本語フォント登録（reportlabに同梱のCIDフォント）
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "test_pdfs" / "test_short.pdf"


def build_styles():
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "JpTitle",
        parent=base["Title"],
        fontName="HeiseiKakuGo-W5",
        fontSize=20,
        leading=26,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "JpHeading",
        parent=base["Heading1"],
        fontName="HeiseiKakuGo-W5",
        fontSize=14,
        leading=20,
        spaceBefore=18,
        spaceAfter=8,
    )
    body_style = ParagraphStyle(
        "JpBody",
        parent=base["BodyText"],
        fontName="HeiseiMin-W3",
        fontSize=11,
        leading=18,
        spaceAfter=10,
    )
    return title_style, heading_style, body_style


def build_story():
    title_style, heading_style, body_style = build_styles()
    story = []

    # ── 1ページ目: タイトル + 序章 ─────────────────────
    story.append(Paragraph("AI校正テスト用文書", title_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("第一章 サーバー運用の基礎", heading_style))
    story.append(Paragraph(
        "本書では、サーバーの基本的な運用について解説します。"
        "近年、多くの企業が自社の機関を再編し、"  # 誤変換: 機関 → 期間
        "クラウドへの移行を進めています。",
        body_style,
    ))
    story.append(Paragraph(
        "とくに重要なのは、定期的なバックアップを行なうことです。"  # 送り仮名: 行なう → 行う
        "障害発生時には、速やかに対応することが求められます。",
        body_style,
    ))
    story.append(Paragraph(
        "本書を活用して、確実に運用スキルを身につけてくさい。",  # 脱字: ください → くさい
        body_style,
    ))

    story.append(PageBreak())

    # ── 2ページ目: 表記ゆれを意図的に混在 ─────────────
    story.append(Paragraph("第二章 サーバ構成の選定", heading_style))  # 表記ゆれ: サーバ
    story.append(Paragraph(
        "サーバの構成を決める際には、いくつかの選択肢があります。"  # 「サーバ」と「サーバー」が文書内で混在
        "オンプレミス、クラウド、ハイブリッドの三つが代表的です。",
        body_style,
    ))
    story.append(Paragraph(
        "それぞれにメリットとデメリットがあるため、"
        "自社の要件お整理してから選定する必要があります。",  # 助詞誤り: を → お
        body_style,
    ))
    story.append(Paragraph(
        "また、長期的な運用コストも考慮することが重要です。",
        body_style,
    ))

    story.append(PageBreak())

    # ── 3ページ目: 類似文字 + 軽微な指摘候補 ───────────
    story.append(Paragraph("第三章 監視とアラート", heading_style))
    story.append(Paragraph(
        "システムの異常を早期に検知するために、"
        "メトリクスを継続的にモニタリングします。"
        "代表的なツールにはプロメテウスやグラファナがあります。",
        body_style,
    ))
    story.append(Paragraph(
        "アラートのしきい値は、運用チームと相談しながらチューニングします。"
        "誤検知が多いと、本当に重要なアラートが埋もれてしまうため、"
        "適切なバランスが必要です。",
        body_style,
    ))
    story.append(Paragraph(
        "本章では、ンステム監視の基本的な考え方を解説しました。",  # 類似文字: シ → ン (シ/ツ/ソ/ンの取り違え系)
        body_style,
    ))

    return story


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="AI校正テスト用文書",
    )

    doc.build(build_story())
    print(f"生成しました: {OUTPUT_PATH}")
    print()
    print("意図的に含めた誤り:")
    print("  1. 誤変換: 「機関を再編」→ 文脈的に「期間を再編」が自然")
    print("  2. 送り仮名: 「行なう」→「行う」（本則）")
    print("  3. 脱字: 「身につけてくさい」→「身につけてください」")
    print("  4. 表記ゆれ: 「サーバー」と「サーバ」が文書内で混在")
    print("  5. 助詞誤り: 「要件お整理」→「要件を整理」")
    print("  6. 類似文字: 「ンステム」→「システム」")


if __name__ == "__main__":
    main()
