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

  .week-label {
    font-size: 0.95rem;
    font-weight: 600;
    color: #fc4c02;
    text-align: center;
    margin-bottom: 0.75rem;
  }
  .range-slider {
    position: relative;
    height: 1.5rem;
    margin: 0.5rem 0.75rem 0;
  }
  .range-track {
    position: absolute;
    left: 0; right: 0; top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: #262a35;
    border-radius: 2px;
  }
  .range-fill {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 4px;
    background: #fc4c02;
    border-radius: 2px;
  }
  .range-handle {
    position: absolute;
    top: 50%;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fc4c02;
    border: 2px solid #0f1117;
    transform: translate(-50%, -50%);
    cursor: grab;
    touch-action: none;
  }
  .range-handle:active { cursor: grabbing; }
  .range-handle.disabled { background: #5a5f6b; cursor: default; }
  .range-ticks {
    display: flex;
    justify-content: space-between;
    font-size: 0.75rem;
    color: #6d7280;
    margin-top: 0.5rem;
  }

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
    visible à chaque rafraîchissement, pas un cumul garanti sans doublon. Les "semaines"
    ci-dessous regroupent les rafraîchissements par semaine calendaire (lundi à dimanche).
  </div>

  <div class="card" id="weekRangeCard" style="display: __SLICER_DISPLAY__;">
    <h2>Période sélectionnée</h2>
    <div class="week-label" id="weekLabel">__INITIAL_WEEK_LABEL__</div>
    <div class="range-slider" id="weekRangeSlider">
      <div class="range-track"></div>
      <div class="range-fill" id="weekRangeFill"></div>
      <div class="range-handle" id="weekHandleMin" tabindex="0" role="slider" aria-label="Début de la période"></div>
      <div class="range-handle" id="weekHandleMax" tabindex="0" role="slider" aria-label="Fin de la période"></div>
    </div>
    <div class="range-ticks">
      <span>__FIRST_WEEK_TICK__</span>
      <span>__LAST_WEEK_TICK__</span>
    </div>
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
const weeks = __WEEKS_JSON__;
const historyEntries = __HISTORY_ENTRIES_JSON__;
const allMembers = __ALL_MEMBERS_JSON__;
const selectedMembers = new Set(allMembers);
const weekCount = weeks.length;

const leaderboardChart = new Chart(document.getElementById('leaderboardChart'), {
  type: 'bar',
  data: { labels: [], datasets: [{ label: 'Distance course (km)', data: [], backgroundColor: '#fc4c02' }] },
  options: { responsive: true, plugins: { legend: { display: false } } }
});

const typeChart = new Chart(document.getElementById('typeChart'), {
  type: 'pie',
  data: { labels: [], datasets: [{ data: [], backgroundColor: ['#fc4c02', '#2a9d8f', '#e9c46a', '#264653', '#e76f51', '#8ab17d', '#f4a261'] }] },
  options: { responsive: true, maintainAspectRatio: true }
});

const trendChart = new Chart(document.getElementById('trendChart'), {
  type: 'line',
  data: { datasets: allMembers.map((name, i) => ({
    label: name,
    data: [],
    borderColor: `hsl(${i * 47 % 360}, 70%, 55%)`,
    fill: false,
    tension: 0.2
  })) },
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

function snapshotIndexForWeek(weekIdx) {
  return weeks[weekIdx].end_idx;
}

function currentSnapshot(maxWeek) {
  return historyEntries[snapshotIndexForWeek(maxWeek)];
}

function buildMemberRows(members) {
  const rows = Object.entries(members)
    .filter(([name]) => selectedMembers.has(name))
    .sort((a, b) => b[1].run_km - a[1].run_km);
  if (rows.length === 0) return '<tr><td colspan="5">Aucune activité pour cette sélection</td></tr>';
  return rows.map(([name, s]) =>
    `<tr><td>${name}</td><td>${s.total_km}</td><td>${s.run_km}</td><td>${s.run_count}</td><td>${s.avg_speed_kmh}</td></tr>`
  ).join('');
}

function renderMemberList(maxWeek) {
  const snapshot = weekCount > 0 ? currentSnapshot(maxWeek) : { members: {} };
  const list = document.getElementById('memberList');
  list.innerHTML = allMembers.map(name => {
    const stats = snapshot.members[name];
    const active = stats && (stats.total_km > 0 || stats.run_km > 0);
    const checked = selectedMembers.has(name) ? 'checked' : '';
    const id = `member-${name.replace(/[^a-zA-Z0-9]/g, '-')}`;
    return `<div class="member-item ${active ? '' : 'inactive'}">
      <input type="checkbox" id="${id}" data-member="${name}" ${checked}>
      <label for="${id}">${name}</label>
    </div>`;
  }).join('');
}

function updateCharts(minWeek, maxWeek) {
  if (weekCount === 0) return;
  const snapshot = currentSnapshot(maxWeek);

  const filteredLeaderboard = snapshot.leaderboard.filter(([name]) => selectedMembers.has(name));
  leaderboardChart.data.labels = filteredLeaderboard.map(r => r[0]);
  leaderboardChart.data.datasets[0].data = filteredLeaderboard.map(r => r[1]);
  leaderboardChart.update();

  typeChart.data.labels = Object.keys(snapshot.type_breakdown);
  typeChart.data.datasets[0].data = Object.values(snapshot.type_breakdown);
  typeChart.update();

  document.getElementById('memberTableBody').innerHTML = buildMemberRows(snapshot.members);

  const rangeStart = weeks[minWeek].start_idx;
  const rangeEnd = weeks[maxWeek].end_idx;
  const rangeEntries = historyEntries.slice(rangeStart, rangeEnd + 1);
  trendChart.data.datasets.forEach(ds => {
    ds.hidden = !selectedMembers.has(ds.label);
    ds.data = rangeEntries.map(e => ({
      x: e.timestamp,
      y: e.members[ds.label] ? e.members[ds.label].run_km : null
    }));
  });
  trendChart.update();
}

function updateWeekLabel(minWeek, maxWeek) {
  const label = document.getElementById('weekLabel');
  if (minWeek === maxWeek) {
    label.textContent = `Semaine du ${weeks[minWeek].label}`;
  } else {
    label.textContent = `Du ${weeks[minWeek].label} au ${weeks[maxWeek].label}`;
  }
}

let currentMinWeek = 0;
let currentMaxWeek = Math.max(weekCount - 1, 0);

function setupWeekSlider() {
  const track = document.getElementById('weekRangeSlider');
  const fill = document.getElementById('weekRangeFill');
  const handleMin = document.getElementById('weekHandleMin');
  const handleMax = document.getElementById('weekHandleMax');

  function idxToPercent(idx) {
    return weekCount > 1 ? (idx / (weekCount - 1)) * 100 : (idx === 0 ? 0 : 100);
  }

  function render() {
    const minPct = weekCount > 1 ? idxToPercent(currentMinWeek) : 0;
    const maxPct = weekCount > 1 ? idxToPercent(currentMaxWeek) : 100;
    handleMin.style.left = `${minPct}%`;
    handleMax.style.left = `${maxPct}%`;
    fill.style.left = `${minPct}%`;
    fill.style.width = `${Math.max(0, maxPct - minPct)}%`;
    updateWeekLabel(currentMinWeek, currentMaxWeek);
    updateCharts(currentMinWeek, currentMaxWeek);
    renderMemberList(currentMaxWeek);
  }

  function percentToIdx(pct) {
    if (weekCount <= 1) return 0;
    return Math.round((pct / 100) * (weekCount - 1));
  }

  function bindHandle(handle, isMin) {
    handle.addEventListener('pointerdown', (event) => {
      if (weekCount <= 1) return;
      handle.setPointerCapture(event.pointerId);

      const move = (moveEvent) => {
        const rect = track.getBoundingClientRect();
        let pct = ((moveEvent.clientX - rect.left) / rect.width) * 100;
        pct = Math.max(0, Math.min(100, pct));
        let idx = percentToIdx(pct);
        if (isMin) {
          currentMinWeek = Math.min(idx, currentMaxWeek);
        } else {
          currentMaxWeek = Math.max(idx, currentMinWeek);
        }
        render();
      };
      const up = () => {
        handle.removeEventListener('pointermove', move);
        handle.removeEventListener('pointerup', up);
      };
      handle.addEventListener('pointermove', move);
      handle.addEventListener('pointerup', up);
    });

    handle.addEventListener('keydown', (event) => {
      if (weekCount <= 1) return;
      let idx = isMin ? currentMinWeek : currentMaxWeek;
      if (event.key === 'ArrowLeft') idx -= 1;
      else if (event.key === 'ArrowRight') idx += 1;
      else return;
      event.preventDefault();
      idx = Math.max(0, Math.min(weekCount - 1, idx));
      if (isMin) currentMinWeek = Math.min(idx, currentMaxWeek);
      else currentMaxWeek = Math.max(idx, currentMinWeek);
      render();
    });
  }

  if (weekCount <= 1) {
    handleMin.classList.add('disabled');
    handleMax.classList.add('disabled');
  } else {
    bindHandle(handleMin, true);
    bindHandle(handleMax, false);
  }

  render();
}

document.getElementById('memberList').addEventListener('change', (event) => {
  const name = event.target.dataset.member;
  if (!name) return;
  if (event.target.checked) selectedMembers.add(name);
  else selectedMembers.delete(name);
  updateCharts(currentMinWeek, currentMaxWeek);
});

setupWeekSlider();
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
    (même ordre que les entrées passées au graphique d'évolution), pour retrouver
    l'instantané le plus récent de la semaine (l'API ne renvoie pas de cumul, seulement
    un instantané) et pour borner la plage affichée dans ce graphique.
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

    replacements = {
        "__LAST_UPDATE__": latest["timestamp"],
        "__MEMBER_ROWS__": build_member_rows(latest["members"]),
        "__WEEKS_JSON__": json.dumps(weeks, ensure_ascii=False),
        "__HISTORY_ENTRIES_JSON__": json.dumps(history_entries, ensure_ascii=False),
        "__ALL_MEMBERS_JSON__": json.dumps(all_members, ensure_ascii=False),
        "__INITIAL_WEEK_LABEL__": initial_week_label,
        "__FIRST_WEEK_TICK__": weeks[0]["label"] if weeks else "",
        "__LAST_WEEK_TICK__": weeks[-1]["label"] if weeks else "",
        "__SLICER_DISPLAY__": "block" if weeks else "none",
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
