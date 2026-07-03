"""Génère docs/index.html à partir de l'historique agrégé dans docs/data.json."""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = BASE_DIR / "docs" / "data.json"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"

TOP_N_TREND_MEMBERS = 8

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Strava Club</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f1117;
    color: #e6e6e6;
    margin: 0;
    padding: 2rem 1rem 4rem;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
  .meta {{ color: #9aa0ab; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  .note {{
    background: #1b1e27;
    border-left: 3px solid #fc4c02;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #b8bec9;
    border-radius: 4px;
    margin-bottom: 2rem;
  }}
  .card {{
    background: #171a22;
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }}
  .card h2 {{ margin-top: 0; font-size: 1.1rem; color: #fc4c02; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
  th, td {{ text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #262a35; }}
  th {{ color: #9aa0ab; font-weight: 500; }}
</style>
</head>
<body>
<div class="container">
  <h1>🏃 Dashboard Strava Club</h1>
  <div class="meta">Dernière mise à jour : {last_update}</div>
  <div class="note">
    Les données proviennent de l'API club Strava, qui ne renvoie qu'un instantané des activités
    récentes sans date précise ni identifiant unique. Les chiffres reflètent donc ce qui était
    visible à chaque rafraîchissement, pas un cumul garanti sans doublon.
  </div>

  <div class="card">
    <h2>Classement course à pied (activités récentes)</h2>
    <canvas id="leaderboardChart"></canvas>
  </div>

  <div class="card">
    <h2>Répartition par type d'activité</h2>
    <canvas id="typeChart"></canvas>
  </div>

  <div class="card">
    <h2>Évolution du classement dans le temps</h2>
    <canvas id="trendChart"></canvas>
  </div>

  <div class="card">
    <h2>Détail par membre</h2>
    <table>
      <thead>
        <tr><th>Membre</th><th>Distance totale (km)</th><th>Distance course (km)</th><th>Nb courses</th><th>Vitesse moy. (km/h)</th></tr>
      </thead>
      <tbody>
        {member_rows}
      </tbody>
    </table>
  </div>
</div>

<script>
const leaderboard = {leaderboard_json};
new Chart(document.getElementById('leaderboardChart'), {{
  type: 'bar',
  data: {{
    labels: leaderboard.map(r => r[0]),
    datasets: [{{ label: 'Distance course (km)', data: leaderboard.map(r => r[1]), backgroundColor: '#fc4c02' }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});

const typeBreakdown = {type_breakdown_json};
new Chart(document.getElementById('typeChart'), {{
  type: 'pie',
  data: {{
    labels: Object.keys(typeBreakdown),
    datasets: [{{ data: Object.values(typeBreakdown), backgroundColor: ['#fc4c02', '#2a9d8f', '#e9c46a', '#264653', '#e76f51', '#8ab17d', '#f4a261'] }}]
  }},
  options: {{ responsive: true }}
}});

const trend = {trend_json};
new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: trend.labels,
    datasets: trend.datasets.map((d, i) => ({{
      label: d.name,
      data: d.values,
      borderColor: `hsl(${{i * 47 % 360}}, 70%, 55%)`,
      fill: false,
      tension: 0.2
    }}))
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ position: 'bottom' }} }} }}
}});
</script>
</body>
</html>
"""


def build_member_rows(members):
    rows = []
    for name, stats in sorted(members.items(), key=lambda item: item[1]["run_km"], reverse=True):
        rows.append(
            f"<tr><td>{name}</td><td>{stats['total_km']}</td><td>{stats['run_km']}</td>"
            f"<td>{stats['run_count']}</td><td>{stats['avg_speed_kmh']}</td></tr>"
        )
    return "\n        ".join(rows) if rows else "<tr><td colspan=\"5\">Aucune activité récente</td></tr>"


def build_trend(history):
    latest_leaderboard = history[-1]["leaderboard"] if history else []
    top_names = [name for name, _ in latest_leaderboard[:TOP_N_TREND_MEMBERS]]

    labels = [entry["timestamp"] for entry in history]
    datasets = []
    for name in top_names:
        values = []
        for entry in history:
            stats = entry.get("members", {}).get(name)
            values.append(stats["run_km"] if stats else None)
        datasets.append({"name": name, "values": values})

    return {"labels": labels, "datasets": datasets}


def main():
    data = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else {"history": []}
    history = data.get("history", [])

    if not history:
        latest = {"timestamp": "jamais", "members": {}, "type_breakdown": {}, "leaderboard": []}
    else:
        latest = history[-1]

    html = PAGE_TEMPLATE.format(
        last_update=latest["timestamp"],
        member_rows=build_member_rows(latest["members"]),
        leaderboard_json=json.dumps(latest["leaderboard"], ensure_ascii=False),
        type_breakdown_json=json.dumps(latest["type_breakdown"], ensure_ascii=False),
        trend_json=json.dumps(build_trend(history), ensure_ascii=False),
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard généré -> {OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
