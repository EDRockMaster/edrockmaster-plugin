# edrockmaster-plugin

Plugin [EDMarketConnector](https://github.com/EDCD/EDMarketConnector) de **EDRockMaster — Elite Dangerous Rock Master Companion**.

Fonctionne seul, sans serveur : alertes du prospecteur, cores et motherlodes,
stats de session live, drones et soute. La liaison au serveur (jalon 3) est optionnelle
et tolère les coupures (file d'attente locale).

## Installation

Copier le dossier du plugin dans le dossier `plugins` d'EDMC
(*File → Settings → Plugins → Open*), puis redémarrer EDMC.

## Structure

- `load.py` : points d'entrée EDMC (`plugin_start3`, `plugin_app`, `journal_entry`…), aussi fin que possible.
- `mining/` : logique pure, sans dépendance à EDMC ni à tkinter, testée par `pytest`.
- `tests/fixtures/` : extraits de journaux réels.

## Développement

```sh
uv sync
uv run pytest
```

## Licence

GPL-3.0-or-later — voir [LICENSE](LICENSE).
