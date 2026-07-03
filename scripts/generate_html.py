"""Génère docs/index.html à partir de l'historique agrégé dans docs/data.json."""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_PATH = BASE_DIR / "docs" / "data.json"
OUTPUT_PATH = BASE_DIR / "docs" / "index.html"

FR_MONTHS = [
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
]

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

  .week-label {{
    font-size: 0.95rem;
    font-weight: 600;
    color: #fc4c02;
    text-align: center;
    margin-bottom: 0.5rem;
  }}
  .range-slider {{
    position: relative;
    height: 2.2rem;
    margin: 0.5rem 0.5rem 0;
  }}
  .range-slider .range-track {{
    position: absolute;
    left: 0; right: 0; top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: #262a35;
    border-radius: 2px;
  }}
  .range-slider .range-fill {{
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: #fc4c02;
    border-radius: 2px;
  }}
  .range-slider input[type=range] {{
    position: absolute;
    left: 0; right: 0; top: 50%;
    transform: translateY(-50%);
    width: 100%;
    margin: 0;
    background: transparent;
    pointer-events: none;
    -webkit-appearance: none;
    appearance: none;
  }}
  .range-slider input[type=range]::-webkit-slider-runnable-track {{ background: transparent; }}
  .range-slider input[type=range]::-webkit-slider-thumb {{
    pointer-events: all;
    -webkit-appearance: none;
    appearance: none;
    width: 18px; height: 18px;
    border-radius: 50%;
    background: #fc4c02;
    cursor: pointer;
    border: 2px solid #0f1117;
  }}
  .range-slider input[type=range]::-moz-range-thumb {{
    pointer-events: all;
    width: 18px; height: 18px;
    border-radius: 50%;
    background: #fc4c02;
    cursor: pointer;
    border: 2px solid #0f1117;
  }}
  .range-slider input[type=range]:disabled::-webkit-slider-thumb {{ background: #5a5f6b; }}
  .range-slider input[type=range]:disabled::-moz-range-thumb {{ background: #5a5f6b; }}
  .range-ticks {{
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #6d7280;
    margin-top: 0.3rem;
  }}

  .member-list {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1.25rem; }}
  .member-item {{ display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; }}
  .member-item input {{ accent-color: #fc4c02; }}
  .member-item.inactive label {{ color: #5a5f6b; font-style: italic; }}
</style>
</head>
<body>
<div class="container">
  <h1>🏃 Dashboard Strava Club</h1>
  <div class="meta">Dernière mise à jour : {last_update}</div>
  <div class="note">
    Les données proviennent de l'API club Strava, qui ne renvoie qu'un instantané des activités
    récentes sans date précise ni identifiant unique. Les chiffres reflètent donc ce qui était
    visible à chaque rafraîchissement, pas un cumul garanti sans doublon. Les "semaines"
    ci-dessous regroupent les rafraîchissements par semaine calendaire (lundi à dimanche).
  </div>

  <div class="card" id="weekRangeCard" style="display: {slicer_display};">
    <h2>Période sélectionnée</h2>
    <div class="week-label" id="weekLabel">{initial_week_label}</div>
    <div class="range-slider">
      <div class="range-track"></div>
      <div class="range-fill" id="weekRangeFill"></div>
      <input type="range" id="weekMin" min="0" max="{max_week_idx}" value="0" step="1">
      <input type="range" id="weekMax" min="0" max="{max_week_idx}" value="{max_week_idx}" step="1">
    </div>
    <div class="range-ticks">
      <span>{first_week_tick}</span>
      <span>{last_week_tick}</span>
    </div>
  </div>

  <div class="card" id="memberSlicerCard" style="display: {member_slicer_display};">
    <h2>Membres affichés</h2>
    <div class="member-list" id="memberList"></div>
  </div>

  <div class="card">
    <h2>Classement course à pied (activités récentes)</h2>
    <canvas id="leaderboardChart"></canvas>
  </div>

  <div class="card">
    <h2>Répartition par type d'activité (club entier)</h2>
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
      <tbody id="memberTableBody">
        {member_rows}
      </tbody>
    </table>
  </div>
</div>

<script>
const weeks = {weeks_json};
const historyEntries = {history_entries_json};
const allMembers = {all_members_json};
const selectedMembers = new Set(allMembers);

const leaderboardChart = new Chart(document.getElementById('leaderboardChart'), {{
  type: 'bar',
  data: {{ labels: [], datasets: [{{ label: 'Distance course (km)', data: [], backgroundColor: '#fc4c02' }}] }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});

const typeChart = new Chart(document.getElementById('typeChart'), {{
  type: 'pie',
  data: {{ labels: [], datasets: [{{ data: [], backgroundColor: ['#fc4c02', '#2a9d8f', '#e9c46a', '#264653', '#e76f51', '#8ab17d', '#f4a261'] }}] }},
  options: {{ responsive: true }}
}});

const weekHighlightPlugin = {{
  id: 'weekHighlight',
  beforeDatasetsDraw(chart) {{
    const range = chart._weekHighlight;
    if (!range) return;
    const {{ ctx, chartArea, scales }} = chart;
    const xScale = scales.x;
    const x0 = xScale.getPixelForValue(range.startIdx);
    const x1 = xScale.getPixelForValue(range.endIdx);
    ctx.save();
    ctx.fillStyle = 'rgba(252, 76, 2, 0.18)';
    ctx.fillRect(Math.min(x0, x1), chartArea.top, Math.max(2, Math.abs(x1 - x0)), chartArea.bottom - chartArea.top);
    ctx.restore();
  }}
}};

const trendChart = new Chart(document.getElementById('trendChart'), {{
  type: 'line',
  data: {{
    labels: historyEntries.map(e => e.timestamp),
    datasets: allMembers.map((name, i) => ({{
      label: name,
      data: historyEntries.map(e => (e.members[name] ? e.members[name].run_km : null)),
      borderColor: `hsl(${{i * 47 % 360}}, 70%, 55%)`,
      fill: false,
      tension: 0.2
    }}))
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ position: 'bottom', onClick: () => {{}} }} }}
  }},
  plugins: [weekHighlightPlugin]
}});

function buildMemberRows(members) {{
  const rows = Object.entries(members)
    .filter(([name]) => selectedMembers.has(name))
    .sort((a, b) => b[1].run_km - a[1].run_km);
  if (rows.length === 0) return '<tr><td colspan="5">Aucune activité pour cette sélection</td></tr>';
  return rows.map(([name, s]) =>
    `<tr><td>${{name}}</td><td>${{s.total_km}}</td><td>${{s.run_km}}</td><td>${{s.run_count}}</td><td>${{s.avg_speed_kmh}}</td></tr>`
  ).join('');
}}

function snapshotIndexForWeek(weekIdx) {{
  return weeks[weekIdx].end_idx;
}}

function currentSnapshot() {{
  const maxWeek = parseInt(document.getElementById('weekMax').value, 10);
  return historyEntries[snapshotIndexForWeek(maxWeek)];
}}

function renderMemberList() {{
  const snapshot = weeks.length > 0 ? currentSnapshot() : {{ members: {{}} }};
  const list = document.getElementById('memberList');
  list.innerHTML = allMembers.map(name => {{
    const stats = snapshot.members[name];
    const active = stats && (stats.total_km > 0 || stats.run_km > 0);
    const checked = selectedMembers.has(name) ? 'checked' : '';
    const id = `member-${{name.replace(/[^a-zA-Z0-9]/g, '-')}}`;
    return `<div class="member-item ${{active ? '' : 'inactive'}}">
      <input type="checkbox" id="${{id}}" data-member="${{name}}" ${{checked}}>
      <label for="${{id}}">${{name}}</label>
    </div>`;
  }}).join('');
}}

function updateCharts() {{
  if (weeks.length === 0) return;
  const minWeek = parseInt(document.getElementById('weekMin').value, 10);
  const maxWeek = parseInt(document.getElementById('weekMax').value, 10);
  const snapshot = historyEntries[snapshotIndexForWeek(maxWeek)];

  const filteredLeaderboard = snapshot.leaderboard.filter(([name]) => selectedMembers.has(name));
  leaderboardChart.data.labels = filteredLeaderboard.map(r => r[0]);
  leaderboardChart.data.datasets[0].data = filteredLeaderboard.map(r => r[1]);
  leaderboardChart.update();

  typeChart.data.labels = Object.keys(snapshot.type_breakdown);
  typeChart.data.datasets[0].data = Object.values(snapshot.type_breakdown);
  typeChart.update();

  document.getElementById('memberTableBody').innerHTML = buildMemberRows(snapshot.members);

  trendChart.data.datasets.forEach(ds => {{ ds.hidden = !selectedMembers.has(ds.label); }});
  trendChart._weekHighlight = {{ startIdx: weeks[minWeek].start_idx, endIdx: weeks[maxWeek].end_idx }};
  trendChart.update();
}}

function updateWeekLabel() {{
  const minWeek = parseInt(document.getElementById('weekMin').value, 10);
  const maxWeek = parseInt(document.getElementById('weekMax').value, 10);
  const label = document.getElementById('weekLabel');
  if (minWeek === maxWeek) {{
    label.textContent = `Semaine du ${{weeks[minWeek].label}}`;
  }} else {{
    label.textContent = `Du ${{weeks[minWeek].label}} au ${{weeks[maxWeek].label}}`;
  }}
}}

function updateRangeFill() {{
  const minWeek = parseInt(document.getElementById('weekMin').value, 10);
  const maxWeek = parseInt(document.getElementById('weekMax').value, 10);
  const count = weeks.length;
  const fill = document.getElementById('weekRangeFill');
  if (count <= 1) {{
    fill.style.left = '0%';
    fill.style.width = '100%';
    return;
  }}
  const pctMin = (minWeek / (count - 1)) * 100;
  const pctMax = (maxWeek / (count - 1)) * 100;
  fill.style.left = `${{pctMin}}%`;
  fill.style.width = `${{pctMax - pctMin}}%`;
}}

function onRangeChange() {{
  updateRangeFill();
  updateWeekLabel();
  updateCharts();
  renderMemberList();
}}

const weekMin = document.getElementById('weekMin');
const weekMax = document.getElementById('weekMax');

if (weeks.length > 0) {{
  weekMin.addEventListener('input', () => {{
    if (parseInt(weekMin.value, 10) > parseInt(weekMax.value, 10)) weekMin.value = weekMax.value;
    onRangeChange();
  }});
  weekMax.addEventListener('input', () => {{
    if (parseInt(weekMax.value, 10) < parseInt(weekMin.value, 10)) weekMax.value = weekMin.value;
    onRangeChange();
  }});
}} else {{
  weekMin.disabled = true;
  weekMax.disabled = true;
}}

document.getElementById('memberList').addEventListener('change', (event) => {{
  const name = event.target.dataset.member;
  if (!name) return;
  if (event.target.checked) selectedMembers.add(name);
  else selectedMembers.delete(name);
  updateCharts();
}});

onRangeChange();
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


def format_day_month(date_):
    return f"{date_.day} {FR_MONTHS[date_.month - 1]}"


def format_week_label(monday, sunday):
    if monday.year == sunday.year:
        return f"{format_day_month(monday)} – {format_day_month(sunday)} {sunday.year}"
    return f"{format_day_month(monday)} {monday.year} – {format_day_month(sunday)} {sunday.year}"


def build_weeks(history):
    """Groupe les entrées d'historique par semaine calendaire (lundi à dimanche).

    Chaque semaine référence les index de début/fin dans le tableau `history` complet
    (même ordre que les timestamps du graphique d'évolution), pour permettre de
    surligner la période correspondante dans ce graphique et de retrouver l'instantané
    le plus récent de la semaine (l'API ne renvoie pas de cumul, seulement un instantané).
    """
    weeks = []
    index_by_key = {}

    for idx, entry in enumerate(history):
        dt = datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
        monday = dt.date() - timedelta(days=dt.weekday())
        key = monday.isoformat()

        if key not in index_by_key:
            index_by_key[key] = len(weeks)
            weeks.append(
                {
                    "label": format_week_label(monday, monday + timedelta(days=6)),
                    "start_idx": idx,
                    "end_idx": idx,
                }
            )
        else:
            weeks[index_by_key[key]]["end_idx"] = idx

    return weeks


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

    weeks = build_weeks(history)
    max_week_idx = max(len(weeks) - 1, 0)
    initial_week_label = f"Semaine du {weeks[-1]['label']}" if weeks else "Pas encore de données"
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

    html = PAGE_TEMPLATE.format(
        last_update=latest["timestamp"],
        member_rows=build_member_rows(latest["members"]),
        weeks_json=json.dumps(weeks, ensure_ascii=False),
        history_entries_json=json.dumps(history_entries, ensure_ascii=False),
        all_members_json=json.dumps(all_members, ensure_ascii=False),
        max_week_idx=max_week_idx,
        initial_week_label=initial_week_label,
        first_week_tick=weeks[0]["label"] if weeks else "",
        last_week_tick=weeks[-1]["label"] if weeks else "",
        slicer_display="block" if weeks else "none",
        member_slicer_display="block" if all_members else "none",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"Dashboard généré -> {OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
