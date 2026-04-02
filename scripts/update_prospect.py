#!/usr/bin/env python3
"""ターゲットリストCRM更新CLI

使い方:
  # 新規追加
  python scripts/update_prospect.py add --name "田中太郎" --company "株式会社ABC" \
    --title "代表取締役" --industry "IT・SaaS" --url "https://linkedin.com/in/tanaka" \
    --tags "SaaS,経営者" --pain "SNS集客の始め方がわからない"

  # ステータス更新
  python scripts/update_prospect.py status p001 --status "コメント済" --note "AI活用の投稿にコメント"

  # 一覧表示
  python scripts/update_prospect.py list [--status "承認済"]

  # 詳細表示
  python scripts/update_prospect.py show p001
"""

import argparse
import json
import os
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRM_PATH = os.path.join(BASE_DIR, "data", "crm", "prospects.json")


def load_crm():
    with open(CRM_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_crm(data):
    with open(CRM_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_id(prospects):
    if not prospects:
        return "p001"
    nums = [int(p["id"][1:]) for p in prospects if p["id"].startswith("p")]
    return f"p{max(nums) + 1:03d}"


def calc_next_action_date(status, last_date, timing_rules):
    rule = timing_rules.get(status)
    if not rule:
        return None
    last = datetime.strptime(last_date, "%Y-%m-%d")
    next_date = last + timedelta(days=rule["days"])
    return next_date.strftime("%Y-%m-%d")


def cmd_add(args):
    crm = load_crm()
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")
    pid = next_id(crm["prospects"])

    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    pain = [p.strip() for p in args.pain.split(",")] if args.pain else []

    prospect = {
        "id": pid,
        "name": args.name,
        "company": args.company or "",
        "title": args.title or "",
        "industry": args.industry or "",
        "linkedin_url": args.url or "",
        "status": "未アプローチ",
        "status_history": [
            {"status": "未アプローチ", "date": today, "note": "リストに追加"}
        ],
        "tags": tags,
        "pain_points": pain,
        "next_action": crm["timing_rules"]["未アプローチ"]["next_action"],
        "next_action_date": calc_next_action_date(
            "未アプローチ", today, crm["timing_rules"]
        ),
        "priority": args.priority or "B",
        "notes": args.note or "",
        "added_at": today,
    }

    crm["prospects"].append(prospect)
    save_crm(crm)
    print(f"追加完了: {pid} - {args.name}（{args.company}）")
    print(f"次のアクション: {prospect['next_action']} ({prospect['next_action_date']}まで)")


def cmd_status(args):
    crm = load_crm()
    now = datetime.now(JST)
    today = now.strftime("%Y-%m-%d")

    prospect = None
    for p in crm["prospects"]:
        if p["id"] == args.id:
            prospect = p
            break

    if not prospect:
        print(f"エラー: ID '{args.id}' が見つかりません")
        return

    valid_statuses = crm["status_flow"]
    if args.status not in valid_statuses:
        print(f"エラー: 無効なステータス '{args.status}'")
        print(f"有効なステータス: {', '.join(valid_statuses)}")
        return

    prospect["status"] = args.status
    prospect["status_history"].append(
        {"status": args.status, "date": today, "note": args.note or ""}
    )

    next_info = crm["timing_rules"].get(args.status)
    if next_info:
        prospect["next_action"] = next_info["next_action"]
        prospect["next_action_date"] = calc_next_action_date(
            args.status, today, crm["timing_rules"]
        )
    else:
        prospect["next_action"] = ""
        prospect["next_action_date"] = None

    save_crm(crm)
    print(f"更新完了: {prospect['id']} {prospect['name']} → {args.status}")
    if prospect["next_action"]:
        print(f"次のアクション: {prospect['next_action']} ({prospect['next_action_date']}まで)")


def cmd_list(args):
    crm = load_crm()
    prospects = crm["prospects"]

    if args.status:
        prospects = [p for p in prospects if p["status"] == args.status]

    if not prospects:
        print("該当するリードはありません")
        return

    print(f"\n{'ID':<6} {'名前':<12} {'会社':<16} {'ステータス':<10} {'次のアクション':<16} {'期日':<12}")
    print("─" * 80)
    for p in prospects:
        print(
            f"{p['id']:<6} {p['name']:<12} {p['company']:<16} {p['status']:<10} "
            f"{p.get('next_action', ''):<16} {p.get('next_action_date', '') or '':<12}"
        )
    print(f"\n合計: {len(prospects)}件")


def cmd_show(args):
    crm = load_crm()
    prospect = None
    for p in crm["prospects"]:
        if p["id"] == args.id:
            prospect = p
            break

    if not prospect:
        print(f"エラー: ID '{args.id}' が見つかりません")
        return

    print(f"\n{'='*50}")
    print(f"  {prospect['name']}（{prospect['company']}）")
    print(f"{'='*50}")
    print(f"  ID:           {prospect['id']}")
    print(f"  役職:         {prospect['title']}")
    print(f"  業界:         {prospect['industry']}")
    print(f"  LinkedIn:     {prospect['linkedin_url']}")
    print(f"  ステータス:   {prospect['status']}")
    print(f"  優先度:       {prospect['priority']}")
    print(f"  タグ:         {', '.join(prospect['tags'])}")
    print(f"  ペイン:       {', '.join(prospect['pain_points'])}")
    print(f"  次アクション: {prospect.get('next_action', '')} ({prospect.get('next_action_date', '')})")
    print(f"  メモ:         {prospect['notes']}")

    print(f"\n  ── ステータス履歴 ──")
    for h in prospect["status_history"]:
        note = f" - {h['note']}" if h["note"] else ""
        print(f"  {h['date']}  {h['status']}{note}")
    print()


def main():
    parser = argparse.ArgumentParser(description="LinkedIn CRM管理ツール")
    subparsers = parser.add_subparsers(dest="command")

    # add
    add_parser = subparsers.add_parser("add", help="新規リード追加")
    add_parser.add_argument("--name", required=True, help="名前")
    add_parser.add_argument("--company", help="会社名")
    add_parser.add_argument("--title", help="役職")
    add_parser.add_argument("--industry", help="業界")
    add_parser.add_argument("--url", help="LinkedIn URL")
    add_parser.add_argument("--tags", help="タグ（カンマ区切り）")
    add_parser.add_argument("--pain", help="ペイン（カンマ区切り）")
    add_parser.add_argument("--priority", choices=["A", "B", "C"], default="B")
    add_parser.add_argument("--note", help="メモ")

    # status
    status_parser = subparsers.add_parser("status", help="ステータス更新")
    status_parser.add_argument("id", help="プロスペクトID（例: p001）")
    status_parser.add_argument("--status", required=True, help="新しいステータス")
    status_parser.add_argument("--note", help="メモ")

    # list
    list_parser = subparsers.add_parser("list", help="一覧表示")
    list_parser.add_argument("--status", help="ステータスでフィルタ")

    # show
    show_parser = subparsers.add_parser("show", help="詳細表示")
    show_parser.add_argument("id", help="プロスペクトID")

    args = parser.parse_args()

    if args.command == "add":
        cmd_add(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
