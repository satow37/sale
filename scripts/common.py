"""共通処理: 楽天API・Threads API・データ保存"""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

RAKUTEN_ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
# 楽天に登録した「許可されたWebサイト」と同じドメイン
SITE_URL = os.environ.get("SITE_URL", "https://satow37.github.io/")

THREADS_BASE = "https://graph.threads.net/v1.0"


def now_jst():
    return datetime.now(JST)


# ---------- 楽天API ----------
def rakuten_search(**params):
    """楽天市場商品検索API(新方式)。Referer/Originヘッダーが必須。"""
    query = {
        "applicationId": os.environ["RAKUTEN_APP_ID"],
        "accessKey": os.environ["RAKUTEN_ACCESS_KEY"],
        "format": "json",
        "formatVersion": 2,
    }
    aff = os.environ.get("RAKUTEN_AFFILIATE_ID")
    if aff:
        query["affiliateId"] = aff
    query.update(params)
    headers = {"Referer": SITE_URL, "Origin": SITE_URL.rstrip("/")}

    for attempt in range(3):
        res = requests.get(RAKUTEN_ENDPOINT, params=query, headers=headers, timeout=20)
        if res.status_code == 429:  # 叩きすぎ
            time.sleep(3 * (attempt + 1))
            continue
        if not res.ok:
            raise RuntimeError(f"楽天APIエラー {res.status_code}: {res.text[:300]}")
        time.sleep(1.1)  # 1秒1リクエストの目安を守る
        return res.json().get("Items", [])
    raise RuntimeError("楽天APIが混雑しています(429)")


def fetch_item(item_code):
    items = rakuten_search(itemCode=item_code, hits=1)
    return items[0] if items else None


# ---------- Threads API ----------
def threads_post(text, reply_to_id=None):
    """テキストを投稿して投稿IDを返す。reply_to_id を渡すとその投稿への返信になる"""
    token = os.environ["THREADS_ACCESS_TOKEN"]
    data = {"media_type": "TEXT", "text": text, "access_token": token}
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    r = requests.post(f"{THREADS_BASE}/me/threads", data=data, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Threads下書き作成エラー {r.status_code}: {r.text[:300]}")
    creation_id = r.json()["id"]
    time.sleep(5)  # 公式推奨: 作成から公開まで少し待つ
    r = requests.post(
        f"{THREADS_BASE}/me/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    if not r.ok:
        raise RuntimeError(f"Threads公開エラー {r.status_code}: {r.text[:300]}")
    return r.json().get("id")


# ---------- データ保存 ----------
def load_json(name, default):
    path = DATA_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(name, obj):
    DATA_DIR.mkdir(exist_ok=True)
    (DATA_DIR / name).write_text(
        json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8"
    )
