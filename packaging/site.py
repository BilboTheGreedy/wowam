import shutil
from pathlib import Path

import markdown

root = Path(__file__).resolve().parent.parent
site = root / "site"
repo = "https://github.com/BilboTheGreedy/wowam"

img = site / "img"
img.mkdir(exist_ok=True)
for f in list((root / "docs").glob("*.png")) + [root / "src/wowam/data/wowam.svg"]:
    shutil.copy(f, img / f.name)

text = (root / "docs/guide.md").read_text(encoding="utf-8")
text = text.replace("../README.md", repo)

md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])
body = md.convert(text)
sections = md.toc_tokens[0]["children"]
nav = "\n".join('    <a href="#%s">%s</a>' % (s["id"], s["name"]) for s in sections)

page = (site / "guide.tpl").read_text(encoding="utf-8")
page = page.replace("{{nav}}", nav).replace("{{body}}", body)
(site / "guide.html").write_text(page, encoding="utf-8")
