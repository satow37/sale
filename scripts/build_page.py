"""セール情報ページ(docs/index.html)を生成"""
from html import escape

from common import DOCS_DIR


def card(r):
    badge = ""
    if r.get("reason"):
        badge = f'<span class="badge">{escape(r["reason"])}</span>'
    soldout = '<span class="soldout">在庫切れ</span>' if not r["available"] else ""
    img = f'<img src="{escape(r["image"])}" alt="" loading="lazy">' if r["image"] else '<div class="noimg"></div>'
    comment = f'<p class="comment">{escape(r.get("comment", ""))}</p>' if r.get("comment") else ""
    return f"""
<a class="card" href="{escape(r['url'])}" target="_blank" rel="sponsored noopener" data-target="{escape(r.get('target','共通'))}">
  {img}
  <div class="body">
    <div class="meta">{escape(r.get('target','共通'))} ・ {escape(r.get('category',''))}</div>
    <h3>{escape(r['name'])}</h3>
    {comment}
    <div class="price">{r['price']:,}<small>円</small> {badge}{soldout}</div>
  </div>
</a>"""


def build_page(rows, settings, now):
    deals = sorted([r for r in rows if r.get("reason") and r["available"]],
                   key=lambda r: r.get("drop") or 0, reverse=True)
    others = [r for r in rows if r not in deals]
    targets = sorted({r.get("target", "共通") for r in rows})
    chips = "".join(f'<button data-f="{escape(t)}">{escape(t)}</button>' for t in targets)
    deals_html = "".join(card(r) for r in deals) or '<p class="empty">いまは大きな値下がりはありません。毎日チェックしています。</p>'
    others_html = "".join(card(r) for r in others) or '<p class="empty">準備中です。</p>'
    account = escape(settings.get("account_name", ""))

    html = f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>暮らしの家電セール速報</title>
<meta name="description" content="一人暮らし・家族暮らしに本当に必要な家電・ガジェットが値下がりしたタイミングだけをお知らせします。">
<style>
:root{{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1b;--sub:#6b6a66;--accent:#d2421f;--line:#e4e1d9}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141413;--card:#1f1f1d;--ink:#f1efe8;--sub:#a3a199;--accent:#ff7a52;--line:#33322f}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;line-height:1.6}}
header,main,footer{{max-width:880px;margin:0 auto;padding:0 16px}}
header{{padding-top:32px}}h1{{font-size:1.6rem;margin:0}}.lead{{color:var(--sub);margin:.3em 0 0}}
.pr{{font-size:.8rem;color:var(--sub);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:16px 0}}
h2{{font-size:1.1rem;margin:28px 0 12px;border-left:4px solid var(--accent);padding-left:8px}}
.chips{{display:flex;gap:8px;flex-wrap:wrap}}.chips button{{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:99px;padding:4px 14px;cursor:pointer}}
.chips button.on{{background:var(--ink);color:var(--bg)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}}
.card{{display:flex;gap:12px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;color:inherit;text-decoration:none}}
.card:hover{{border-color:var(--accent)}}.card img,.noimg{{width:84px;height:84px;object-fit:contain;border-radius:8px;background:#fff;flex:none}}
.meta{{font-size:.72rem;color:var(--sub)}}h3{{font-size:.95rem;margin:2px 0}}.comment{{font-size:.8rem;color:var(--sub);margin:2px 0}}
.price{{font-weight:700;font-size:1.1rem}}.price small{{font-size:.75rem}}
.badge{{display:inline-block;font-size:.7rem;background:var(--accent);color:#fff;border-radius:6px;padding:1px 6px;margin-left:4px;vertical-align:middle}}
.soldout{{font-size:.7rem;color:var(--sub);margin-left:4px}}.empty{{color:var(--sub)}}
footer{{font-size:.75rem;color:var(--sub);padding:32px 16px}}footer a{{color:var(--sub)}}
</style></head><body>
<header>
<h1>暮らしの家電セール速報</h1>
<p class="lead">一人暮らし・家族暮らしに本当に必要なものが、安くなったときだけ。</p>
<div class="pr">【PR】このページは楽天アフィリエイトを利用しています。リンク先での購入により運営者に報酬が発生することがあります。価格は {now:%Y年%m月%d日 %H:%M} 時点のもので、変動する場合があります。</div>
<div class="chips"><button class="on" data-f="">すべて</button>{chips}</div>
</header>
<main>
<h2>🔥 いまが買い時</h2><div class="grid">{deals_html}</div>
<h2>チェック中の商品</h2><div class="grid">{others_html}</div>
</main>
<footer>
<p>最新のセール情報は Threads <a href="https://www.threads.com/@{account}" target="_blank" rel="noopener">@{account}</a> でお知らせしています。</p>
<p><a href="https://webservice.rakuten.co.jp/" target="_blank" rel="noopener">Supported by Rakuten Developers</a></p>
</footer>
<script>
document.querySelectorAll('.chips button').forEach(b=>b.onclick=()=>{{
 document.querySelectorAll('.chips button').forEach(x=>x.classList.toggle('on',x===b));
 const f=b.dataset.f;document.querySelectorAll('.card').forEach(c=>c.style.display=(!f||c.dataset.target===f)?'':'none');
}});
</script>
</body></html>"""
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
