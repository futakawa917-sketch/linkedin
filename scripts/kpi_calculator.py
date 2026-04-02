#!/usr/bin/env python3
"""KPI逆算エンジン: 月間商談目標から必要行動量を自動算出する"""

import json
import math
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_conversion_rates():
    """実績ベースの転換率があればそちらを優先、なければデフォルト値を使用"""
    defaults_path = os.path.join(BASE_DIR, "config", "kpi_defaults.json")
    actuals_path = os.path.join(BASE_DIR, "data", "conversion_rates.json")

    defaults = load_json(defaults_path)
    default_rates = {k: v["value"] for k, v in defaults["rates"].items()}

    rate_source = "default"

    if os.path.exists(actuals_path):
        actuals = load_json(actuals_path)
        actual_rates = actuals.get("rates", {})
        for key, info in actual_rates.items():
            if info.get("confidence") in ("medium", "high"):
                default_rates[key] = info["value"]
                rate_source = "mixed"
        if all(
            actual_rates.get(k, {}).get("confidence") in ("medium", "high")
            for k in default_rates
        ):
            rate_source = "calculated"

    return default_rates, rate_source


def calculate_kpi(goal_meetings, working_days=22):
    """商談目標から必要行動量を逆算"""
    rates, rate_source = get_conversion_rates()

    # ファネル逆算
    dms_needed = math.ceil(goal_meetings / rates["dm_to_meeting"])
    approvals_needed = math.ceil(dms_needed / rates["approved_to_dm"])
    requests_needed = math.ceil(approvals_needed / rates["request_to_approved"])
    comments_needed = math.ceil(requests_needed / rates["comment_to_request"])
    target_list_size = math.ceil(comments_needed / rates["target_to_comment"])

    # 投稿数（設定から取得）
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    posts_per_week = settings["accounts"]["personal"]["posts_per_week"]
    company_posts_per_week = settings["accounts"]["company"]["posts_per_week"]
    posts_personal = posts_per_week * 4
    posts_company = company_posts_per_week * 4

    # 日次ブレークダウン
    daily_comments = math.ceil(comments_needed / working_days)
    daily_requests = math.ceil(requests_needed / working_days)
    daily_dms = math.ceil(dms_needed / working_days)

    now = datetime.now(JST)

    result = {
        "month": now.strftime("%Y-%m"),
        "goal_meetings": goal_meetings,
        "calculated_at": now.isoformat(),
        "conversion_rates": rates,
        "required_actions": {
            "dms_sent": dms_needed,
            "connections_approved": approvals_needed,
            "connection_requests": requests_needed,
            "comments_on_targets": comments_needed,
            "target_list_size": target_list_size,
            "posts_personal": posts_personal,
            "posts_company": posts_company,
        },
        "daily_actions": {
            "comments": daily_comments,
            "connection_requests": daily_requests,
            "dms": daily_dms,
            "post_days_per_week": posts_per_week,
        },
        "rate_source": rate_source,
    }

    return result


def print_summary(result):
    """KPI計算結果をわかりやすく表示"""
    print(f"\n{'='*50}")
    print(f"  LinkedIn BtoB KPI逆算結果 ({result['month']})")
    print(f"{'='*50}")
    print(f"\n  商談目標: {result['goal_meetings']}件/月")
    print(f"  転換率ソース: {result['rate_source']}")

    print(f"\n{'─'*50}")
    print("  ファネル必要数（月間）")
    print(f"{'─'*50}")
    actions = result["required_actions"]
    print(f"  ターゲットリスト :  {actions['target_list_size']:>6}人")
    print(f"  コメント         :  {actions['comments_on_targets']:>6}件")
    print(f"  つながり申請     :  {actions['connection_requests']:>6}件")
    print(f"  承認見込み       :  {actions['connections_approved']:>6}件")
    print(f"  DM送信           :  {actions['dms_sent']:>6}件")
    print(f"  → 商談獲得       :  {result['goal_meetings']:>6}件")

    print(f"\n{'─'*50}")
    print("  日次アクション目安")
    print(f"{'─'*50}")
    daily = result["daily_actions"]
    print(f"  コメント         :  {daily['comments']:>3}件/日")
    print(f"  つながり申請     :  {daily['connection_requests']:>3}件/日")
    print(f"  DM送信           :  {daily['dms']:>3}件/日")
    print(f"  投稿             :  週{daily['post_days_per_week']}回（月/水/金）")

    print(f"\n{'─'*50}")
    print("  投稿本数（月間）")
    print(f"{'─'*50}")
    print(f"  個人アカウント   :  {actions['posts_personal']:>3}本")
    print(f"  企業アカウント   :  {actions['posts_company']:>3}本")

    print(f"\n{'─'*50}")
    print("  使用転換率")
    print(f"{'─'*50}")
    rates = result["conversion_rates"]
    labels = {
        "target_to_comment": "ターゲット→コメント",
        "comment_to_request": "コメント→申請",
        "request_to_approved": "申請→承認",
        "approved_to_dm": "承認→DM",
        "dm_to_meeting": "DM→商談",
    }
    for key, label in labels.items():
        print(f"  {label:<20s}:  {rates[key]*100:>5.1f}%")

    print(f"\n{'='*50}\n")


def main():
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    goal = settings["kpi"]["monthly_meeting_goal"]
    working_days = settings["kpi"]["working_days_per_month"]

    result = calculate_kpi(goal, working_days)

    targets_path = os.path.join(BASE_DIR, "data", "kpi", "targets.json")
    save_json(targets_path, result)

    print_summary(result)
    print(f"  保存先: {targets_path}")


if __name__ == "__main__":
    main()
