"""Agrège les activités brutes en statistiques et accumule un historique dans docs/data.json.

Limite connue : l'API club ne renvoie qu'un instantané des activités récentes, sans date ni
identifiant unique. Chaque exécution est donc stockée comme un point d'historique distinct
("ce qui était visible à ce moment-là"), pas comme un cumul réel sans doublons possibles.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "data" / "raw_activities.json"
HISTORY_PATH = BASE_DIR / "docs" / "data.json"

MAX_HISTORY_ENTRIES = 500


def member_name(activity):
    athlete = activity.get("athlete", {})
    return f"{athlete.get('firstname', '').strip()} {athlete.get('lastname', '').strip()}".strip()


def average_speed_kmh(distance_m, moving_time_s):
    if not moving_time_s:
        return 0.0
    return (distance_m / moving_time_s) * 3.6


def aggregate_members(activities):
    members = {}
    for activity in activities:
        name = member_name(activity)
        if not name:
            continue
        distance_km = activity.get("distance", 0) / 1000
        stats = members.setdefault(
            name,
            {"total_km": 0.0, "run_km": 0.0, "run_count": 0, "run_moving_time_s": 0},
        )
        stats["total_km"] += distance_km
        if activity.get("type") == "Run":
            stats["run_km"] += distance_km
            stats["run_count"] += 1
            stats["run_moving_time_s"] += activity.get("moving_time", 0)

    for stats in members.values():
        stats["total_km"] = round(stats["total_km"], 2)
        stats["run_km"] = round(stats["run_km"], 2)
        stats["avg_speed_kmh"] = round(
            average_speed_kmh(stats["run_km"] * 1000, stats["run_moving_time_s"]), 2
        )
        del stats["run_moving_time_s"]

    return members


def aggregate_type_breakdown(activities):
    breakdown = {}
    for activity in activities:
        activity_type = activity.get("type", "Unknown")
        breakdown[activity_type] = breakdown.get(activity_type, 0) + 1
    return breakdown


def build_leaderboard(members):
    ranked = sorted(members.items(), key=lambda item: item[1]["run_km"], reverse=True)
    return [[name, stats["run_km"]] for name, stats in ranked]


def load_history():
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return {"history": []}


def main():
    activities = json.loads(RAW_PATH.read_text())

    members = aggregate_members(activities)
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "activity_count": len(activities),
        "members": members,
        "type_breakdown": aggregate_type_breakdown(activities),
        "leaderboard": build_leaderboard(members),
    }

    history = load_history()
    history["history"].append(entry)
    history["history"] = history["history"][-MAX_HISTORY_ENTRIES:]

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"Historique mis à jour ({len(history['history'])} entrées) -> {HISTORY_PATH}")


if __name__ == "__main__":
    sys.exit(main())
