#!/usr/bin/env python3
# 清单驱动的静态站点生成器。读取 build/pages.json + build/articles/<slug>.md，
# 输出到仓库根目录（GitHub Pages 直接服务）。新增文章只需改 pages.json + 加 md。
import os, re, json, html, markdown, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)            # 仓库根 = build 的上一级
ART  = os.path.join(HERE, "articles")
CFG  = json.load(open(os.path.join(HERE, "pages.json"), encoding="utf-8"))

BASE, SITE, KF = CFG["base"], CFG["site"], CFG["kf"]
GSC  = CFG.get("google_site_verification", "")
PAGES = CFG["pages"]

def gsc_meta():
    return f'<meta name="google-site-verification" content="{GSC}">\n' if GSC else ""

def nav_html(cur):
    out = []
    for p in PAGES:
        url = "/" if p["slug"] == "" else f"/{p['slug']}/"
        cls = ' class="active"' if p["slug"] == cur else ""
        out.append(f'<a href="{url}"{cls}>{p["nav"]}</a>')
    return "\n".join(out)

def shell(p, body):
    canon = BASE + ("/" if p["slug"] == "" else f"/{p['slug']}/")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{gsc_meta()}<title>{html.escape(p['title'])}</title>
<meta name="description" content="{html.escape(p['desc'])}">
<link rel="canonical" href="{canon}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{html.escape(p['title'])}">
<meta property="og:description" content="{html.escape(p['desc'])}">
<meta property="og:url" content="{canon}">
<meta property="og:site_name" content="{SITE}">
<meta property="og:image" content="{KF}/logo.png">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header class="site-header">
  <a class="brand" href="/">King<span>Flow</span></a>
  <nav class="topnav">{nav_html(p['slug'])}</nav>
  <a class="cta" href="{KF}" rel="noopener">前往官网 →</a>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  <p><strong>KingFlow</strong> · 国内直连、稳定低延迟的 Claude / GPT API 中转平台</p>
  <p>官网：<a href="{KF}" rel="noopener">www.kingflow.ai</a> ｜ 支持 Claude Code · OpenAI Codex · 全系 Claude / GPT 模型</p>
  <p class="muted">© 2026 KingFlow. 本站为 KingFlow 中转方案与配置教程合集。</p>
</footer>
</body>
</html>
"""

def md_to_html(slug):
    raw = open(os.path.join(ART, slug + ".md"), encoding="utf-8").read()
    h1, out = "", []
    for ln in raw.splitlines():
        if not h1 and ln.startswith("# "):
            h1 = ln[2:].strip(); continue
        out.append(ln)
    body_md = re.sub(r'<img[^>]*logo\.png[^>]*>', '', "\n".join(out))
    return h1, markdown.markdown(body_md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

def home_body():
    cards = []
    for p in PAGES:
        if p["slug"] == "": continue
        cards.append(f'<a class="card" href="/{p["slug"]}/">\n  <h3>{html.escape(p["nav"])}</h3>\n  <p>{html.escape(p["desc"])}</p>\n  <span class="more">阅读 →</span>\n</a>')
    return f"""<section class="hero">
  <h1>KingFlow — 国内直连的 Claude / GPT API 中转站</h1>
  <p class="lead">无需魔法网络、一行配置即用，支持 Claude Code、OpenAI Codex 与全系 Claude / GPT 模型。低延迟、稳定、按量计费。</p>
  <div class="hero-cta">
    <a class="btn primary" href="{KF}" rel="noopener">立即使用 KingFlow</a>
    <a class="btn" href="/claude-api/">了解 Claude 中转站</a>
  </div>
</section>
<section class="grid">
{''.join(cards)}
</section>"""

urls = []
for p in PAGES:
    d = ROOT if p["slug"] == "" else os.path.join(ROOT, p["slug"])
    os.makedirs(d, exist_ok=True)
    if p["slug"] == "":
        body = home_body()
    else:
        h1, htmlb = md_to_html(p["slug"])
        body = f'<article class="post">\n<h1>{html.escape(h1)}</h1>\n{htmlb}\n</article>'
    open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(shell(p, body))
    urls.append(BASE + ("/" if p["slug"] == "" else f"/{p['slug']}/"))

# style.css -> 根
import shutil
shutil.copyfile(os.path.join(HERE, "style.css"), os.path.join(ROOT, "style.css"))
# sitemap / robots / nojekyll
today = datetime.date.today().isoformat()
sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
for u in urls:
    sm += f'  <url><loc>{u}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>{"1.0" if u.rstrip("/")==BASE else "0.8"}</priority></url>\n'
sm += "</urlset>\n"
open(os.path.join(ROOT, "sitemap.xml"), "w").write(sm)
open(os.path.join(ROOT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
open(os.path.join(ROOT, ".nojekyll"), "w").write("")
print(f"generated {len(PAGES)} pages, GSC={'on' if GSC else 'off'}")
print("\n".join(urls))
