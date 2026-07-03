# Projet : Dashboard Strava Club

## Objectif

Créer un dashboard HTML statique qui résume les activités récentes des membres d'un club Strava, publié automatiquement sur GitHub Pages et rafraîchi périodiquement via GitHub Actions. Le lien final sera partagé avec un ami — aucune installation requise de son côté, juste un navigateur.

## ⚠️ Limitation critique à connaître avant de commencer

L'API utilisée (`GET /clubs/{id}/activities`) sera **supprimée par Strava le 1er septembre 2026**. Ce projet a donc une durée de vie garantie d'environ 2 mois à partir d'aujourd'hui (3 juillet 2026). C'est un choix assumé pour aller vite — si le projet doit vivre plus longtemps, il faudra migrer vers une authentification OAuth par membre (`activity:read`) avant cette date.

Autres limites à accepter dès le départ :
- **Pas de date par activité** : l'endpoint ne renvoie aucun timestamp. Impossible d'avoir une vue "jour par jour" fiable. On simule une notion de fraîcheur en horodatant chaque exécution du script (heure du refresh).
- **Pas d'identifiant d'athlète unique** : seuls prénom + nom sont fournis. Deux membres homonymes seront confondus. On agrège donc par nom complet.
- **Pas de champ `average_speed` direct** : à calculer soi-même (`distance / moving_time`).
- **Rate limit** : 100 requêtes / 15 min, 1000 / jour (lecture). Largement suffisant pour un refresh horaire.

## Architecture cible

```
strava-club-dashboard/
├── .github/
│   └── workflows/
│       └── refresh.yml          # cron GitHub Actions, ex: toutes les heures
├── scripts/
│   ├── fetch_strava.py          # appelle l'API, gère le refresh token
│   ├── aggregate.py             # calcule les stats (par membre, par type, cumulés)
│   └── generate_html.py         # génère index.html à partir des stats
├── docs/                        # dossier publié par GitHub Pages
│   └── index.html               # fichier généré, écrasé à chaque run
├── requirements.txt
└── README.md
```

GitHub Pages sert le contenu du dossier `docs/` sur la branche `main`. Le workflow régénère `docs/index.html` et le commit automatiquement.

## Étape 1 — Créer l'app Strava

1. Aller sur https://www.strava.com/settings/api et créer une application (nécessite un abonnement Strava actif pour le compte créateur).
2. Renseigner un nom, une catégorie, et associer le club concerné.
3. Noter `Client ID` et `Client Secret`.
4. Mettre le "Authorization Callback Domain" sur `localhost` pour la génération manuelle du token.

## Étape 2 — Obtenir un refresh token (une seule fois)

1. Construire l'URL d'autorisation avec le scope `read`:
   ```
   https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost&scope=read
   ```
2. Ouvrir dans le navigateur, autoriser, récupérer le paramètre `code` dans l'URL de redirection.
3. Échanger ce code contre un refresh token :
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=CLIENT_ID \
     -d client_secret=CLIENT_SECRET \
     -d code=AUTHORIZATION_CODE \
     -d grant_type=authorization_code
   ```
4. Conserver précieusement le `refresh_token` retourné — il ne change plus (sauf révocation).

## Étape 3 — Script `fetch_strava.py`

Doit :
- Utiliser `client_id`, `client_secret`, `refresh_token` (lus depuis des variables d'environnement, jamais en dur dans le code).
- Échanger le refresh token contre un access token à chaque exécution (`grant_type=refresh_token`).
- Appeler `GET https://www.strava.com/api/v3/clubs/{CLUB_ID}/activities?per_page=100`.
- Retourner la liste brute d'activités (chaque item contient : `athlete.firstname`, `athlete.lastname`, `name`, `distance`, `moving_time`, `elapsed_time`, `total_elevation_gain`, `type`, `sport_type`, `workout_type`).

## Étape 4 — Script `aggregate.py`

Doit calculer, à partir de la liste brute :
- Total kilomètres par membre, tous sports confondus et filtré par `type == "Run"` pour la course.
- Vitesse moyenne par activité de course : `distance (m) / moving_time (s)`, convertie en min/km ou km/h.
- Classement des membres (distance totale course sur la période récupérée).
- Répartition par type d'activité (Run, Ride, Swim, etc.) pour le club entier.
- Horodatage du run (`datetime.utcnow()`) à afficher comme "dernière mise à jour".

Important : chaque appel ne renvoie qu'un instantané récent (pas d'historique profond), donc `aggregate.py` doit soit accumuler les résultats dans un fichier JSON persistant (`docs/data.json`, committé à chaque run) pour construire un historique dans le temps, soit se contenter d'un résumé "activités récentes" sans prétendre à un historique complet. Recommandation : accumuler en JSON pour au moins avoir une tendance sur les 2 mois de vie du projet.

## Étape 5 — Script `generate_html.py`

- Lit les stats agrégées (et l'historique JSON accumulé si mis en place).
- Génère un unique fichier `docs/index.html`, autonome (CSS inline ou CDN, JS inline).
- Utiliser Chart.js via CDN pour : classement en barres, répartition par type en camembert, évolution du cumul dans le temps si l'historique JSON existe.
- Afficher clairement la date/heure de dernière mise à jour et une note discrète sur la limite de fraîcheur des données (pas de dates réelles par activité).

## Étape 6 — Workflow GitHub Actions (`refresh.yml`)

- Déclenché par `schedule` (cron, ex: `0 * * * *` pour toutes les heures) + `workflow_dispatch` pour un lancement manuel.
- Étapes : checkout → setup Python → `pip install -r requirements.txt` → exécuter les 3 scripts dans l'ordre → commit + push si `docs/index.html` ou `docs/data.json` a changé.
- Secrets nécessaires à créer dans GitHub (Settings → Secrets and variables → Actions) : `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, `STRAVA_CLUB_ID`.

## Étape 7 — Activer GitHub Pages

- Repo Settings → Pages → Source : branche `main`, dossier `/docs`.
- Le lien final sera du type `https://<username>.github.io/strava-club-dashboard/`.
- C'est ce lien unique qu'il faut partager avec l'ami — il se met à jour tout seul, aucune action de sa part.

## Étape 8 — Test local avant automatisation

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

## Checklist finale

- [ ] App Strava créée, refresh token obtenu et testé
- [ ] Les 3 scripts fonctionnent en local et produisent un `docs/index.html` correct
- [ ] Repo GitHub créé, secrets configurés
- [ ] Workflow Actions testé manuellement (`workflow_dispatch`) avant de compter sur le cron
- [ ] GitHub Pages activé, lien vérifié depuis un navigateur externe (pas juste localhost)
- [ ] Lien envoyé à l'ami
- [ ] Rappel calendrier pour migrer ou arrêter le projet avant le 1er septembre 2026 (suppression de l'endpoint)

## requirements.txt suggéré

```
requests
```

(Pas besoin de plus — pas de pandas ni de framework web, tout est généré en statique.)
