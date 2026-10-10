# edrockmaster-plugin

*[English](README.md) · Français*

**EDRockMaster Companion**, l'application de bureau d'**EDRockMaster — Elite Dangerous Rock Master Companion** (décisions de conception ADR 0020 et ADR 0024). Le dépôt garde son nom jusqu'à la sortie de la 0.4.0, où il devient `edrockmaster-desktop`.

Elle lit le journal qu'Elite Dangerous écrit sur l'ordinateur du joueur et affiche en direct, dans sa propre fenêtre : alertes du prospecteur, cores et filons-mères, statistiques de minage, drones, soute et ventes ; un compteur de combat par site (zones de conflit dans l'espace et au sol, sites d'extraction de ressources, balises de navigation), avec les primes, les obligations de combat, les ratios par type de site, les amendes, les bons non encaissés et les objectifs communautaires ; le commerce (bénéfice, bénéfice par heure de vol, routes, transferts avec les porte-vaisseaux) ; l'ingénierie (matériaux, plafonds, ingénieurs, objectifs de blueprints et leur liste de courses, et tous les blueprints à parcourir) ; la situation du commandant. En français et en anglais. Rien n'est envoyé nulle part ; une version ultérieure ajoutera une liaison facultative avec les services d'EDRockMaster (étape 1B).

> **Le plugin EDMC est arrêté** (ADR 0024). Sa dernière version, la [0.2.2](https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2), reste disponible mais n'en aura plus d'autre : utilisez l'application de bureau.

## Rôle dans le projet

- **Contextes délimités** (dans `edrockmaster/domain/`) : minage, combat, commerce, ingénierie et situation du commandant, calculés en local depuis le journal (ADR 0011, 0013 à 0015, 0017 à 0019, 0023).
- **Événements** : aucun produit ni consommé aujourd'hui : l'application fonctionne hors ligne. À l'étape 1B, elle enverra ses faits à l'API d'ingestion (ADR 0005), jamais directement à un service.
- Règles d'ingénierie, ADR, carte des contextes et glossaire : dépôt `edrockmaster-architecture`.

## Installation

- **Joueurs** : depuis le Microsoft Store, *EDRockMaster Companion* (Windows 10 21H1 ou plus récent, 64 bits).
- **Testeurs** : le zip portable d'un [build Windows](https://github.com/EDRockMaster/edrockmaster-plugin/actions/workflows/windows.yml) ; débloquer le zip téléchargé (*Propriétés → Débloquer*), l'extraire sur un disque local et lancer `EDRockMaster.exe`.

Ce qui a changé à chaque version : [journal des modifications](CHANGELOG.fr.md). Données personnelles : [politique de confidentialité](docs/privacy.fr.md) (rien n'est envoyé nulle part).

## Structure

- `edrockmaster/` : l'application. `domain/` et `application/` (le cœur) ne dépendent d'aucun adaptateur ni d'aucune interface ; `infrastructure/` (adaptateurs), `ui/` (présentateurs), `desktop/` (la racine de composition, le lecteur de journal, la fenêtre pywebview). `lint-imports` vérifie les frontières.
- `web/` : l'interface (Svelte 5 et TypeScript, ADR 0021), construite en un seul fichier HTML livré avec l'application.
- `L10n/` : traductions des textes du cœur (`fr.strings`).
- `tests/fixtures/` : extraits de vrais journaux, sans données personnelles.
- `packaging/windows/` : spécification PyInstaller et manifeste MSIX (ADR 0022).
- `scripts/` : emballage Windows (`package_desktop.py`, `make_icons.py`, avec le fichier de build de l'ADR 0016), notes de version (`release_notes.sh`), version (`version.sh`), canal de release (`release_plan.py`), release GitHub (`github_release.py`), enregistrement vers donnée de test (`sanitise_recording.py`), donnée de test vers fichier de journal (`fixture_to_journal.py`), journal de démo (`make_demo_journal.py`), données du jeu pour l'ingénierie (`import_engineering_data.py`, ADR 0017).

## Documentation

- [Conception de l'application de bureau](docs/design.fr.md)
- [Politique de confidentialité](docs/privacy.fr.md), [fiche du Microsoft Store](docs/store-listing.fr.md) et [soumission au Store](docs/store-submission.fr.md)

## Développement

```sh
uv sync
uv run pytest
cd web && corepack pnpm install && corepack pnpm build && cd ..
uv run python -m edrockmaster.desktop          # le journal du joueur
uv run python -m edrockmaster.desktop --demo   # un journal d'exemple (--demo=en, --demo=fr)
```

Sous Linux, pywebview a besoin de GTK et de WebKit2GTK avec leur liaison Python (PyGObject), en général celle de la Python du système ; `EDROCKMASTER_JOURNAL_DIR` désigne un autre dossier de journal. Détails : [conception](docs/design.fr.md#application-de-bureau). La CI lance aussi `ruff`, `mypy --strict`, `lint-imports` et les contrôles de l'interface (`pnpm lint`, `check`, `test`).

## Publier une version

Pas de production sans recette (ADR 0012, ADR 0022) :

1. Mettre la nouvelle version dans `pyproject.toml` et `edrockmaster/__init__.py` (`VERSION`), selon SemVer, et ajouter son entrée à `CHANGELOG.md` et `CHANGELOG.fr.md`. Les tests vérifient que les versions concordent et que les deux entrées existent. Fusionner par une PR.
2. **Candidate** : taguer le commit de fusion `vX.Y.Z-rc.1` et pousser le tag. Gitea publie les notes de version en pré-release privée ; le build Windows de ce commit donne le MSIX, soumis dans Partner Center en **vol de paquet** aux testeurs.
3. **Recette** : installer la candidate depuis le Store et jouer. Un problème : le corriger par une PR, puis taguer `vX.Y.Z-rc.2` sur le nouveau commit de fusion.
4. **Production** : taguer `vX.Y.Z` sur le **même commit** que la candidate recettée et pousser. La CI refuse un tag de production sans candidate sur ce commit (`scripts/release_plan.py`), puis publie les notes sur Gitea et GitHub, qui annonce la version sur Discord ; le MSIX de production, reconstruit depuis ce commit, est soumis à tous les clients.

Le code garde la version `X.Y.Z` de la candidate à la production ; l'emballage écrit `edrockmaster/build.json` avec la version complète, le commit et le canal (ADR 0016).

## Licence

GPL-3.0-or-later — voir [LICENSE](LICENSE).

Le catalogue d'ingénierie (`edrockmaster/domain/engineering/catalogue.json`) contient des données du jeu appartenant à Frontier Developments, hors de cette licence — voir [NOTICE](NOTICE).
