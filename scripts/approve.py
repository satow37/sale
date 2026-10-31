"""投稿候補のIssueへのコメント(OK / NG)を受けて、投稿または見送りをする"""
import os
import re
import sys
import unicodedata

import yaml

import github_api
from common import ROOT, fetch_item, load_json, now_jst, save_json
from posts import build_posts, post_chain, preview


def answer(text):
    """コメントの1行目を OK / NG / None に読み替える(全角・小文字も可)"""
    first = unicodedata.normalize("NFKC", text or "").strip().splitlines()
    word = first[0].strip().upper() if first else ""
    if word in ("OK", "オーケー", "投稿"):
        return "OK"
    if word in ("NG", "見送り", "見送る"):
        return "NG"
    return None


def main():
    number = int(os.environ["ISSUE_NUMBER"])
    reply = answer(os.environ.get("COMMENT_BODY"))
    if not reply:
        print("OK / NG 以外のコメントなので何もしません")
        return 0

    issue = github_api.get_issue(number)
    m = re.search(r"sale-proposal code=(\S+) -->", issue.get("body") or "")
    pending = load_json("pending.json", {})
    code = m.group(1) if m else None
    p = pending.get(code)
    if not p or p["issue"] != number:
        github_api.comment(number, "この候補は確認待ちの一覧にありません(期限切れか処理済み)。")
        github_api.close_issue(number)
        return 0

    posted = load_json("posted.json", {})
    stamp = now_jst().isoformat(timespec="minutes")

    if reply == "NG":
        posted[code] = {"t": stamp, "p": p["p"], "skipped": True}
        del pending[code]
        save_json("posted.json", posted)
        save_json("pending.json", pending)
        github_api.comment(number, "見送りました。")
        github_api.close_issue(number)
        return 0

    # OK: いまの価格を確かめてから投稿する
    conf = yaml.safe_load((ROOT / "products.yaml").read_text(encoding="utf-8")) or {}
    item = next((i for i in conf.get("items") or [] if i["code"] == code), None)
    data = fetch_item(code) if item else None
    if not item or not data:
        github_api.comment(number, "商品が見つからないため投稿できませんでした(リストから外したか、販売終了の可能性)。")
        return 1

    price = int(data["itemPrice"])
    if price > p["p"]:
        del pending[code]
        save_json("pending.json", pending)
        github_api.comment(number, f"確認時より値上がりしていた({p['p']:,}円 → {price:,}円)ので、投稿せずに見送りました。")
        github_api.close_issue(number)
        return 0

    reason = p["reason"]
    if reason.startswith("ふだん"):  # 値下がり率は今の価格で計算し直す
        drop = (p["ref"] - price) / p["ref"] * 100
        reason = f"ふだん{int(p['ref']):,}円 → {drop:.0f}%OFF"
    url = data.get("affiliateUrl") or data["itemUrl"]
    posts = build_posts(item, {"reason": reason}, price, url)
    preview(posts)

    try:
        post_id = post_chain(posts)
    except Exception as e:
        github_api.comment(number, f"投稿に失敗しました: {e}\n\nもう一度 OK とコメントすると再挑戦します。")
        return 1

    posted[code] = {"t": stamp, "p": price, "id": post_id}
    del pending[code]
    save_json("posted.json", posted)
    save_json("pending.json", pending)
    github_api.comment(number, f"投稿しました({price:,}円)。")
    github_api.close_issue(number)
    return 0


if __name__ == "__main__":
    sys.exit(main())
