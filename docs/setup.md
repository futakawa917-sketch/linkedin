# セットアップガイド

## 1. GitHubリポジトリ設定

```bash
cd snshack-linkedin
git remote set-url origin https://github.com/futakawa917-sketch/linkedin.git
git add -A
git commit -m "Initial setup: LinkedIn BtoB automation system"
git push -u origin main
```

## 2. GitHub Secrets設定

リポジトリの Settings → Secrets and variables → Actions で以下を設定:

| Secret名 | 値 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic APIキー |

## 3. 初期設定のカスタマイズ

### `config/settings.json`
- `kpi.monthly_meeting_goal`: 月間商談目標件数を設定
- `target.industry`: ターゲット業界を編集
- `target.pain_points`: ターゲットのペインを編集

### `config/kpi_defaults.json`
- 転換率のデフォルト値を必要に応じて調整

## 4. KPI初回計算

```bash
python scripts/kpi_calculator.py
```

## 5. GitHub Actions確認

以下のワークフローが自動で動作します:

| ワークフロー | スケジュール | 内容 |
|---|---|---|
| daily-reminder | 毎朝9:00 JST | 日次アクションリスト生成 |
| weekly-post-generation | 毎週月曜7:00 JST | 週次投稿ドラフト生成（PR作成） |
| monthly-kpi-update | 毎月1日10:00 JST | 転換率再計算＋KPI目標更新 |

各ワークフローは手動実行（workflow_dispatch）も可能です。
