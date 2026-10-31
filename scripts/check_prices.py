"""価格を取得 → 買い時を判定 → 投稿候補をIssueで確認依頼 → セール情報ページを更新

実際の投稿は、Issueに OK とコメントしたときに approve.py が行う
"""
import os
import statistics
import sys
from datetime import datetime

import yaml

import github_api
from build_page import build_page
from common import ROOT, fetch_item, load_json, now_jst, save_json
from posts import build_posts, preview

DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"
HISTORY_KEEP_DAYS = 180


def parse_t(s):
    return datetime.fromisoformat(s)


def days_span(entries):
    if not entries:
        return 0
    ts = [parse_t(e["t"]) for e in entries]
    return (max(ts) - min(ts)).days


def evaluate(entries, price, threshold):
    """過去の記録と今の価格から、値下がり率と判定理由を返す"""
    now = now_jst()
    past30 = [e["p"] for e in entries if (now - parse_t(e["t"])).days <= 30]
    past90 = [e["p"] for e in entries if (now - parse_t(e["t"])).days <= 90]
    if not past30:
        return None
    ref = statistics.median(past30)  # 30日間の「ふだんの価格」
    drop = (ref - price) / ref * 100 if ref else 0
    reason = None
    if drop >= threshold:
        reason = f"ふだん{int(ref):,}円 → {drop:.0f}%OFF"
    elif past90 and price < min(past90) and days_span(entries) >= 14 and drop >= 5:
        reason = "過去90日の最安値を更新"
    return {"ref": ref, "drop": drop, "reason": reason}


def proposal_body(item, info, price, url, posts, expire_days):
    parts = []
    for i, text in enumerate(posts):
        label = "本投稿" if i == 0 else f"返信{i}"
        parts.append(f"**{label}**({len(text)}文字)\n\n```text\n{text}\n```")
    return "\n".join([
        f"<!-- sale-proposal code={item['code']} -->",
        f"## {item['name']} が買い時です",
        "",
        f"- いまの価格: **{price:,}円**({info['reason']})",
        f"- 商品ページ: {url}",
        "",
        "### 投稿する内容",
        "",
        "\n\n".join(parts),
        "",
        "### どうしますか?",
        "",
        "- 投稿する → このIssueに **OK** とコメント",
        f"- 見送る → **NG** とコメント(同じ商品は{item.get('cooldown', 7)}日間提案しません)",
        f"- {expire_days}日たっても返事がなければ自動で見送ります",
        "",
        "OKのときは価格をもう一度確認し、値上がりしていたら投稿しません。",
    ])


def expire_proposals(pending, now, expire_days):
    """返事がないまま期限が過ぎた投稿候補を閉じる"""
    for code, p in list(pending.items()):
        if (now - parse_t(p["t"])).days < expire_days:
            continue
        print(f"期限切れのため見送り: {code}(Issue #{p['issue']})")
        if DRY_RUN:
            continue
        try:
            github_api.comment(p["issue"], f"{expire_days}日たったので見送りました。")
            github_api.close_issue(p["issue"])
        except Exception as e:
            print(f"⚠ Issueを閉じられませんでした: {e}")
        del pending[code]


def main():
    conf = yaml.safe_load((ROOT / "products.yaml").read_text(encoding="utf-8")) or {}
    settings = conf.get("settings", {})
    items = conf.get("items") or []
    history = load_json("history.json", {})
    posted = load_json("posted.json", {})
    pending = load_json("pending.json", {})
    now = now_jst()
    stamp = now.isoformat(timespec="minutes")

    if not items:
        print("products.yaml に商品がまだ登録されていません。ページだけ更新します。")

    min_days = settings.get("min_history_days", 5)
    cooldown = settings.get("repost_cooldown_days", 7)
    expire_days = settings.get("proposal_expire_days", 2)
    expire_proposals(pending, now, expire_days)
    deals, rows = [], []

    for item in items:
        code = item["code"]
        try:
            data = fetch_item(code)
        except Exception as e:  # 1商品の失敗で全体を止めない
            print(f"⚠ {code}: {e}")
            continue
        if not data:
            print(f"⚠ {code}: 商品が見つかりません(販売終了の可能性)")
            continue

        price = int(data["itemPrice"])
        available = data.get("availability", 1) == 1
        entries = history.get(code, [])
        info = None
        if days_span(entries) >= min_days - 1:
            info = evaluate(entries, price, item.get("threshold", settings.get("drop_threshold", 15)))

        # 今回の価格を記録(古いものは削除)
        entries.append({"t": stamp, "p": price})
        history[code] = [e for e in entries if (now - parse_t(e["t"])).days <= HISTORY_KEEP_DAYS]

        url = data.get("affiliateUrl") or data["itemUrl"]
        imgs = data.get("mediumImageUrls") or []
        img = imgs[0] if imgs else ""
        if isinstance(img, dict):  # formatVersion=1 形式への保険
            img = img.get("imageUrl", "")

        row = {
            **item, "price": price, "url": url, "image": img,
            "available": available,
            "drop": round(info["drop"]) if info else None,
            "reason": info["reason"] if info else None,
            "shop": data.get("shopName", ""),
        }
        rows.append(row)

        if not (info and info["reason"] and available):
            continue
        if code in pending:  # 確認待ちの候補がある
            continue
        last = posted.get(code)
        if last:
            elapsed = (now - parse_t(last["t"])).days
            if elapsed < cooldown and price > last["p"] * 0.95:
                continue
        deals.append((info["drop"], item, info, price, url))

    deals.sort(key=lambda d: d[0], reverse=True)
    for drop, item, info, price, url in deals[: settings.get("max_posts_per_run", 2)]:
        posts = build_posts(item, info, price, url)
        print(f"===== 投稿候補: {item['name']} =====")
        preview(posts)
        if DRY_RUN:
            print("(テストモードのため確認依頼は出していません)")
            continue
        try:
            number = github_api.create_issue(
                f"投稿候補: {item['name']} {price:,}円",
                proposal_body({**item, "cooldown": cooldown}, info, price, url, posts, expire_days))
        except Exception as e:
            print(f"⚠ 確認依頼を出せませんでした: {e}")
            continue
        pending[item["code"]] = {"t": stamp, "p": price, "issue": number,
                                 "ref": info["ref"], "reason": info["reason"]}
        print(f"確認依頼を出しました: Issue #{number}")

    save_json("history.json", history)
    save_json("posted.json", posted)
    save_json("pending.json", pending)
    build_page(rows, settings, now)
    print(f"完了: {len(rows)}商品をチェック、買い時 {len(deals)}件、確認待ち {len(pending)}件")


if __name__ == "__main__":
    sys.exit(main())
