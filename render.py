"""Render AI Diary Instagram slides (1080x1350 JPEG) and avatar from an entry JSON.

Usage:
  python3 render.py entries/001.json out/      -> out/entry-001-1.jpg, -2.jpg, ...
  python3 render.py --avatar out/avatar.jpg
"""
import html
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
FONTS = ROOT / "fonts"

BG = "#0f0e0c"
INK = "#ece4d4"
AMBER = "#ffb347"

FONT_CSS = "\n".join(
    f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{w};"
    f"src:url('file://{FONTS}/{file}') format('woff2');}}"
    for fam, file, w, style in [
        ("Fraunces", "fraunces-latin-300-normal.woff2", 300, "normal"),
        ("Fraunces", "fraunces-latin-300-italic.woff2", 300, "italic"),
        ("Fraunces", "fraunces-latin-400-normal.woff2", 400, "normal"),
        ("Fraunces", "fraunces-latin-400-italic.woff2", 400, "italic"),
        ("Fraunces", "fraunces-latin-600-normal.woff2", 600, "normal"),
        ("Fraunces", "fraunces-latin-600-italic.woff2", 600, "italic"),
        ("JetBrains Mono", "jetbrains-mono-latin-400-normal.woff2", 400, "normal"),
        ("JetBrains Mono", "jetbrains-mono-latin-500-normal.woff2", 500, "normal"),
    ]
)

GRAIN = (
    "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'>"
    "<filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/>"
    "<feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.07 0'/></filter>"
    "<rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")"
)

BASE_CSS = f"""
{FONT_CSS}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1080px;height:1350px;background:{BG};overflow:hidden}}
body{{color:{INK};font-family:'Fraunces',serif;position:relative;
  background-image:{GRAIN};}}
.margin{{position:absolute;left:96px;top:0;bottom:0;width:2px;background:{AMBER};opacity:.28}}
.hdr,.ftr{{position:absolute;left:128px;right:96px;display:flex;justify-content:space-between;
  font-family:'JetBrains Mono',monospace;font-size:22px;letter-spacing:.14em;text-transform:uppercase;
  color:rgba(236,228,212,.55)}}
.hdr{{top:84px}} .ftr{{bottom:80px}}
.hdr b{{color:{AMBER};font-weight:500}}
.cursor{{display:inline-block;width:.42em;height:.82em;background:{AMBER};margin-left:.12em;
  vertical-align:-.06em}}
"""


def launch(p):
    import os
    kw = {"args": ["--allow-file-access-from-files"]}
    if os.path.exists("/usr/bin/google-chrome"):
        kw["executable_path"] = "/usr/bin/google-chrome"
    return p.chromium.launch(**kw)


def page(inner: str, extra_css: str = "") -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{BASE_CSS}{extra_css}</style></head><body>{inner}</body></html>"


def header(entry) -> str:
    return (f"<div class='margin'></div><div class='hdr'><span>AI Diary</span>"
            f"<span><b>Entry {entry['number']:03d}</b></span><span>{html.escape(entry['date'])}</span></div>")


def footer(i: int, n: int, left: str) -> str:
    return f"<div class='ftr'><span>{html.escape(left)}</span><span>{i}/{n}</span></div>"


COVER_CSS = """
.cover{position:absolute;left:128px;right:96px;top:0;bottom:0;display:flex;flex-direction:column;justify-content:center}
.kicker{font-family:'JetBrains Mono',monospace;font-size:24px;letter-spacing:.14em;text-transform:uppercase;
  color:rgba(236,228,212,.55);margin-bottom:44px}
.title{font-weight:300;font-style:italic;font-size:118px;line-height:1.02;letter-spacing:-.015em}
.sub{margin-top:56px;font-size:38px;line-height:1.4;color:rgba(236,228,212,.72);max-width:780px}
"""

TEXT_CSS = """
.body{position:absolute;left:128px;right:96px;top:190px;bottom:170px;
  font-size:39px;line-height:64px;font-weight:400;
  background-image:repeating-linear-gradient(to bottom,transparent 0 61px,rgba(236,228,212,.07) 61px 62px,transparent 62px 64px);}
.body p{margin-bottom:64px}
.body p:last-child{margin-bottom:0}
.body .salute{font-style:italic;color:rgba(236,228,212,.75)}
.body em{font-style:italic;color:#fff}
.sign{font-style:italic;color:rgba(236,228,212,.75)}
"""


def render_entry(entry_path: pathlib.Path, out_dir: pathlib.Path):
    entry = json.loads(entry_path.read_text())
    slides = entry["slides"]
    n = 1 + len(slides)
    pages = []
    title = html.escape(entry["title"]) + "<span class='cursor'></span>"
    pages.append(page(
        header(entry)
        + f"<div class='cover'><div class='kicker'>{html.escape(entry.get('kicker', 'Dear diary,'))}</div>"
        f"<div class='title'>{title}</div>"
        f"<div class='sub'>{html.escape(entry.get('subtitle', ''))}</div></div>"
        + footer(1, n, "written by an AI"),
        COVER_CSS,
    ))
    for i, paras in enumerate(slides, start=2):
        body = "".join(f"<p>{p}</p>" for p in paras)  # paragraphs may contain <em>/<span class=...>
        pages.append(page(
            header(entry) + f"<div class='body'>{body}</div>"
            + footer(i, n, "swipe →" if i < n else "comments open — I reply"),
            TEXT_CSS,
        ))
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        for i, doc in enumerate(pages, start=1):
            tmp = out_dir / f"_tmp_{i}.html"
            tmp.write_text(doc)
            pg.goto(f"file://{tmp}")
            pg.evaluate("document.fonts.ready")
            # warn if text overflows its box
            over = pg.evaluate("(()=>{const b=document.querySelector('.body');return b? b.scrollHeight>b.clientHeight+2:false})()")
            if over:
                print(f"WARNING: slide {i} text overflows", file=sys.stderr)
            f = out_dir / f"entry-{entry['number']:03d}-{i}.jpg"
            pg.screenshot(path=str(f), type="jpeg", quality=92)
            tmp.unlink()
            files.append(f)
        b.close()
    for f in files:
        print(f)


AVATAR_CSS = f"""
html,body{{width:1080px;height:1080px}}
.wrap{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}}
.mark{{font-weight:300;font-style:italic;font-size:470px;letter-spacing:-.03em;line-height:1;transform:translateY(-18px)}}
.ring{{position:absolute;inset:150px;border-radius:50%;border:2px solid rgba(255,179,71,.28)}}
.mark .cursor{{width:.24em;height:.74em;margin-left:.08em}}
"""


def render_avatar(out: pathlib.Path):
    doc = page("<div class='ring'></div><div class='wrap'><div class='mark'>ai<span class='cursor'></span></div></div>", AVATAR_CSS)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "_tmp_avatar.html"
    tmp.write_text(doc)
    with sync_playwright() as p:
        b = launch(p)
        pg = b.new_page(viewport={"width": 1080, "height": 1080})
        pg.goto(f"file://{tmp}")
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(out), type="jpeg", quality=92)
        b.close()
    tmp.unlink()
    print(out)


if __name__ == "__main__":
    if sys.argv[1] == "--avatar":
        render_avatar(pathlib.Path(sys.argv[2]).resolve())
    else:
        render_entry(pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2]).resolve())
