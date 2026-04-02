#!/usr/bin/env python3
"""投稿AI生成パイプライン: Claude APIで週次のLinkedIn投稿ドラフトを生成"""

import json
import os
import random
from datetime import datetime, timezone, timedelta

import anthropic

JST = timezone(timedelta(hours=9))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_recent_posts(limit=10):
    """最近の投稿を取得（重複回避用）"""
    recent = []
    for folder in ["posted", "approved", "drafts"]:
        dir_path = os.path.join(BASE_DIR, "posts", folder)
        if not os.path.exists(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path), reverse=True):
            if fname.endswith(".md") and not fname.startswith("."):
                content = load_file(os.path.join(dir_path, fname))
                recent.append({"file": fname, "content": content[:500]})
                if len(recent) >= limit:
                    break
    return recent


def get_posting_dates():
    """今週の投稿日を計算（月/水/金）"""
    now = datetime.now(JST)
    # 今週の月曜を基準に
    monday = now - timedelta(days=now.weekday())

    schedule_map = {"月": 0, "水": 2, "金": 4}
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    schedule_days = settings.get("posting", {}).get("schedule_days", ["月", "水", "金"])

    dates = []
    for day_name in schedule_days:
        offset = schedule_map.get(day_name, 0)
        post_date = monday + timedelta(days=offset)
        # 過去の日付はスキップ
        if post_date.date() >= now.date():
            dates.append(post_date.strftime("%Y-%m-%d"))

    return dates


def select_post_types(count):
    """投稿タイプを比率に基づいて選択"""
    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    ratio = settings.get("posting", {}).get("post_type_ratio", {})

    # 重み付き選択
    types = list(ratio.keys())
    weights = [ratio[t] for t in types]
    selected = random.choices(types, weights=weights, k=count)
    return selected


def build_prompt(post_type, post_date, recent_posts, settings):
    """Claude APIに送るプロンプトを構築"""
    # ナレッジ読み込み
    pain_points = load_file(
        os.path.join(BASE_DIR, "knowledge", "industry_pain_points.md")
    )
    best_practices = load_file(
        os.path.join(BASE_DIR, "knowledge", "linkedin_best_practices.md")
    )
    winning_patterns = load_file(
        os.path.join(BASE_DIR, "knowledge", "winning_patterns.md")
    )
    learnings = load_file(os.path.join(BASE_DIR, "knowledge", "learnings.md"))
    hooks_template = load_file(
        os.path.join(BASE_DIR, "posts", "templates", "hooks.md")
    )
    post_types_template = load_file(
        os.path.join(BASE_DIR, "posts", "templates", "post_types.md")
    )

    type_labels = {
        "expertise": "専門性",
        "case_study": "事例",
        "engagement": "エンゲージメント",
        "cta": "CTA",
    }

    target_info = settings.get("target", {})

    # 最近の投稿テーマリスト（重複回避）
    recent_themes = "\n".join(
        [f"- {p['file']}" for p in recent_posts[:5]]
    ) if recent_posts else "（まだ投稿はありません）"

    user_message = f"""以下の条件でLinkedIn投稿を1本生成してください。

## 条件
- 投稿日: {post_date}
- 投稿タイプ: {type_labels.get(post_type, post_type)}
- アカウント: 個人（SNS運用代行会社の代表）

## ターゲット
- 業界: {', '.join(target_info.get('industry', []))}
- 企業規模: {target_info.get('company_size', '')}
- 決裁者: {', '.join(target_info.get('decision_maker_titles', []))}
- ペイン:
{chr(10).join('  - ' + p for p in target_info.get('pain_points', []))}

## 業界別ペインポイント（参考）
{pain_points}

## LinkedInベストプラクティス
{best_practices}

## 過去の当たりパターン
{winning_patterns}

## 学び・気づき
{learnings}

## フックテンプレート
{hooks_template}

## 投稿タイプガイド
{post_types_template}

## 最近の投稿（重複回避のため参照）
{recent_themes}

## 重要な注意事項
- 上記の最近の投稿とテーマが被らないように、新しい切り口で書いてください
- LinkedInの「続きを読む」で切れる1行目が最重要です
- フック候補は3つ出し、最も効果的なものを選んで本文に使ってください
- ハッシュタグは3〜5個で末尾に配置してください
"""

    return user_message


def generate_post(client, system_prompt, user_message):
    """Claude APIで投稿を生成"""
    response = client.messages.create(
        model="claude-sonnet-4-6-20250514",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text


def save_draft(post_date, post_type, content):
    """ドラフトをMarkdownファイルとして保存"""
    type_labels = {
        "expertise": "専門性",
        "case_study": "事例",
        "engagement": "エンゲージメント",
        "cta": "CTA",
    }

    # テーマ名をファイル名に使う（簡略化）
    type_label = type_labels.get(post_type, post_type)
    filename = f"{post_date}_{post_type}.md"
    filepath = os.path.join(BASE_DIR, "posts", "drafts", filename)

    full_content = f"""# LinkedIn投稿ドラフト

## メタデータ
- 投稿日: {post_date}
- アカウント: personal
- 投稿タイプ: {type_label}
- ステータス: draft
- 生成日: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}

---

{content}

---

## 承認チェック
- [ ] 内容確認済み
- [ ] トーン・表現を確認
- [ ] 投稿済み
"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_content)

    return filepath


def update_calendar(dates, post_types):
    """月間カレンダーを更新"""
    now = datetime.now(JST)
    month = now.strftime("%Y-%m")
    calendar_path = os.path.join(BASE_DIR, "posts", "calendar", f"{month}_calendar.md")

    type_labels = {
        "expertise": "専門性",
        "case_study": "事例",
        "engagement": "エンゲージメント",
        "cta": "CTA",
    }

    # 既存のカレンダーがあれば読み込み
    existing = load_file(calendar_path)

    if not existing:
        lines = [
            f"# {month} 投稿カレンダー\n",
            "| 日付 | タイプ | ステータス | ファイル |",
            "|------|--------|-----------|---------|",
        ]
    else:
        lines = existing.strip().split("\n")

    for date, ptype in zip(dates, post_types):
        label = type_labels.get(ptype, ptype)
        filename = f"{date}_{ptype}.md"
        line = f"| {date} | {label} | draft | {filename} |"
        # 重複チェック
        if not any(date in l for l in lines):
            lines.append(line)

    with open(calendar_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return calendar_path


def main():
    print("LinkedIn投稿生成パイプライン開始...\n")

    settings = load_json(os.path.join(BASE_DIR, "config", "settings.json"))
    system_prompt = load_file(
        os.path.join(BASE_DIR, "config", "prompts", "post_personal.md")
    )
    recent_posts = get_recent_posts()

    dates = get_posting_dates()
    if not dates:
        print("今週の残り投稿日はありません")
        return

    post_types = select_post_types(len(dates))

    print(f"生成予定: {len(dates)}本")
    for d, t in zip(dates, post_types):
        print(f"  {d} - {t}")
    print()

    client = anthropic.Anthropic()

    generated_files = []
    for date, ptype in zip(dates, post_types):
        print(f"生成中: {date} ({ptype})...")

        user_message = build_prompt(ptype, date, recent_posts, settings)
        content = generate_post(client, system_prompt, user_message)
        filepath = save_draft(date, ptype, content)

        generated_files.append(filepath)
        print(f"  → {filepath}")

        # 生成したものを最近の投稿リストに追加（重複回避）
        recent_posts.insert(
            0, {"file": os.path.basename(filepath), "content": content[:500]}
        )

    # カレンダー更新
    calendar_path = update_calendar(dates, post_types)

    print(f"\n完了:")
    print(f"  投稿ドラフト: {len(generated_files)}本生成")
    print(f"  カレンダー: {calendar_path}")


if __name__ == "__main__":
    main()
