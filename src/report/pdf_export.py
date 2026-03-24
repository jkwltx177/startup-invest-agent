"""Markdown 보고서를 PDF로 변환."""
from pathlib import Path


def md_to_pdf(md_path: str, pdf_path: str) -> bool:
    """
    Markdown → HTML → PDF (weasyprint).
    실패 시 False 반환 → caller가 .md 경로 사용
    """
    try:
        import markdown
        from weasyprint import HTML
        from weasyprint.text.fonts import FontConfiguration

        md_content = Path(md_path).read_text(encoding="utf-8")
        html_body = markdown.markdown(
            md_content,
            extensions=["tables", "fenced_code", "nl2br"],
        )
        full_html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Helvetica', sans-serif; font-size: 11pt; line-height: 1.5; margin: 2cm; }}
    h1 {{ font-size: 18pt; border-bottom: 1px solid #333; padding-bottom: 0.3em; }}
    h2 {{ font-size: 14pt; margin-top: 1.2em; }}
    h3 {{ font-size: 12pt; margin-top: 1em; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #ddd; padding: 6px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    ul, ol {{ margin: 0.5em 0; padding-left: 1.5em; }}
    @page {{ size: A4; margin: 2cm; }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

        font_config = FontConfiguration()
        HTML(string=full_html).write_pdf(pdf_path, font_config=font_config)
        return True
    except Exception:
        return False
