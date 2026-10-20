# edrockmaster-plugin

*[English](README.md) · Français*

**EDRockMaster Companion**, l'application de bureau d'**EDRockMaster — Elite Dangerous Rock Master Companion** (décisions de conception ADR 0020 et ADR 0024). Le dépôt garde son nom jusqu'à la sortie de la 0.4.0, où il devient `edrockmaster-desktop`.

Elle lit le journal qu'Elite Dangerous écrit sur l'ordinateur du joueur et affiche en direct, dans sa propre fenêtre : alertes du prospecteur, cores et filons-mères, statistiques de minage, drones, soute et ventes ; un compteur de combat par site (zones de conflit dans l'espace et au sol, sites d'extraction de ressources, balises de navigation), avec les primes, les obligations de combat, les ratios par type de site, les amendes et les bons non encaissés ; les objectifs communautaires rejoints, avec leur échéance ; le commerce (bénéfice, bénéfice par heure de vol, routes, transferts avec les porte-vaisseaux, le marché de la station comparé à la galaxie, la valeur de la soute, les prix de chaque marchandise dans la galaxie, et où l'acheter et la vendre) ; l'ingénierie (matériaux, plafonds, ingénieurs, objectifs de blueprints et leur liste de courses, et tous les blueprints à parcourir), et à pied (matériaux du casier du vaisseau et du sac, combinaisons et armes, ingénieurs à pied, matériaux déplacés vers le porte-vaisseaux du joueur) ; la situation du commandant. En français et en anglais. Rien ne quitte l'ordinateur aujourd'hui ; les versions suivantes ouvriront des portes facultatives, chacune fermée par défaut (ci-dessous).

> **Le plugin EDMC est arrêté** (ADR 0024). Sa dernière version, la [0.2.2](https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2), reste disponible mais n'en aura plus d'autre : utilisez l'application de bureau.

## Rôle dans le projet

- **Contextes délimités** (dans `edrockmaster/domain/`) : minage, combat, commerce, ingénierie et situation du commandant, calculés en local depuis le journal (ADR 0011, 0013 à 0015, 0017 à 0019, 0023, 0027, 0029).
- **Événements** : aucun produit ni consommé aujourd'hui : l'application fonctionne hors ligne, et reste complète toutes portes fermées (ADR 0026).
- **Dialogues** (ADR 0028) : l'application ne parle qu'aux portes que cet ADR liste, chacune ouverte par le joueur dans *Réglages* :
  - les services d'EDRockMaster, une fois un compte lié (étape 1B) : les entrées du journal réduites à une liste blanche envoyées à l'API d'ingestion (ADR 0005), les données lues par la passerelle GraphQL (ADR 0004) ; jamais directement à un service ;
  - EDDN, le réseau de données de la communauté, envoyé par l'application elle-même, sans compte ;
  - plus tard, Inara et EDSM, avec la clé du joueur.

  Elle ne parle jamais à Frontier : ce que seule l'API Companion de Frontier dit (le contenu d'un porte-vaisseaux, le marché de la station) vient des services d'EDRockMaster. Ses propres secrets (le jeton de connexion, les clés du joueur) sont rangés dans le gestionnaire d'identifiants de Windows ; aucun secret du projet n'y est livré.
- Règles d'ingénierie, ADR, carte des contextes et glossaire : dépôt `edrockmaster-architecture`.

## Installation

- **Joueurs** : télécharger `EDRockMaster.Companion-stable-Setup.exe` depuis la [dernière release](https://github.com/EDRockMaster/edrockmaster-plugin/releases/latest) et le lancer (Windows 10 ou plus récent, 64 bits). Il installe sans droits d'administrateur, ajoute l'application au menu Démarrer et au bureau, et l'application se met ensuite à jour d'elle-même (ADR 0053). L'installeur n'est pas encore signé : Windows peut avertir d'un éditeur inconnu, *Informations complémentaires*, puis *Exécuter quand même*. Désinstaller depuis *Applications installées* : vos données restent dans `%LOCALAPPDATA%\EDRockMaster`. Sans installer : le zip portable de la même release.
- **Testeurs** : choisir *Bêta* dans *Réglages*, *Mises à jour* pour recevoir aussi les candidates, ou installer `EDRockMaster.Companion-beta-Setup.exe` depuis la dernière pré-release. Un build de développement : le zip d'un [build Windows](https://github.com/EDRockMaster/edrockmaster-plugin/actions/workflows/windows.yml) ; le débloquer (*Propriétés → Débloquer*), l'extraire sur un disque local et lancer `EDRockMaster.exe`.

Ce qui a changé à chaque version : [journal des modifications](CHANGELOG.fr.md). Données personnelles : [politique de confidentialité](docs/privacy.fr.md) (rien ne nous est envoyé).

## Structure

- `edrockmaster/` : l'application. `domain/` et `application/` (le cœur) ne dépendent d'aucun adaptateur ni d'aucune interface ; `infrastructure/` (adaptateurs), `ui/` (présentateurs), `desktop/` (la racine de composition, le lecteur de journal, la fenêtre pywebview). `lint-imports` vérifie les frontières.
- `web/` : l'interface (Svelte 5 et TypeScript, ADR 0021), construite en un seul fichier HTML livré avec l'application.
- `L10n/` : traductions des textes du cœur (`fr.strings`).
- `tests/fixtures/` : extraits de vrais journaux, sans données personnelles.
- `packaging/windows/` : spécification PyInstaller (ADR 0020) ; Velopack empaquette son dossier dans le workflow Windows (ADR 0053).
- `scripts/` : emballage Windows (`package_desktop.py`, `make_icons.py`, avec le fichier de build de l'ADR 0016), notes de version (`release_notes.sh`), version (`version.sh`), canal de release (`release_plan.py`), barrière du build Windows sur Gitea (`windows_build_gate.py`, ADR 0034), release GitHub, complétée et publiée (`github_release.py`), enregistrement vers donnée de test (`sanitise_recording.py`), donnée de test vers fichier de journal (`fixture_to_journal.py`), journal de démo (`make_demo_journal.py`), données du jeu pour l'ingénierie (`import_engineering_data.py`, ADR 0017, ADR 0027).

## Documentation

- [Conception de l'application de bureau](docs/design.fr.md)
- [Politique de confidentialité](docs/privacy.fr.md)

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

Pas de production sans recette (ADR 0012, ADR 0053) :

1. Mettre la nouvelle version dans `pyproject.toml` et `edrockmaster/__init__.py` (`VERSION`), selon SemVer, et ajouter son entrée à `CHANGELOG.md` et `CHANGELOG.fr.md`. Les tests vérifient que les versions concordent et que les deux entrées existent. Fusionner par une PR.
2. **Candidate** : taguer le commit de fusion `vX.Y.Z-rc.1` et pousser le tag. Le build Windows l'empaquette avec Velopack pour le canal de mise à jour **bêta** et laisse sa release GitHub en brouillon ; la CI Gitea lui donne ses notes, copie ses fichiers dans une release Gitea et la publie en **pré-release**. Les applications du canal bêta s'y mettent à jour.
3. **Recette** : jouer avec la candidate, installée avec son installeur `beta` ou mise à jour sur le canal bêta. Un problème : le corriger par une PR, puis taguer `vX.Y.Z-rc.2` sur le nouveau commit de fusion.
4. **Production** : taguer `vX.Y.Z` sur le **même commit** que la candidate recettée et pousser. La CI refuse un tag de production sans candidate sur ce commit (`scripts/release_plan.py`) ; le build Windows l'empaquette pour les canaux **stable** et **bêta**, et la CI Gitea la publie en release sur GitHub, qui l'annonce sur Discord, et sur Gitea. Les applications installées se mettent à jour d'elles-mêmes.

Le code garde la version `X.Y.Z` de la candidate à la production ; l'emballage écrit `edrockmaster/build.json` avec la version complète, le commit et le canal (ADR 0016).

## Licence

GPL-3.0-or-later — voir [LICENSE](LICENSE).

Le catalogue d'ingénierie (`edrockmaster/domain/engineering/catalogue.json`) contient des données du jeu appartenant à Frontier Developments, hors de cette licence — voir [NOTICE](NOTICE).
