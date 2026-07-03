"""Agrège les activités brutes en statistiques (docs/data.json) et maintient un ledger
d'activités par empreinte de contenu (docs/activities_seen.json) -- voir CLAUDE.md Étape 9.

Limite connue : l'API club ne renvoie qu'un instantané des activités récentes, sans date ni
identifiant unique par activité. docs/data.json stocke donc chaque exécution comme un point
d'historique distinct ("ce qui était visible à ce moment-là"), pas comme un cumul réel sans
doublons possibles.

Le ledger (Étape 9) contourne l'absence de date en hashant le contenu de chaque activité et en
retenant la date de sa première détection par ce script comme approximation de sa date de
création réelle -- ce qui permet de reconstruire une vraie série temporelle.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_PATH = BASE_DIR / "data" / "raw_activities.json"
HISTORY_PATH = BASE_DIR / "docs" / "data.json"
LEDGER_PATH = BASE_DIR / "docs" / "activities_seen.json"
EXCLUDED_PATH = BASE_DIR / "scripts" / "excluded_activities.json"

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


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def activity_hash(activity):
    """Empreinte de contenu servant de pseudo-ID (Strava n'en fournit pas). Deux activités
    identiques sur tous ces champs (même athlète, mêmes valeurs, même titre) seraient fusionnées
    à tort -- risque jugé faible en pratique, documenté dans CLAUDE.md Étape 9."""
    athlete_name = member_name(activity)
    fields = [
        athlete_name,
        str(activity.get("type", "")),
        str(activity.get("distance", 0)),
        str(activity.get("moving_time", 0)),
        str(activity.get("elapsed_time", 0)),
        str(activity.get("total_elevation_gain", 0)),
        str(activity.get("name", "")),
    ]
    digest = hashlib.sha256("|".join(fields).encode("utf-8")).hexdigest()
    return digest[:16]


def update_ledger(activities, excluded_hashes, now_iso):
    ledger = load_json(LEDGER_PATH, {})
    added = 0
    for activity in activities:
        activity_id = activity_hash(activity)
        if activity_id in excluded_hashes or activity_id in ledger:
            continue
        ledger[activity_id] = {
            "first_seen": now_iso,
            "athlete": member_name(activity),
            "sport": activity.get("type", "Unknown"),
            "distance": activity.get("distance", 0),
            "moving_time": activity.get("moving_time", 0),
            "elevation": activity.get("total_elevation_gain", 0),
            "title": activity.get("name", ""),
        }
        added += 1
    return ledger, added


def main():
    activities = json.loads(RAW_PATH.read_text())
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # V1 -- historique par instantané agrégé (docs/data.json), conservé tel quel.
    members = aggregate_members(activities)
    entry = {
        "timestamp": now_iso,
        "activity_count": len(activities),
        "members": members,
        "type_breakdown": aggregate_type_breakdown(activities),
        "leaderboard": build_leaderboard(members),
    }
    history = load_json(HISTORY_PATH, {"history": []})
    history["history"].append(entry)
    history["history"] = history["history"][-MAX_HISTORY_ENTRIES:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    print(f"Historique mis à jour ({len(history['history'])} entrées) -> {HISTORY_PATH}")

    # V2 (Étape 9) -- ledger d'activités par empreinte, avec date de première détection.
    excluded_hashes = set(load_json(EXCLUDED_PATH, []))
    ledger, added = update_ledger(activities, excluded_hashes, now_iso)
    LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Ledger mis à jour : {added} nouvelle(s) activité(s), {len(ledger)} au total -> {LEDGER_PATH}")


if __name__ == "__main__":
    sys.exit(main())
