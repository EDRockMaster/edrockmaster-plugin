# edrockmaster-plugin

*English · [Français](README.fr.md)*

**EDRockMaster Companion**, the desktop application of **EDRockMaster — Elite Dangerous Rock Master Companion** (design decisions ADR 0020 and ADR 0024). The repository keeps its name until the release of 0.4.0, when it becomes `edrockmaster-desktop`.

It reads the journal that Elite Dangerous writes on the player's computer and shows, live, in a window of its own: prospector alerts, cores and motherlodes, mining statistics, limpets, cargo and sales; a combat counter per site (conflict zones in space and on the ground, resource extraction sites, navigation beacons), with bounties, combat bonds, rates per site type, fines, unredeemed vouchers and community goals; trade (profit, profit per hour of flight, routes, fleet carrier transfers); engineering (materials, caps, engineers, blueprint goals and their shopping list, and every blueprint to browse); the commander's situation. English and French. Nothing is sent anywhere; a later version will add an optional link with EDRockMaster services (step 1B).

> **The EDMC plugin is discontinued** (ADR 0024). Its last release, [0.2.2](https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2), stays available but gets no further release: use the desktop application.

## Role in the project

- **Bounded contexts** (in `edrockmaster/domain/`): mining, combat, trade, engineering and the commander's situation, computed locally from the journal (ADR 0011, 0013 to 0015, 0017 to 0019, 0023).
- **Events**: none produced or consumed today: the application works offline. In step 1B it will send its facts to the ingestion API (ADR 0005), never to a service directly.
- Engineering rules, ADRs, context map and glossary: `edrockmaster-architecture` repository.

## Installation

- **Players**: from the Microsoft Store, *EDRockMaster Companion* (Windows 10 21H1 or later, 64-bit).
- **Testers**: the portable zip of a [Windows build](https://github.com/EDRockMaster/edrockmaster-plugin/actions/workflows/windows.yml); unblock the downloaded zip (*Properties → Unblock*), extract it on a local disk and run `EDRockMaster.exe`.

What changed in each version: [changelog](CHANGELOG.md). Privacy: [privacy policy](docs/privacy.md) (nothing is sent anywhere).

## Layout

- `edrockmaster/`: the application. `domain/` and `application/` (the core) depend on no adapter and no interface; `infrastructure/` (adapters), `ui/` (presenters), `desktop/` (the composition root, the journal reader, the pywebview window). `lint-imports` checks the boundaries.
- `web/`: the interface (Svelte 5 and TypeScript, ADR 0021), built into one HTML file shipped with the application.
- `L10n/`: translations of the core's texts (`fr.strings`).
- `tests/fixtures/`: excerpts of real journals, free of personal data.
- `packaging/windows/`: PyInstaller specification and MSIX manifest (ADR 0022).
- `scripts/`: Windows packaging (`package_desktop.py`, `make_icons.py`, with the build file of ADR 0016), release notes (`release_notes.sh`), version (`version.sh`), release channel (`release_plan.py`), GitHub release (`github_release.py`), recording to test fixture (`sanitise_recording.py`), fixture to journal file (`fixture_to_journal.py`), demo journal (`make_demo_journal.py`), game data of engineering (`import_engineering_data.py`, ADR 0017).

## Documentation

- [Design of the desktop application](docs/design.md)
- [Privacy policy](docs/privacy.md), [Microsoft Store listing](docs/store-listing.md) and [Store submission](docs/store-submission.md)

## Development

```sh
uv sync
uv run pytest
cd web && corepack pnpm install && corepack pnpm build && cd ..
uv run python -m edrockmaster.desktop          # the player's journal
uv run python -m edrockmaster.desktop --demo   # a sample journal (--demo=en, --demo=fr)
```

On Linux, pywebview needs GTK and WebKit2GTK with their Python binding (PyGObject), usually from the system's Python; `EDROCKMASTER_JOURNAL_DIR` points to another journal folder. Details: [design](docs/design.md#desktop-application). The CI also runs `ruff`, `mypy --strict`, `lint-imports` and the interface's checks (`pnpm lint`, `check`, `test`).

## Releasing

No production without acceptance (ADR 0012, ADR 0022):

1. Set the new version in `pyproject.toml` and `edrockmaster/__init__.py` (`VERSION`), following SemVer, and add its entry to `CHANGELOG.md` and `CHANGELOG.fr.md`. Tests check that versions match and that both entries exist. Merge through a pull request.
2. **Candidate**: tag the merge commit `vX.Y.Z-rc.1` and push the tag. Gitea publishes the release notes as a private pre-release; the Windows build of that commit gives the MSIX, submitted in Partner Center as a **package flight** to the testers.
3. **Acceptance**: install the candidate from the Store and play. A problem: fix it through a pull request, then tag `vX.Y.Z-rc.2` on the new merge commit.
4. **Production**: tag `vX.Y.Z` on the **same commit** as the accepted candidate and push. The CI refuses a production tag without a candidate on that commit (`scripts/release_plan.py`), then publishes the notes on Gitea and GitHub, which announces the release on Discord; the production MSIX, rebuilt from that commit, is submitted to every customer.

The code keeps the version `X.Y.Z` from candidate to production; the packaging writes `edrockmaster/build.json` with the full version, the commit and the channel (ADR 0016).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

The engineering catalogue (`edrockmaster/domain/engineering/catalogue.json`) is game data of Frontier Developments, not under this licence — see [NOTICE](NOTICE).
