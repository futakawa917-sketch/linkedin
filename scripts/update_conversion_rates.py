#!/usr/bin/env python3
"""転換率再計算: CRM実績データから各工程の転換率を算出し更新"""

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


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def count_status_transitions(prospects):
    """各ステータスに到達したプロスペクト数をカウント"""
    status_order = [
        "未アプローチ",
        "コメント済",
        "申請済",
        "承認済",
        "DM済",
        "アポ獲得",
        "商談済",
    ]

    reached = {s: 0 for s in status_order}

    for p in prospects:
        # ステータス履歴から到達済みのステータスをカウント
        reached_statuses = {h["status"] for h in p.get("status_history", [])}
        for s in status_order:
            if s in reached_statuses:
                reached[s] += 1

    return reached


def calculate_rates(reached):
    """ステータス間の転換率を計算"""
    transitions = [
        ("target_to_comment", "未アプローチ", "コメント済"),
        ("comment_to_request", "コメント済", "申請済"),
        ("request_to_approved", "申請済", "承認済"),
        ("approved_to_dm", "承認済", "DM済"),
        ("dm_to_meeting", "DM済", "アポ獲得"),
    ]

    rates = {}
    for key, from_status, to_status in transitions:
        from_count = reached.get(from_status, 0)
        to_count = reached.get(to_status, 0)

        if from_count > 0:
            value = round(to_count / from_count, 3)
        else:
            value = None

        # 信頼度判定
        if from_count >= 50:
            confidence = "high"
        elif from_count >= 20:
            confidence = "medium"
        else:
            confidence = "low"

        rates[key] = {
            "value": value,
            "sample": from_count,
            "confidence": confidence,
            "from_count": from_count,
            "to_count": to_count,
        }

    return rates


def main():
    crm = load_json(os.path.join(BASE_DIR, "data", "crm", "prospects.json"))
    if not crm or not crm.get("prospects"):
        print("CRMデータがありません。デフォルト転換率を引き続き使用します。")
        return

    prospects = crm["prospects"]
    print(f"プロスペクト数: {len(prospects)}\n")

    reached = count_status_transitions(prospects)
    print("ステータス到達数:")
    for status, count in reached.items():
        if count > 0:
            print(f"  {status}: {count}")

    rates = calculate_rates(reached)

    # 既存の転換率データを読み込み（履歴追加用）
    rates_path = os.path.join(BASE_DIR, "data", "conversion_rates.json")
    existing = load_json(rates_path)
    history = existing.get("history", []) if existing else []

    # 今月のスナップショットを履歴に追加
    now = datetime.now(JST)
    month = now.strftime("%Y-%m")
    month_snapshot = {
        "month": month,
        **{k: v["value"] for k, v in rates.items() if v["value"] is not None},
    }

    # 同月の既存エントリがあれば更新、なければ追加
    updated = False
    for i, h in enumerate(history):
        if h.get("month") == month:
            history[i] = month_snapshot
            updated = True
            break
    if not updated:
        history.append(month_snapshot)

    result = {
        "updated_at": now.isoformat(),
        "source": "calculated",
        "sample_size": {
            "total_prospects": len(prospects),
        },
        "rates": rates,
        "history": history,
    }

    save_json(rates_path, result)

    print(f"\n転換率:")
    labels = {
        "target_to_comment": "ターゲット→コメント",
        "comment_to_request": "コメント→申請",
        "request_to_approved": "申請→承認",
        "approved_to_dm": "承認→DM",
        "dm_to_meeting": "DM→商談",
    }
    for key, label in labels.items():
        info = rates[key]
        if info["value"] is not None:
            print(
                f"  {label}: {info['value']*100:.1f}% "
                f"({info['from_count']}→{info['to_count']}, 信頼度: {info['confidence']})"
            )
        else:
            print(f"  {label}: データ不足")

    print(f"\n保存先: {rates_path}")


if __name__ == "__main__":
    main()
