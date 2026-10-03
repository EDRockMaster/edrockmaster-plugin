# edrockmaster-plugin

*English · [Français](README.fr.md)*

[EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for **EDRockMaster — Elite Dangerous Rock Master Companion**.

Works on its own, without any server: prospector alerts, cores and motherlodes, live session stats, limpets, cargo and sales. A later version will add an optional link with EDRockMaster services (sign-in and uploads, opt-in).

User interface in English and French: the plugin follows the language selected in EDMC.

## Installation

Requires EDMC 6.1 or later.

1. Download `EDRockMaster-vX.Y.Z.zip` from the [releases](https://github.com/EDRockMaster/edrockmaster-plugin/releases).
2. In EDMC, open *File → Settings → Plugins → Open Plugins Folder* and extract the zip there: you get an `EDRockMaster` folder next to the other plugins.
3. Restart EDMC.

## Usage

- **Panel** (EDMC's main window): session status, the last prospector alert, and the session statistics. **Reset** ends the running session.
- **Settings → EDRockMaster**: alert threshold per commodity (empty means no alert), minimum content, minimum remaining reserve, cores, sound.
- **Journal recorder** (same tab, off by default): saves the journal events received by the plugin in JSONL files. *Open recordings folder* shows them; join one to a bug report.

What changed in each version: [changelog](CHANGELOG.md).

## Layout

- `load.py`: EDMC entry points (`plugin_start3`, `plugin_app`, `journal_entry`…), kept as thin as possible.
- `edrockmaster/`: the plugin code, in a uniquely named package (see [prerequisites](docs/prerequisites.md)). Domain logic depends neither on EDMC nor on tkinter, and is tested with `pytest`.
- `L10n/`: translations (`fr.strings`).
- `tests/fixtures/`: excerpts of real journals.
- `scripts/`: packaging (`package.sh`), release notes (`release_notes.sh`), version (`version.sh`).

## Documentation

- [EDMC and plugin registry prerequisites](docs/prerequisites.md)
- [Plugin design](docs/design.md)
- Engineering rules and architecture: `edrockmaster-architecture` repository

## Development

```sh
uv sync
uv run pytest
```

Widget tests use a real Tk: they run where a display exists and are skipped elsewhere (CI).

## Releasing

1. Set the new version in `pyproject.toml` and `edrockmaster/__init__.py` (`VERSION`), following SemVer.
2. Add its entry to `CHANGELOG.md` and `CHANGELOG.fr.md`. Tests check that versions match and that both entries exist.
3. Merge through a pull request, then tag the merge commit `vX.Y.Z` on Gitea and push the tag.
4. The CI checks the tag against the version, builds the zip and publishes the release, with the changelog entry as notes, on Gitea and GitHub.

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
