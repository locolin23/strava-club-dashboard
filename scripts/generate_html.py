"""Génère docs/index.html à partir de l'historique agrégé dans docs/data.json."""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = BASE_DIR / "docs" / "data.json"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"

# Le template utilise des placeholders __XXX__ remplacés par de simples .replace()
# plutôt que str.format(), pour éviter d'avoir à échapper les accolades dans le JS.
PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard Strava Club</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #0f1117;
    color: #e6e6e6;
    margin: 0;
    padding: 2rem 1rem 4rem;
  }
  .container { max-width: 960px; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin-bottom: 0.25rem; }
  .meta { color: #9aa0ab; font-size: 0.9rem; margin-bottom: 1.5rem; }
  .note {
    background: #1b1e27;
    border-left: 3px solid #fc4c02;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #b8bec9;
    border-radius: 4px;
    margin-bottom: 2rem;
  }
  .note a { color: #fc4c02; }
  .card {
    background: #171a22;
    border-radius: 8px;
    padding: 1.25rem;
    margin-bottom: 1.5rem;
  }
  .card h2 { margin-top: 0; font-size: 1.1rem; color: #fc4c02; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #262a35; }
  th { color: #9aa0ab; font-weight: 500; }

  .pie-wrap { max-width: 280px; margin: 0 auto; }

  .member-list { display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; }
  .member-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }
  .member-item input { accent-color: #fc4c02; }
  .member-item.inactive label { color: #5a5f6b; font-style: italic; }
</style>
</head>
<body>
<div class="container">
  <h1>🏃 Dashboard Strava Club</h1>
  <div class="meta">Dernière mise à jour : __LAST_UPDATE__</div>
  <div class="note">
    Les données proviennent de l'API club Strava, qui ne renvoie qu'un instantané des activités
    récentes sans date précise ni identifiant unique. Les chiffres reflètent donc ce qui était
    visible à chaque rafraîchissement, pas un cumul garanti sans doublon. La réponse brute de
    l'API, avant tout traitement, est disponible dans le dépôt :
    <a href="https://github.com/locolin23/strava-club-dashboard/blob/main/data/raw_activities.json">data/raw_activities.json</a>.
  </div>

  <div class="card" id="memberSlicerCard" style="display: __MEMBER_SLICER_DISPLAY__;">
    <h2>Membres affichés</h2>
    <div class="member-list" id="memberList"></div>
  </div>

  <div class="card">
    <h2>Classement course à pied (activités récentes)</h2>
    <canvas id="leaderboardChart"></canvas>
  </div>

  <div class="card">
    <h2>Répartition par type d'activité (club entier)</h2>
    <div class="pie-wrap"><canvas id="typeChart"></canvas></div>
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
      <tbody id="memberTableBody">
        __MEMBER_ROWS__
      </tbody>
    </table>
  </div>
</div>

<script>
const historyEntries = __HISTORY_ENTRIES_JSON__;
const allMembers = __ALL_MEMBERS_JSON__;
const selectedMembers = new Set(allMembers);
const latestEntry = historyEntries.length > 0
  ? historyEntries[historyEntries.length - 1]
  : { leaderboard: [], type_breakdown: {}, members: {} };

const leaderboardChart = new Chart(document.getElementById('leaderboardChart'), {
  type: 'bar',
  data: { labels: [], datasets: [{ label: 'Distance course (km)', data: [], backgroundColor: '#fc4c02' }] },
  options: { responsive: true, plugins: { legend: { display: false } } }
});

const typeChart = new Chart(document.getElementById('typeChart'), {
  type: 'pie',
  data: {
    labels: Object.keys(latestEntry.type_breakdown),
    datasets: [{ data: Object.values(latestEntry.type_breakdown), backgroundColor: ['#fc4c02', '#2a9d8f', '#e9c46a', '#264653', '#e76f51', '#8ab17d', '#f4a261'] }]
  },
  options: { responsive: true, maintainAspectRatio: true }
});

const trendChart = new Chart(document.getElementById('trendChart'), {
  type: 'line',
  data: {
    datasets: allMembers.map((name, i) => ({
      label: name,
      data: historyEntries.map(e => ({
        x: e.timestamp,
        y: e.members[name] ? e.members[name].run_km : null
      })),
      borderColor: `hsl(${i * 47 % 360}, 70%, 55%)`,
      fill: false,
      tension: 0.2
    }))
  },
  options: {
    responsive: true,
    plugins: { legend: { position: 'bottom', onClick: () => {} } },
    scales: {
      x: {
        type: 'time',
        time: { tooltipFormat: 'dd/MM/yyyy HH:mm' },
        ticks: { color: '#9aa0ab' },
        grid: { color: '#232733' }
      },
      y: {
        ticks: { color: '#9aa0ab' },
        grid: { color: '#232733' }
      }
    }
  }
});

function buildMemberRows(members) {
  const rows = Object.entries(members)
    .filter(([name]) => selectedMembers.has(name))
    .sort((a, b) => b[1].run_km - a[1].run_km);
  if (rows.length === 0) return '<tr><td colspan="5">Aucune activité pour cette sélection</td></tr>';
  return rows.map(([name, s]) =>
    `<tr><td>${name}</td><td>${s.total_km}</td><td>${s.run_km}</td><td>${s.run_count}</td><td>${s.avg_speed_kmh}</td></tr>`
  ).join('');
}

function renderMemberList() {
  const list = document.getElementById('memberList');
  list.innerHTML = allMembers.map(name => {
    const stats = latestEntry.members[name];
    const active = stats && (stats.total_km > 0 || stats.run_km > 0);
    const checked = selectedMembers.has(name) ? 'checked' : '';
    const id = `member-${name.replace(/[^a-zA-Z0-9]/g, '-')}`;
    return `<div class="member-item ${active ? '' : 'inactive'}">
      <input type="checkbox" id="${id}" data-member="${name}" ${checked}>
      <label for="${id}">${name}</label>
    </div>`;
  }).join('');
}

function updateCharts() {
  const filteredLeaderboard = latestEntry.leaderboard.filter(([name]) => selectedMembers.has(name));
  leaderboardChart.data.labels = filteredLeaderboard.map(r => r[0]);
  leaderboardChart.data.datasets[0].data = filteredLeaderboard.map(r => r[1]);
  leaderboardChart.update();

  document.getElementById('memberTableBody').innerHTML = buildMemberRows(latestEntry.members);

  trendChart.data.datasets.forEach(ds => { ds.hidden = !selectedMembers.has(ds.label); });
  trendChart.update();
}

document.getElementById('memberList').addEventListener('change', (event) => {
  const name = event.target.dataset.member;
  if (!name) return;
  if (event.target.checked) selectedMembers.add(name);
  else selectedMembers.delete(name);
  updateCharts();
});

renderMemberList();
updateCharts();
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


def build_all_members(history):
    members = set()
    for entry in history:
        members.update(entry.get("members", {}).keys())
    return sorted(members)


def main():
    data = json.loads(HISTORY_PATH.read_text()) if HISTORY_PATH.exists() else {"history": []}
    history = data.get("history", [])

    if not history:
        latest = {"timestamp": "jamais", "members": {}, "type_breakdown": {}, "leaderboard": []}
    else:
        latest = history[-1]

    all_members = build_all_members(history)

    history_entries = [
        {
            "timestamp": entry["timestamp"],
            "leaderboard": entry["leaderboard"],
            "type_breakdown": entry["type_breakdown"],
            "members": entry["members"],
        }
        for entry in history
    ]

    replacements = {
        "__LAST_UPDATE__": latest["timestamp"],
        "__MEMBER_ROWS__": build_member_rows(latest["members"]),
        "__HISTORY_ENTRIES_JSON__": json.dumps(history_entries, ensure_ascii=False),
        "__ALL_MEMBERS_JSON__": json.dumps(all_members, ensure_ascii=False),
        "__MEMBER_SLICER_DISPLAY__": "block" if all_members else "none",
    }

    html = PAGE_TEMPLATE
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard généré -> {OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
