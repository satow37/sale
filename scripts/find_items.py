"""キーワードで楽天の商品候補を探し、products.yamlに貼れる形で一覧表示"""
import os
import sys

from common import rakuten_search

SORTS = {"レビュー数順": "-reviewCount", "安い順": "+itemPrice", "標準": "standard"}


def main():
    keyword = os.environ.get("KEYWORD") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not keyword:
        print("キーワードを指定してください")
        return 1
    sort = SORTS.get(os.environ.get("SORT", "レビュー数順"), "-reviewCount")
    min_price = os.environ.get("MIN_PRICE")
    params = {"keyword": keyword, "hits": 20, "sort": sort, "availability": 1}
    if min_price:
        params["minPrice"] = int(min_price)
    items = rakuten_search(**params)

    lines = [f"## 「{keyword}」の候補 {len(items)}件", "",
             "| 商品名 | 価格 | レビュー | ショップ | itemCode |",
             "|---|---|---|---|---|"]
    for it in items:
        name = it["itemName"].replace("|", " ")[:50]
        lines.append(
            f"| [{name}]({it['itemUrl']}) | {int(it['itemPrice']):,}円 | "
            f"★{it.get('reviewAverage', 0)} ({it.get('reviewCount', 0)}件) | "
            f"{it.get('shopName', '')} | `{it['itemCode']}` |"
        )
    lines += ["", "気に入った商品の itemCode を products.yaml の code に貼ってください。"]
    out = "\n".join(lines)
    print(out)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(out + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
