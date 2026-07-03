# Projet : Dashboard Strava Club

## Objectif

Créer un dashboard HTML statique qui résume les activités récentes des membres d'un club Strava, publié automatiquement sur GitHub Pages et rafraîchi périodiquement via GitHub Actions. Le lien final sera partagé avec un ami — aucune installation requise de son côté, juste un navigateur.

## ⚠️ Limitation critique à connaître avant de commencer

L'API utilisée (`GET /clubs/{id}/activities`) sera **supprimée par Strava le 1er septembre 2026**. Ce projet a donc une durée de vie garantie d'environ 2 mois à partir d'aujourd'hui (3 juillet 2026). C'est un choix assumé pour aller vite — si le projet doit vivre plus longtemps, il faudra migrer vers une authentification OAuth par membre (`activity:read`) avant cette date.

Autres limites à accepter dès le départ :
- **Pas de date par activité** : l'endpoint ne renvoie aucun timestamp. Impossible d'avoir une vue "jour par jour" fiable. On simule une notion de fraîcheur en horodatant chaque exécution du script (heure du refresh). → Voir Étape 9 pour le plan de contournement (empreinte de contenu + date de première détection).
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
│   ├── generate_html.py         # génère index.html à partir des stats
│   └── excluded_activities.json # (V2, Étape 9) liste statique de hashs à exclure
├── data/
│   ├── raw_activities.json      # (V2) dernier instantané brut, écrasé à chaque run
│   └── raw_snapshots/           # (V2, Étape 9) archive de chaque instantané, jamais écrasée
├── docs/                        # dossier publié par GitHub Pages
│   ├── index.html               # fichier généré, écrasé à chaque run
│   ├── data.json                # historique par instantané (V1, voir Étape 9 pour son statut)
│   └── activities_seen.json     # (V2, Étape 9) ledger hash -> date de première détection
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

## Étape 9 — Reconstruction d'un historique daté via empreintes d'activité (V2)

**Statut : plan validé, pas encore implémenté.**

Constat : `raw_activities.json` ne fournit ni identifiant, ni date par activité (confirmé en
inspectant la réponse réelle de l'API — le champ n'existe tout simplement pas). Sans ID, deux
exécutions successives ne peuvent pas savoir si elles voient la même activité ou une nouvelle.
Le plan ci-dessous transforme "la première fois que notre cron a vu cette activité" en une
approximation de sa date de création, ce qui permet de reconstruire une vraie série temporelle —
chose jugée impossible dans les limitations initiales de ce projet (voir plus haut).

Au passage, le dashboard actuel (généré par `generate_html.py`) a été entièrement reconstruit
sur un design "Club Activity Board" (classements par sport, cartes athlètes, composition de
l'effort, records — voir `design_handoff_club_dashboard/`), lu directement depuis
`data/raw_activities.json` plutôt que depuis `docs/data.json`. C'est une vue "instantané", sans
dimension temporelle, cohérente avec le fait qu'on ne pouvait alors pas dater les activités.
L'étape 9 lève cette contrainte.

### 1. Empreinte d'activité (hash)

Puisqu'il n'y a pas d'ID Strava, on calcule un hash de contenu (sha256 tronqué) à partir de :
nom complet de l'athlète, `type`, `distance`, `moving_time`, `elapsed_time`,
`total_elevation_gain`, `name` (titre de l'activité).

**Limite acceptée** : deux activités strictement identiques sur tous ces champs (même athlète,
mêmes valeurs, même titre) seraient fusionnées à tort. Risque jugé faible en pratique, mais pas
nul — même famille de compromis que la limite "homonymes" déjà acceptée pour les noms d'athlètes.

### 2. Archive brute — ne jamais rien perdre

`fetch_strava.py` doit, en plus d'écraser `data/raw_activities.json` (dernier instantané, utilisé
tel quel par la vue "Agrégation"), archiver **chaque** réponse brute dans
`data/raw_snapshots/<timestamp>.json` (fichier jamais écrasé, jamais supprimé). Objectif : ne
perdre aucune donnée, et pouvoir reconstruire le ledger ci-dessous depuis zéro en rejouant tout
l'historique brut si jamais sa logique doit être corrigée ou refaite.

### 3. Ledger `docs/activities_seen.json`

`aggregate.py` maintient un fichier `docs/activities_seen.json` :
`hash -> { first_seen, athlete, sport, distance, moving_time, elevation, title }`.

- Un hash déjà présent n'est **jamais** réécrit (son `first_seen` reste la première détection).
- Un hash absent du ledger et absent de la liste d'exclusion est ajouté avec
  `first_seen` = horodatage de ce run.
- Ce ledger devient la source d'une vraie vue "série temporelle" (groupement par date réelle
  approximative, par jour ou semaine, par membre) — enfin possible malgré l'absence de date
  native dans l'API.

### 4. Liste d'exclusion statique

`scripts/excluded_activities.json` : simple tableau de hashs, maintenu à la main, pour retirer
définitivement une activité précise du dashboard (test, doublon, activité à ne pas montrer).
Filtré avant tout calcul dans `aggregate.py` — un hash exclu n'entre jamais dans le ledger.

### 5. Toggle sur le dashboard

`generate_html.py` ajoute un bouton en haut de page pour basculer entre deux vues :
- **Agrégation** — la vue actuelle "Club Activity Board", construite à partir de
  `data/raw_activities.json` (fenêtre récente glissante de l'API, sans dimension temporelle).
- **Série temporelle** — nouvelle vue construite à partir de `docs/activities_seen.json`,
  groupée par `first_seen`, avec un vrai graphe d'évolution jour/semaine par membre.

### Limites à garder en tête

- `first_seen` approxime la date de création à la précision du cron (± 1h), et seulement à
  partir du déploiement de ce système — impossible de dater rétroactivement des activités qui
  auraient disparu de la fenêtre récente de l'API avant ce déploiement.
- `data/raw_snapshots/` grossit indéfiniment (quelques dizaines de Mo estimées sur les ~2 mois de
  vie restants du projet avant la suppression de l'endpoint) — jugé acceptable vu la taille.
- `docs/data.json` (l'ancien historique par instantané agrégé, V1) devient obsolète une fois ce
  ledger en place. Conservé pour l'instant (le workflow continue à l'alimenter) mais plus lu par
  le dashboard — à supprimer plus tard s'il reste inutilisé.

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
