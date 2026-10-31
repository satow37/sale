"""投稿文の組み立てと、複数投稿をつなげて流す処理"""
import re
import time

from common import threads_post

LIMIT = 500  # Threads の1投稿の上限文字数
NOTE = "※価格は投稿時点。変動することがあります"


def split_text(text, limit=LIMIT):
    """長文を段落(空行)の切れ目で、limit 文字以内の投稿に分ける"""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        # 1段落が長すぎるときは文の切れ目でさらに分ける
        pieces = [p] if len(p) <= limit else [s for s in re.findall(r"[^。!?！？\n]*[。!?！？\n]?", p) if s]
        for i, piece in enumerate(pieces):
            sep = ("\n\n" if i == 0 else "") if cur else ""
            if len(cur) + len(sep) + len(piece) <= limit:
                cur += sep + piece
            else:
                if cur:
                    chunks.append(cur.strip())
                cur = piece[:limit]
    if cur.strip():
        chunks.append(cur.strip())
    return chunks


def pr_post(item, info, price, url, lead):
    """【PR】+ 一言 + 商品名・価格・リンク。500文字を超えるときは一言を削る"""
    tail = "\n".join(["", "", item["name"][:40], f"💰 {price:,}円({info['reason']})",
                      "", "▼楽天で見る", url, "", NOTE])
    head = "【PR】\n"
    lead = (lead or "").strip()
    room = LIMIT - len(head) - len(tail)
    if len(lead) > room:
        lead = lead[: room - 1] + "…"
    return head + lead + tail


def build_posts(item, info, price, url):
    """商品の投稿をつながった投稿のリストにする(1つ目が本投稿、2つ目以降は返信)

    story があれば: ストーリーを分割した投稿 → 最後に【PR】リンクの返信
    pain と solution があれば: 悩み → 【PR】+解決策+リンクの返信
    どちらもなければ: 【PR】+価格+リンクの1投稿
    """
    story = (item.get("story") or "").strip()
    if story:
        return split_text(story) + [pr_post(item, info, price, url, item.get("comment"))]
    pain = (item.get("pain") or "").strip()
    solution = (item.get("solution") or "").strip()
    if pain and solution:
        return [pain[:LIMIT], pr_post(item, info, price, url, solution)]
    lines = ["【PR】", f"{item['name'][:40]} が値下がり中", f"💰 {price:,}円({info['reason']})"]
    if item.get("comment"):
        lines.append(f"✔ {item['comment']}")
    lines += ["", "▼楽天で見る", url, "", NOTE]
    return ["\n".join(lines)[:LIMIT]]


def post_chain(posts):
    """1つ目を投稿し、残りを順に返信としてつなげる。最初の投稿IDを返す"""
    first_id = threads_post(posts[0])
    prev = first_id
    for text in posts[1:]:
        time.sleep(10)  # 公開直後は返信先として見つからないことがあるので少し待つ
        for attempt in range(2):
            try:
                prev = threads_post(text, reply_to_id=prev)
                break
            except Exception as e:
                print(f"⚠ 返信の投稿失敗({attempt + 1}回目): {e}")
                time.sleep(20)
        else:
            break  # つながりが切れるので、残りは出さない
    return first_id


def preview(posts):
    for i, text in enumerate(posts):
        label = "本投稿" if i == 0 else f"返信{i}"
        print(f"----- {label}({len(text)}文字) -----\n{text}")
