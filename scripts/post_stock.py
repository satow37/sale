"""ストック(stock.yaml)から悩みだけの投稿を1本流す。その日にセール投稿があればお休み"""
import hashlib
import os
import sys
from datetime import datetime

import yaml

from common import ROOT, load_json, now_jst, save_json
from posts import post_chain, preview, split_text

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"


def post_key(text):
    return hashlib.sha1(text.strip().encode("utf-8")).hexdigest()[:12]


def posted_sale_today(now):
    posted = load_json("posted.json", {})
    return any(datetime.fromisoformat(v["t"]).date() == now.date()
               for v in posted.values() if not v.get("skipped"))


def main():
    now = now_jst()
    if posted_sale_today(now):
        print("今日はセール投稿があったので、悩み投稿はお休みします。")
        return 0

    conf = yaml.safe_load((ROOT / "stock.yaml").read_text(encoding="utf-8")) or {}
    posts = [p for p in (conf.get("posts") or []) if (p.get("text") or "").strip()]
    done = load_json("stock_posted.json", {})

    todo = [p for p in posts if post_key(p["text"]) not in done]
    print(f"ストック: 全{len(posts)}本 / 未投稿{len(todo)}本")
    if not todo:
        print("⚠ 未投稿のストックがありません。stock.yaml に書き足してください。")
        return 0

    text = todo[0]["text"].strip()
    chain = split_text(text)  # 500文字を超える分は返信につなげる
    preview(chain)
    if DRY_RUN:
        print("(テストモードのため投稿していません)")
        return 0

    post_id = post_chain(chain)
    done[post_key(text)] = {"t": now.isoformat(timespec="minutes"), "id": post_id}
    save_json("stock_posted.json", done)
    if len(todo) <= 3:
        print(f"⚠ 残りのストックが{len(todo) - 1}本です。書き足してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
