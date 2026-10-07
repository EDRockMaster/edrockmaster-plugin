# edrockmaster-plugin

*English · [Français](README.fr.md)*

[EDMarketConnector](https://github.com/EDCD/EDMarketConnector) (EDMC) plugin for **EDRockMaster — Elite Dangerous Rock Master Companion**.

Works on its own, without any server: prospector alerts, cores and motherlodes, live session stats, limpets, cargo and sales. Also a combat counter, per site (conflict zones in space and on the ground, resource extraction sites, navigation beacons): kills, bounties and combat bonds, kills and credits per hour by site type, miscellaneous kills, fines, unredeemed vouchers, community goals. And a trade counter: profit, profit per hour of flight, routes, cargo bought, losses, transfers with fleet carriers. A later version will add an optional link with EDRockMaster services (sign-in and uploads, opt-in).

User interface in English and French: the plugin follows the language selected in EDMC.

## Installation

Requires EDMC 6.1 or later.

1. Download `EDRockMaster-vX.Y.Z.zip` from the [releases](https://github.com/EDRockMaster/edrockmaster-plugin/releases).
2. In EDMC, open *File → Settings → Plugins → Open Plugins Folder* and extract the zip there: you get an `EDRockMaster` folder next to the other plugins.
3. Restart EDMC.

## Usage

- **Panel** (EDMC's main window): the activity in progress, mining, combat or trade. For mining: the last prospector alert and the session statistics; for combat: the current site, rates per site type, kills, credits, fines, unredeemed vouchers and community goals; for trade: flight time, profit, profit per hour, tons sold, cargo bought and one line per route. **Reset** ends the session shown. In the preferences, choose the activities shown, and whether the panel shows the last active one or stacks them all.
- **Settings → EDRockMaster**: alert threshold per commodity (empty means no alert), minimum content, minimum remaining reserve, cores, sound.
- **Journal recorder** (same tab, off by default): saves the journal events received by the plugin in JSONL files. *Open recordings folder* shows them; join one to a bug report. The tab ends with the full version of the plugin (for example `0.3.0-rc.2`): quote it too.

What changed in each version: [changelog](CHANGELOG.md).

## Layout

- `load.py`: EDMC entry points (`plugin_start3`, `plugin_app`, `journal_entry`…), kept as thin as possible.
- `edrockmaster/`: the plugin code, in a uniquely named package (see [prerequisites](docs/prerequisites.md)). Domain logic depends neither on EDMC nor on tkinter, and is tested with `pytest`.
- `L10n/`: translations (`fr.strings`).
- `tests/fixtures/`: excerpts of real journals.
- `scripts/`: packaging (`package.sh`, with the build file from `build_file.py`), release notes (`release_notes.sh`), version (`version.sh`), release channel (`release_plan.py`), GitHub release (`github_release.py`), recording to test fixture (`sanitise_recording.py`).

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

No production without acceptance (ADR 0012, in the architecture repository):

1. Set the new version in `pyproject.toml` and `edrockmaster/__init__.py` (`VERSION`), following SemVer, and add its entry to `CHANGELOG.md` and `CHANGELOG.fr.md`. Tests check that versions match and that both entries exist. Merge through a pull request.
2. **Candidate**: tag the merge commit `vX.Y.Z-rc.1` and push the tag. The CI publishes a **private pre-release on Gitea**.
3. **Acceptance**: install the candidate in EDMC and play, journal recorder on, following the milestone's in-game checklist. A problem: fix it through a pull request, then tag `vX.Y.Z-rc.2` on the new merge commit.
4. **Production**: tag `vX.Y.Z` on the **same commit** as the accepted candidate and push. The CI refuses a production tag without a candidate on that commit (`scripts/release_plan.py`), then publishes on Gitea and GitHub, with the changelog entry as notes.

The code keeps the version `X.Y.Z` from candidate to production; the packaging writes `edrockmaster/build.json` into each zip, with the full version, the commit and the channel (ADR 0016). A CI artifact is `X.Y.Z-dev+<commit>`, a clone runs as `X.Y.Z-dev`.

Every CI run also keeps the zip as an artifact (dev builds, 14 days).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).
