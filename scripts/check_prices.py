"""価格を取得 → 買い時を判定 → Threadsに投稿 → セール情報ページを更新"""
import os
import statistics
import sys
import time
from datetime import datetime

import yaml

from common import (ROOT, fetch_item, load_json, now_jst, save_json,
                    threads_post)
from build_page import build_page

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


def make_post(item, info, price, url):
    """1投稿版(pain/solution が未記入の商品用)"""
    name = item["name"][:40]
    lines = [
        "【PR】",
        f"{name} が値下がり中",
        f"💰 {price:,}円({info['reason']})",
    ]
    if item.get("comment"):
        lines.append(f"✔ {item['comment']}")
    lines += ["", "▼楽天で見る", url, "", "※価格は投稿時点。変動することがあります"]
    text = "\n".join(lines)
    return text[:500]


def is_two_step(item):
    return bool((item.get("pain") or "").strip() and (item.get("solution") or "").strip())


def make_main_post(item):
    """2段構成の本投稿: 悩みの場面と問いかけだけ(リンクなし)"""
    return item["pain"].strip()[:500]


def make_reply_post(item, info, price, url):
    """2段構成の返信: 解決できる理由 + セール価格 + 【PR】リンク"""
    name = item["name"][:40]
    tail = "\n".join([
        "",
        "",
        f"{name}",
        f"💰 {price:,}円({info['reason']})",
        "",
        "▼楽天で見る",
        url,
        "",
        "※価格は投稿時点。変動することがあります",
    ])
    head = "【PR】\n"
    # 500文字を超えるときは solution 側を削って、価格とリンクは必ず残す
    room = 500 - len(head) - len(tail)
    solution = item["solution"].strip()
    if len(solution) > room:
        solution = solution[: room - 1] + "…"
    return head + solution + tail


def publish(item, info, price, url):
    """投稿して、最初の投稿IDを返す。テストモードなら None"""
    if is_two_step(item):
        posts = [make_main_post(item), make_reply_post(item, info, price, url)]
    else:
        posts = [make_post(item, info, price, url)]
    for i, text in enumerate(posts):
        label = "本投稿" if i == 0 else "返信"
        print(f"----- {label} -----\n{text}")
    if DRY_RUN:
        print("(テストモードのため投稿していません)")
        return None

    first_id = threads_post(posts[0])
    if len(posts) > 1:
        time.sleep(10)  # 公開直後は返信先として見つからないことがあるので少し待つ
        for attempt in range(2):
            try:
                threads_post(posts[1], reply_to_id=first_id)
                break
            except Exception as e:
                print(f"⚠ 返信の投稿失敗({attempt + 1}回目): {e}")
                time.sleep(20)
    return first_id


def main():
    conf = yaml.safe_load((ROOT / "products.yaml").read_text(encoding="utf-8")) or {}
    settings = conf.get("settings", {})
    items = conf.get("items") or []
    history = load_json("history.json", {})
    posted = load_json("posted.json", {})
    now = now_jst()
    stamp = now.isoformat(timespec="minutes")

    if not items:
        print("products.yaml に商品がまだ登録されていません。ページだけ更新します。")

    min_days = settings.get("min_history_days", 5)
    cooldown = settings.get("repost_cooldown_days", 7)
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
        last = posted.get(code)
        if last:
            elapsed = (now - parse_t(last["t"])).days
            if elapsed < cooldown and price > last["p"] * 0.95:
                continue
        deals.append((info["drop"], item, info, price, url))

    deals.sort(key=lambda d: d[0], reverse=True)
    for drop, item, info, price, url in deals[: settings.get("max_posts_per_run", 2)]:
        try:
            post_id = publish(item, info, price, url)
        except Exception as e:
            print(f"⚠ 投稿失敗: {e}")
            continue
        if post_id:
            # 本投稿が出ていれば記録する(返信だけ失敗しても同じ悩みを連投しないため)
            posted[item["code"]] = {"t": stamp, "p": price, "id": post_id}

    save_json("history.json", history)
    save_json("posted.json", posted)
    build_page(rows, settings, now)
    print(f"完了: {len(rows)}商品をチェック、買い時 {len(deals)}件")


if __name__ == "__main__":
    sys.exit(main())
