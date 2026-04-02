# 日次ワークフロー（30分）

## 毎朝のルーティン

### 1. アクションリストを確認（2分）
`output/daily/` に自動生成されたアクションリストを確認。
GitHub上で確認するか、ローカルでpullして確認。

### 2. コメント活動（15分）
- ターゲットリストの見込み客のLinkedIn投稿にコメント
- 1コメント3行以上、具体的な内容で
- 目安: 14件/日

### 3. つながり申請（5分）
- コメントで反応があった相手に申請を送信
- 申請メッセージは短く（「コメントでやりとりさせていただきました。つながりお願いします」程度）
- 目安: 7件/日

### 4. DM送信（5分）
- 承認済みのリードにDMを送信
- `python scripts/update_prospect.py` のDMテンプレート生成機能を活用
- 目安: 2件/日

### 5. CRM更新（3分）
```bash
# ステータス更新の例
python scripts/update_prospect.py status p001 --status "コメント済" --note "AI活用投稿にコメント"
python scripts/update_prospect.py status p003 --status "承認済" --note ""
```

## 週次タスク

### 月曜: 投稿レビュー
- GitHub PRに自動生成された投稿ドラフトをレビュー
- 必要に応じて編集
- マージ = 承認

### 金曜: 実績更新
```bash
# 当月の実績を手動更新
# data/kpi/actuals/YYYY-MM.json を編集
# actions: comments_made, connection_requests_sent, dms_sent, meetings_booked
```

## 月次タスク

### 月初: 振り返り＋設定
1. LinkedInからアナリティクスCSVをエクスポート
2. `python scripts/import_analytics.py path/to/csv` で取込
3. KPIの自動更新を確認（GitHub Actionsで月初に実行）
4. 必要に応じて `config/settings.json` の目標値を調整

### ターゲットリスト追加
```bash
python scripts/update_prospect.py add \
  --name "名前" \
  --company "会社名" \
  --title "役職" \
  --industry "業界" \
  --url "https://linkedin.com/in/xxx" \
  --tags "タグ1,タグ2" \
  --pain "ペイン1,ペイン2" \
  --priority A
```

## コマンドリファレンス

| コマンド | 用途 |
|---|---|
| `python scripts/kpi_calculator.py` | KPI逆算を再実行 |
| `python scripts/update_prospect.py add ...` | リード追加 |
| `python scripts/update_prospect.py status ID --status "ステータス"` | ステータス更新 |
| `python scripts/update_prospect.py list` | リード一覧 |
| `python scripts/update_prospect.py list --status "承認済"` | フィルタ一覧 |
| `python scripts/update_prospect.py show ID` | リード詳細 |
| `python scripts/daily_reminder.py` | アクションリスト手動生成 |
| `python scripts/generate_posts.py` | 投稿ドラフト手動生成 |
| `python scripts/import_analytics.py CSV` | 分析CSV取込 |
| `python scripts/update_conversion_rates.py` | 転換率再計算 |
