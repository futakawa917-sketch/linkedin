#!/usr/bin/env python3
"""LinkedIn分析データCSV取込: 手動エクスポートしたCSVを構造化データに変換

使い方:
  python scripts/import_analytics.py path/to/linkedin_export.csv

CSVフォーマット（LinkedIn標準エクスポート or 手動作成）:
  date,post_text,impressions,reactions,comments,reposts,clicks,engagement_rate

手動入力用の簡易フォーマットも対応:
  date,impressions,reactions,comments
"""

import argparse
import csv
import json
import os
import shutil
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_csv(filepath):
    """CSVを読み込んでレコードリストに変換"""
    records = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            record = {
                "date": row.get("date", "").strip(),
                "post_text": row.get("post_text", "").strip()[:100],
                "impressions": int(row.get("impressions", 0) or 0),
                "reactions": int(row.get("reactions", 0) or 0),
                "comments": int(row.get("comments", 0) or 0),
                "reposts": int(row.get("reposts", 0) or 0),
                "clicks": int(row.get("clicks", 0) or 0),
            }
            total_engagement = (
                record["reactions"]
                + record["comments"]
                + record["reposts"]
                + record["clicks"]
            )
            record["engagement_rate"] = (
                round(total_engagement / record["impressions"] * 100, 2)
                if record["impressions"] > 0
                else 0
            )
            records.append(record)
    return records


def group_by_month(records):
    """レコードを月別にグループ化"""
    months = {}
    for r in records:
        if not r["date"]:
            continue
        month = r["date"][:7]  # YYYY-MM
        months.setdefault(month, []).append(r)
    return months


def update_processed(month, records):
    """加工済みデータを更新"""
    path = os.path.join(BASE_DIR, "data", "analytics", "processed", f"{month}.json")
    existing = load_json(path) or {"month": month, "posts": [], "summary": {}}

    # 既存データに追加（日付で重複排除）
    existing_dates = {p["date"] for p in existing["posts"]}
    for r in records:
        if r["date"] not in existing_dates:
            existing["posts"].append(r)

    # サマリ再計算
    posts = existing["posts"]
    if posts:
        existing["summary"] = {
            "total_posts": len(posts),
            "total_impressions": sum(p["impressions"] for p in posts),
            "total_reactions": sum(p["reactions"] for p in posts),
            "total_comments": sum(p["comments"] for p in posts),
            "avg_impressions": round(
                sum(p["impressions"] for p in posts) / len(posts)
            ),
            "avg_engagement_rate": round(
                sum(p["engagement_rate"] for p in posts) / len(posts), 2
            ),
            "top_post": max(posts, key=lambda p: p["impressions"]),
        }

    save_json(path, existing)
    return existing


def update_actuals(month, summary):
    """月次実績ファイルの投稿パフォーマンス部分を更新"""
    path = os.path.join(BASE_DIR, "data", "kpi", "actuals", f"{month}.json")
    actuals = load_json(path) or {
        "month": month,
        "updated_at": datetime.now(JST).isoformat(),
        "actions": {},
        "posts": {"personal": {}, "company": {}},
        "funnel_snapshot": {},
    }

    actuals["updated_at"] = datetime.now(JST).isoformat()
    actuals["posts"]["personal"] = {
        "count": summary.get("total_posts", 0),
        "total_impressions": summary.get("total_impressions", 0),
        "total_engagement": summary.get("total_reactions", 0)
        + summary.get("total_comments", 0),
        "avg_impressions": summary.get("avg_impressions", 0),
        "avg_engagement_rate": summary.get("avg_engagement_rate", 0),
    }

    save_json(path, actuals)
    return actuals


def archive_csv(filepath):
    """元CSVをimportsフォルダにアーカイブ"""
    imports_dir = os.path.join(BASE_DIR, "data", "analytics", "imports")
    os.makedirs(imports_dir, exist_ok=True)
    today = datetime.now(JST).strftime("%Y-%m-%d")
    basename = os.path.basename(filepath)
    dest = os.path.join(imports_dir, f"{today}_{basename}")
    shutil.copy2(filepath, dest)
    return dest


def main():
    parser = argparse.ArgumentParser(description="LinkedIn分析データCSV取込")
    parser.add_argument("csv_path", help="CSVファイルのパス")
    args = parser.parse_args()

    if not os.path.exists(args.csv_path):
        print(f"エラー: ファイルが見つかりません: {args.csv_path}")
        return

    print(f"CSV読み込み: {args.csv_path}")
    records = parse_csv(args.csv_path)
    print(f"  レコード数: {len(records)}")

    months = group_by_month(records)

    for month, month_records in months.items():
        processed = update_processed(month, month_records)
        summary = processed["summary"]
        update_actuals(month, summary)

        print(f"\n  {month}:")
        print(f"    投稿数: {summary.get('total_posts', 0)}")
        print(f"    総インプレッション: {summary.get('total_impressions', 0):,}")
        print(f"    平均エンゲージメント率: {summary.get('avg_engagement_rate', 0)}%")

    archived = archive_csv(args.csv_path)
    print(f"\n  アーカイブ: {archived}")
    print("\n取込完了")


if __name__ == "__main__":
    main()
