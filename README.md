# Dashboard Strava Club

Dashboard HTML statique résumant les activités récentes des membres d'un club Strava, publié
automatiquement sur GitHub Pages et rafraîchi toutes les heures via GitHub Actions.

⚠️ **Ce projet a une durée de vie limitée** : l'endpoint `GET /clubs/{id}/activities` utilisé ici
sera supprimé par Strava le 1er septembre 2026. Voir [CLAUDE.md](CLAUDE.md) pour le détail des
limitations (pas de date par activité, pas d'identifiant d'athlète unique, etc.).

## Démarrage rapide

1. Créer une app Strava sur https://www.strava.com/settings/api et obtenir un refresh token
   (voir CLAUDE.md, étapes 1 et 2).
2. Configurer les secrets GitHub : `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`,
   `STRAVA_REFRESH_TOKEN`, `STRAVA_CLUB_ID` (Settings → Secrets and variables → Actions).
3. Activer GitHub Pages sur la branche `main`, dossier `/docs`.
4. Lancer le workflow manuellement une première fois (Actions → Refresh dashboard → Run workflow).

## Test local

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export STRAVA_CLIENT_ID=...
export STRAVA_CLIENT_SECRET=...
export STRAVA_REFRESH_TOKEN=...
export STRAVA_CLUB_ID=...
python scripts/fetch_strava.py
python scripts/aggregate.py
python scripts/generate_html.py
open docs/index.html
```

## Architecture

- `scripts/fetch_strava.py` — appelle l'API Strava, écrit `data/raw_activities.json`.
- `scripts/aggregate.py` — calcule les stats et les accumule dans `docs/data.json`.
- `scripts/generate_html.py` — génère `docs/index.html` (Chart.js via CDN) à partir de l'historique.
- `.github/workflows/refresh.yml` — orchestre le tout toutes les heures et commit les changements.
