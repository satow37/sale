# 暮らしの家電セール速報 bot

楽天の価格を1日3回チェックし、登録した商品が値下がりしたときだけ Threads(@osatow37)に自動投稿します。
あわせてセール情報ページ(https://satow37.github.io/sale/)を自動更新します。

## しくみ

```
products.yaml(自分で選んだ商品)
   ↓ 1日3回(8時・12時・20時)
楽天APIで価格取得 → data/history.json に記録
   ↓
30日間のふだんの価格より15%以上安い / 90日最安値 → 「買い時」
   ↓
Threadsに投稿(1回最大2件・同じ商品は7日間再投稿しない)
  pain と solution を書いた商品 → 本投稿(悩み・リンクなし)+ 返信(解決策・価格・【PR】リンク)
  書いていない商品        → 1投稿(【PR】・価格・リンク)
docs/index.html を更新(GitHub Pagesで公開)

stock.yaml(書き溜めた悩み投稿)
   ↓ 毎日21時
その日にセール投稿がなければ、未投稿のものを上から1本投稿(リンクなし)
```

## 初回セットアップ

### 1. Secrets(鍵の保管場所)を登録
リポジトリの Settings → Secrets and variables → Actions → **New repository secret** で次の5つを登録します。

| 名前 | 中身 |
|---|---|
| `RAKUTEN_APP_ID` | Rakuten Developers のアプリID |
| `RAKUTEN_ACCESS_KEY` | 同じくアクセスキー(pk_で始まる) |
| `RAKUTEN_AFFILIATE_ID` | 楽天アフィリエイトID |
| `THREADS_ACCESS_TOKEN` | Threadsのアクセストークン |
| `GH_PAT` | トークン自動更新用のGitHubトークン(下記) |

**GH_PAT の作り方**:GitHub右上アイコン → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
- Repository access: Only select repositories → `sale`
- Permissions → Repository permissions → **Secrets: Read and write**
- 有効期限は最長(1年)に。期限前に作り直してください。

### 2. GitHub Pages を有効化
Settings → Pages → Source: **Deploy from a branch** / Branch: `main` / フォルダ: `/docs` → Save

### 3. 動作テスト
1. Actions → 「商品候補を探す」→ Run workflow → キーワードに「電気ケトル」→ 実行。結果画面に候補一覧が出れば楽天APIはOK。
2. 気に入った商品の itemCode を `products.yaml` に追記(GitHub上で鉛筆アイコンから編集できます)。
3. Actions → 「価格チェックと投稿」→ Run workflow(テストモードにチェックのまま)→ 実行。
4. `stock.yaml` に悩み投稿を書いて、Actions → 「悩み投稿」→ Run workflow(テストモードのまま)→ 実行。ログに投稿文が出ればOK。

### 4. 本番開始
Settings → Secrets and variables → Actions → **Variables** タブ → New repository variable
- 名前 `LIVE_MODE` / 値 `true`

これで定期実行が実際に投稿するようになります。止めたいときは `false` に。

## 注意
- 値下がり判定には5日ほど価格の記録が必要です。始めてすぐは投稿されません。
- 投稿・ページには【PR】表記が入ります(ステマ規制対応)。消さないでください。
- 鍵(Secrets)の中身はチャットやファイルに書かないこと。
