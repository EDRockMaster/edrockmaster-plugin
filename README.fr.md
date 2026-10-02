# edrockmaster-plugin

*[English](README.md) · Français*

Plugin [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) de **EDRockMaster — Elite Dangerous Rock Master Companion**.

Fonctionne seul, sans serveur : alertes du prospecteur, cores et motherlodes, stats de session live, drones et soute. La liaison avec les services EDRockMaster est facultative : elle demande de se connecter et d'activer l'envoi, et elle tolère les coupures (file d'attente locale).

Interface en français et en anglais : le plugin suit la langue choisie dans EDMC.

## Installation

Copier le dossier `EDRockMaster` du zip de la release dans le dossier `plugins` d'EDMC (*File → Settings → Plugins → Open*), puis redémarrer EDMC.

## Structure

- `load.py` : points d'entrée EDMC (`plugin_start3`, `plugin_app`, `journal_entry`…), aussi fin que possible.
- `edrockmaster/` : le code du plugin, dans un paquet au nom unique (voir [prérequis](docs/prerequisites.fr.md)). La logique de domaine ne dépend ni d'EDMC ni de tkinter, et elle est testée par `pytest`.
- `L10n/` : traductions (`fr.strings`).
- `tests/fixtures/` : extraits de journaux réels.

## Documentation

- [Prérequis EDMC et registre de plugins](docs/prerequisites.fr.md)
- [Conception du plugin](docs/design.fr.md)
- Règles d'ingénierie et architecture : dépôt `edrockmaster-architecture`

## Développement

```sh
uv sync
uv run pytest
```

## Licence

GPL-3.0-or-later — voir [LICENSE](LICENSE).
