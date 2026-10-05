# edrockmaster-plugin

*[English](README.md) · Français*

Plugin [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) de **EDRockMaster — Elite Dangerous Rock Master Companion**.

Fonctionne seul, sans serveur : alertes du prospecteur, cores et filons-mères, statistiques de session en direct, drones, soute et ventes. Aussi un compteur de combat, par site (zones de conflit, sites d'extraction de ressources, balises de navigation) : victimes, primes et obligations de combat, victimes et crédits par heure selon le type de site, victimes diverses, amendes, bons non encaissés, objectifs communautaires. Une version ultérieure ajoutera une liaison facultative avec les services d'EDRockMaster (connexion et envois, sur option).

Interface en français et en anglais : le plugin suit la langue choisie dans EDMC.

## Installation

Demande EDMC 6.1 ou plus récent.

1. Télécharger `EDRockMaster-vX.Y.Z.zip` depuis les [releases](https://github.com/EDRockMaster/edrockmaster-plugin/releases).
2. Dans EDMC, ouvrir *Fichier → Paramètres → Plugins → Open Plugins Folder* (bouton non traduit dans EDMC) et y extraire le zip : on obtient un dossier `EDRockMaster` à côté des autres plugins.
3. Redémarrer EDMC.

## Utilisation

- **Panneau** (fenêtre principale d'EDMC) : l'activité en cours, minage ou combat. Pour le minage : la dernière alerte du prospecteur et les statistiques de la session ; pour le combat : le site en cours, les ratios par type de site, victimes, crédits, amendes, bons non encaissés et objectifs communautaires. **Réinitialiser** termine la session affichée.
- **Paramètres → EDRockMaster** : seuil d'alerte par commodité (vide : pas d'alerte), teneur minimale, réserve minimale, cores, son.
- **Enregistreur du journal** (même onglet, désactivé par défaut) : enregistre les événements du journal reçus par le plugin dans des fichiers JSONL. *Ouvrir le dossier des enregistrements* les affiche ; en joindre un à un signalement de bogue.

Les changements de chaque version : [journal des modifications](CHANGELOG.fr.md).

## Structure

- `load.py` : points d'entrée EDMC (`plugin_start3`, `plugin_app`, `journal_entry`…), aussi fin que possible.
- `edrockmaster/` : le code du plugin, dans un paquet au nom unique (voir [prérequis](docs/prerequisites.fr.md)). La logique de domaine ne dépend ni d'EDMC ni de tkinter, et elle est testée par `pytest`.
- `L10n/` : traductions (`fr.strings`).
- `tests/fixtures/` : extraits de journaux réels.
- `scripts/` : emballage (`package.sh`), notes de release (`release_notes.sh`), version (`version.sh`), canal de release (`release_plan.py`), release GitHub (`github_release.py`), enregistrement vers données de test (`sanitise_recording.py`).

## Documentation

- [Prérequis EDMC et registre de plugins](docs/prerequisites.fr.md)
- [Conception du plugin](docs/design.fr.md)
- Règles d'ingénierie et architecture : dépôt `edrockmaster-architecture`

## Développement

```sh
uv sync
uv run pytest
```

Les tests des widgets utilisent un vrai Tk : ils tournent là où il y a un affichage et sont sautés ailleurs (CI).

## Publier une version

Pas de production sans recette (ADR 0012, dans le dépôt d'architecture) :

1. Indiquer la nouvelle version dans `pyproject.toml` et `edrockmaster/__init__.py` (`VERSION`), selon SemVer, et ajouter son entrée à `CHANGELOG.md` et `CHANGELOG.fr.md`. Les tests vérifient que les versions concordent et que les deux entrées existent. Fusionner par une pull request.
2. **Candidate** : taguer le commit de fusion `vX.Y.Z-rc.1` et pousser le tag. La CI publie une **pré-release privée sur Gitea**.
3. **Recette** : installer la candidate dans EDMC et jouer, enregistreur du journal activé, en suivant la liste de vérifications en jeu du jalon. En cas de problème : le corriger par une pull request, puis taguer `vX.Y.Z-rc.2` sur le nouveau commit de fusion.
4. **Production** : taguer `vX.Y.Z` sur le **même commit** que la candidate validée et pousser. La CI refuse un tag de production sans candidate sur ce commit (`scripts/release_plan.py`), puis publie sur Gitea et GitHub, avec l'entrée du journal des modifications comme notes.

Chaque passage de la CI garde aussi le zip en artefact (versions de dev, 14 jours).

## Licence

GPL-3.0-or-later — voir [LICENSE](LICENSE).
