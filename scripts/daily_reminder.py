#!/usr/bin/env python3
"""日次アクションリスト生成: CRM + KPI進捗 + 投稿予定を統合して出力"""

import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_today():
    return datetime.now(JST).strftime("%Y-%m-%d")


def get_current_month():
    return datetime.now(JST).strftime("%Y-%m")


def load_actuals(month):
    """当月の実績データを読み込み（なければ空）"""
    path = os.path.join(BASE_DIR, "data", "kpi", "actuals", f"{month}.json")
    data = load_json(path)
    if data:
        return data.get("actions", {})
    return {}


def get_remaining_days(month):
    """当月の残り営業日数を概算"""
    now = datetime.now(JST)
    year, mon = int(month[:4]), int(month[5:7])
    if mon == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=JST)
    else:
        next_month = datetime(year, mon + 1, 1, tzinfo=JST)
    remaining = (next_month - now).days
    # 営業日は約70%（土日除外の概算）
    return max(1, int(remaining * 0.7))


def find_overdue_prospects(crm, today):
    """期日を過ぎたまたは今日期日のプロスペクトを抽出"""
    overdue = []
    for p in crm.get("prospects", []):
        action_date = p.get("next_action_date")
        if action_date and action_date <= today and p.get("next_action"):
            days_overdue = (
                datetime.strptime(today, "%Y-%m-%d")
                - datetime.strptime(action_date, "%Y-%m-%d")
            ).days
            overdue.append({**p, "days_overdue": days_overdue})
    return sorted(overdue, key=lambda x: (-x["days_overdue"], x.get("priority", "C")))


def find_approved_posts(today):
    """今日の投稿予定を確認"""
    approved_dir = os.path.join(BASE_DIR, "posts", "approved")
    posts = []
    if not os.path.exists(approved_dir):
        return posts
    for fname in os.listdir(approved_dir):
        if fname.startswith(today) and fname.endswith(".md"):
            posts.append(fname)
    return posts


def group_by_action(prospects):
    """アクション別にグループ化"""
    groups = {}
    for p in prospects:
        action = p.get("next_action", "不明")
        groups.setdefault(action, []).append(p)
    return groups


def generate_report(today, month, targets, actuals, crm, approved_posts):
    """Markdownレポートを生成"""
    lines = [f"# 本日のアクション ({today})\n"]

    # KPI進捗
    if targets:
        remaining_days = get_remaining_days(month)
        required = targets.get("required_actions", {})

        lines.append("## KPI進捗\n")
        lines.append(
            f"| 指標 | 月間目標 | 実績 | 達成率 | 残り{remaining_days}日 | 日次ペース |"
        )
        lines.append("|------|----------|------|--------|----------|-----------|")

        metrics = [
            ("コメント", "comments_on_targets", "comments_made"),
            ("つながり申請", "connection_requests", "connection_requests_sent"),
            ("DM送信", "dms_sent", "dms_sent"),
            ("商談", "goal_meetings", "meetings_booked"),
        ]

        for label, target_key, actual_key in metrics:
            if target_key == "goal_meetings":
                target_val = targets.get("goal_meetings", 0)
            else:
                target_val = required.get(target_key, 0)
            actual_val = actuals.get(actual_key, 0)
            rate = (actual_val / target_val * 100) if target_val > 0 else 0
            remaining = max(0, target_val - actual_val)
            daily_pace = (
                f"{remaining / remaining_days:.0f}件/日"
                if remaining_days > 0
                else "-"
            )
            lines.append(
                f"| {label} | {target_val} | {actual_val} | {rate:.0f}% | 残{remaining}件 | {daily_pace} |"
            )
        lines.append("")

    # タスク
    overdue = find_overdue_prospects(crm, today)
    if overdue:
        groups = group_by_action(overdue)
        priority_order = ["DM送信", "フォローアップ", "つながり申請", "投稿にコメント", "リマインド確認"]

        lines.append("## 今日のタスク\n")

        priority_labels = {0: "A", 1: "B", 2: "C"}
        for i, action in enumerate(priority_order):
            prospects_in_group = groups.get(action, [])
            if not prospects_in_group:
                continue
            plabel = priority_labels.get(i, "C")
            lines.append(f"### 優先度{plabel}: {action}（{len(prospects_in_group)}件）")
            for p in prospects_in_group:
                overdue_note = (
                    f"（{p['days_overdue']}日超過）" if p["days_overdue"] > 0 else ""
                )
                lines.append(
                    f"- **{p['name']}**（{p['company']}）{overdue_note} [{p['priority']}]"
                )
            lines.append("")
    else:
        lines.append("## 今日のタスク\n")
        lines.append("期日のタスクはありません。\n")

    # ファネルサマリ
    if crm.get("prospects"):
        lines.append("## ファネルサマリ\n")
        status_counts = {}
        for p in crm["prospects"]:
            s = p.get("status", "不明")
            status_counts[s] = status_counts.get(s, 0) + 1
        lines.append("| ステータス | 件数 |")
        lines.append("|---|---|")
        for s in crm.get("status_flow", []):
            count = status_counts.get(s, 0)
            if count > 0:
                lines.append(f"| {s} | {count} |")
        lines.append(f"| **合計** | **{len(crm['prospects'])}** |")
        lines.append("")

    # 投稿予定
    lines.append("## 投稿\n")
    if approved_posts:
        for post in approved_posts:
            theme = post.replace(today + "_", "").replace(".md", "")
            lines.append(f"- [ ] 本日の投稿: {theme}")
    else:
        lines.append("- 本日の投稿予定はありません")
    lines.append("")

    # 時間見積
    task_count = len(overdue) if overdue else 0
    estimated_min = min(30, 5 + task_count * 2)
    lines.append(f"---\n所要時間見積: 約{estimated_min}分\n")

    return "\n".join(lines)


def main():
    today = get_today()
    month = get_current_month()

    targets = load_json(os.path.join(BASE_DIR, "data", "kpi", "targets.json"))
    actuals = load_actuals(month)
    crm = load_json(os.path.join(BASE_DIR, "data", "crm", "prospects.json")) or {
        "prospects": []
    }
    approved_posts = find_approved_posts(today)

    report = generate_report(today, month, targets, actuals, crm, approved_posts)

    output_dir = os.path.join(BASE_DIR, "output", "daily")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{today}_actions.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n保存先: {output_path}")


if __name__ == "__main__":
    main()
