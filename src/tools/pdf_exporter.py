import os
import datetime

# macOS: ensure homebrew libraries are findable by weasyprint/pango
if "DYLD_FALLBACK_LIBRARY_PATH" not in os.environ:
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = "/opt/homebrew/lib"

import markdown
from weasyprint import HTML


def generate_pdf(markdown_text: str, output_dir: str = "./output", filename: str = "report") -> str:
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(output_dir, f"{filename}_{ts}.pdf")

    html_body = markdown.markdown(markdown_text, extensions=["tables", "fenced_code"])
    html_full = f"""<!DOCTYPE html><html><head>
    <meta charset="utf-8">
    <style>
      body {{ font-family: -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', sans-serif;
              font-size: 11pt; margin: 2cm; line-height: 1.6; color: #222; }}
      h1 {{ font-size: 20pt; border-bottom: 2px solid #333; padding-bottom: 8px; margin-top: 0; }}
      h2 {{ font-size: 15pt; border-bottom: 1px solid #888; margin-top: 24px; }}
      h3 {{ font-size: 13pt; margin-top: 16px; }}
      table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 10pt; }}
      th, td {{ border: 1px solid #ccc; padding: 6px 10px; text-align: left; }}
      th {{ background: #2c5f8a; color: #fff; font-weight: bold; }}
      tr:nth-child(even) {{ background: #f4f8fb; }}
      tr:hover {{ background: #e8f0fe; }}
      img {{ max-width: 100%; display: block; margin: 12px auto; }}
      code {{ background: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-size: 10pt; }}
      pre {{ background: #f0f0f0; padding: 12px; border-radius: 4px; overflow-x: auto; }}
      blockquote {{ border-left: 4px solid #ccc; margin: 0; padding-left: 16px; color: #555; }}
      ul, ol {{ margin: 8px 0; padding-left: 24px; }}
      li {{ margin: 4px 0; }}
      hr {{ border: none; border-top: 1px solid #ccc; margin: 20px 0; }}
      a {{ color: #1a73e8; word-break: break-all; }}
    </style>
    </head><body>{html_body}</body></html>"""

    HTML(string=html_full).write_pdf(pdf_path)
    return pdf_path
