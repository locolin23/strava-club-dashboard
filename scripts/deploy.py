#!/usr/bin/env python3
"""Déploie les changements locaux (ex : scripts/excluded_activities.json) : synchronise avec
origin/main (en gérant automatiquement les conflits de rebase sur docs/index.html, un fichier
généré, puisque le cron horaire pousse un commit toutes les heures), commit, push, puis déclenche
le workflow GitHub Actions pour que le pipeline tourne avec les vraies données et les secrets du
repo.

Usage :
    python scripts/deploy.py ["message de commit"]
"""

import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO = "locolin23/strava-club-dashboard"
WORKFLOW = "refresh.yml"

# Chemins volontairement exclus du commit (matériel de référence, config personnelle locale).
EXCLUDE_PATHSPECS = [":!design_handoff_club_dashboard", ":!.claude"]


def run(cmd, check=True, capture=False):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR, text=True, capture_output=capture)
    if check and result.returncode != 0:
        if capture:
            print(result.stdout)
            print(result.stderr)
        raise SystemExit(f"Échec de la commande : {' '.join(cmd)}")
    return result


def has_staged_changes():
    result = run(["git", "diff", "--cached", "--quiet"], check=False)
    return result.returncode != 0


def regenerate_dashboard():
    run([sys.executable, "scripts/generate_html.py"])


def sync_with_remote():
    """Récupère et rebase sur origin/main. Si le seul conflit porte sur docs/index.html (fichier
    généré, jamais édité à la main), le régénère et poursuit le rebase automatiquement. Tout
    autre conflit est jugé inattendu -- le rebase est annulé pour résolution manuelle plutôt que
    de deviner."""
    run(["git", "fetch", "origin"])
    result = run(["git", "rebase", "origin/main"], check=False)
    if result.returncode == 0:
        return

    status = run(["git", "status", "--porcelain"], capture=True).stdout
    conflicted = [line[3:] for line in status.splitlines() if line.startswith("UU ")]

    if conflicted == ["docs/index.html"]:
        print("Conflit sur docs/index.html (fichier généré) -- régénération automatique.")
        regenerate_dashboard()
        run(["git", "add", "docs/index.html"])
        run(["git", "rebase", "--continue"])
    else:
        run(["git", "rebase", "--abort"], check=False)
        raise SystemExit(
            f"Conflit de rebase inattendu sur {conflicted or 'fichier(s) inconnu(s)'} -- "
            "résolution manuelle nécessaire (rebase annulé, rien n'a été perdu)."
        )


def main():
    commit_message = sys.argv[1] if len(sys.argv) > 1 else "Update dashboard config"

    # Commit localement d'abord : `git rebase` refuse de démarrer avec des changements non
    # committés dans l'arbre de travail, même sans rapport avec ce qui arrive du remote.
    run(["git", "add", "--", ".", *EXCLUDE_PATHSPECS])
    committed = has_staged_changes()
    if committed:
        run(["git", "commit", "-m", commit_message])
    else:
        print("Aucun changement local à committer.")

    sync_with_remote()

    if committed:
        run(["git", "push"])
        print("\nChangements poussés sur main.")

    print("Déclenchement du workflow GitHub Actions (fetch -> aggregate -> generate)...")
    run(["gh", "workflow", "run", WORKFLOW, "--repo", REPO])
    print(f"Suivi : https://github.com/{REPO}/actions")


if __name__ == "__main__":
    main()
