# edrockmaster-plugin

*English · [Français](README.fr.md)*

[EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for **EDRockMaster — Elite Dangerous Rock Master Companion**.

Works on its own, without any server: prospector alerts, cores and motherlodes, live session stats, limpets and cargo. The link with EDRockMaster services is optional: it requires signing in and enabling uploads, and it survives outages (local queue).

User interface in English and French: the plugin follows the language selected in EDMC.

## Installation

Copy the `EDRockMaster` folder from the release zip into EDMC's `plugins` folder (*File → Settings → Plugins → Open*), then restart EDMC.

## Layout

- `load.py`: EDMC entry points (`plugin_start3`, `plugin_app`, `journal_entry`…), kept as thin as possible.
- `edrockmaster/`: the plugin code, in a uniquely named package (see [prerequisites](docs/prerequisites.md)). Domain logic depends neither on EDMC nor on tkinter, and is tested with `pytest`.
- `L10n/`: translations (`fr.strings`).
- `tests/fixtures/`: excerpts of real journals.

## Documentation

- [EDMC and plugin registry prerequisites](docs/prerequisites.md)
- Engineering rules and architecture: `edrockmaster-architecture` repository

## Development

```sh
uv sync
uv run pytest
```

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
