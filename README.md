# edrockmaster-plugin

*English · [Français](README.fr.md)*

**EDRockMaster Companion**, the desktop application of **EDRockMaster — Elite Dangerous Rock Master Companion** (design decisions ADR 0020 and ADR 0024). The repository keeps its name until the release of 0.4.0, when it becomes `edrockmaster-desktop`.

It reads the journal that Elite Dangerous writes on the player's computer and shows, live, in a window of its own: prospector alerts, cores and motherlodes, mining statistics, limpets, cargo and sales; a combat counter per site (conflict zones in space and on the ground, resource extraction sites, navigation beacons), with bounties, combat bonds, rates per site type, fines and unredeemed vouchers; the community goals joined, with their expiry; trade (profit, profit per hour of flight, routes, fleet carrier transfers, the station's market compared with the galaxy, the cargo's worth, each commodity's prices across the galaxy, and where to buy and sell it); engineering (materials, caps, engineers, blueprint goals and their shopping list, and every blueprint to browse), and on foot (materials in the ship locker and the backpack, suits and weapons, on-foot engineers, materials moved to the player's fleet carrier); the commander's situation. English and French. Nothing leaves the computer today; later versions open optional doors, each off by default (below).

> **The EDMC plugin is discontinued** (ADR 0024). Its last release, [0.2.2](https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2), stays available but gets no further release: use the desktop application.

## Role in the project

- **Bounded contexts** (in `edrockmaster/domain/`): mining, combat, trade, engineering and the commander's situation, computed locally from the journal (ADR 0011, 0013 to 0015, 0017 to 0019, 0023, 0027, 0029).
- **Events**: none produced or consumed today: the application works offline, and stays complete with every door closed (ADR 0026).
- **Dialogues** (ADR 0028): the application only talks to the doors that ADR lists, each turned on by the player in *Settings*:
  - EDRockMaster services, once an account is linked (step 1B): journal entries reduced to an allow-list sent to the ingestion API (ADR 0005), data read through the GraphQL gateway (ADR 0004); never to a service directly;
  - EDDN, the community's data network, sent by the application itself, no account needed;
  - later, Inara and EDSM, with the player's own key.

  It never talks to Frontier: what only Frontier's Companion API tells (a fleet carrier's content, the docked market) comes from EDRockMaster services. Its own secrets (the sign-in token, the player's keys) are kept in the Windows Credential Manager; no secret of the project ships in it.
- Engineering rules, ADRs, context map and glossary: `edrockmaster-architecture` repository.

## Installation

- **Players**: download `EDRockMaster.Companion-stable-Setup.exe` from the [latest release](https://github.com/EDRockMaster/edrockmaster-plugin/releases/latest) and run it (Windows 10 or later, 64-bit). It installs without administrator rights, adds the application to the Start menu and the desktop, and the application then updates itself (ADR 0053). The installer is not signed yet: Windows may warn about an unknown publisher, *More info*, then *Run anyway*. Uninstall from *Installed apps*: your data stays in `%LOCALAPPDATA%\EDRockMaster`. Without installing: the portable zip of the same release.
- **Testers**: choose *Beta* in *Settings*, *Updates* to get the release candidates too, or install `EDRockMaster.Companion-beta-Setup.exe` from the latest pre-release. A development build: the zip of a [Windows build](https://github.com/EDRockMaster/edrockmaster-plugin/actions/workflows/windows.yml); unblock it (*Properties → Unblock*), extract it on a local disk and run `EDRockMaster.exe`.

What changed in each version: [changelog](CHANGELOG.md). Privacy: [privacy policy](docs/privacy.md) (nothing is sent to us).

## Layout

- `edrockmaster/`: the application. `domain/` and `application/` (the core) depend on no adapter and no interface; `infrastructure/` (adapters), `ui/` (presenters), `desktop/` (the composition root, the journal reader, the pywebview window). `lint-imports` checks the boundaries.
- `web/`: the interface (Svelte 5 and TypeScript, ADR 0021), built into one HTML file shipped with the application.
- `L10n/`: translations of the core's texts (`fr.strings`).
- `tests/fixtures/`: excerpts of real journals, free of personal data.
- `packaging/windows/`: PyInstaller specification (ADR 0020); Velopack packs its folder in the Windows workflow (ADR 0053).
- `scripts/`: Windows packaging (`package_desktop.py`, `make_icons.py`, with the build file of ADR 0016), release notes (`release_notes.sh`), version (`version.sh`), release channel (`release_plan.py`), Windows build gate on Gitea (`windows_build_gate.py`, ADR 0034), GitHub release, finished and published (`github_release.py`), recording to test fixture (`sanitise_recording.py`), fixture to journal file (`fixture_to_journal.py`), demo journal (`make_demo_journal.py`), game data of engineering (`import_engineering_data.py`, ADR 0017, ADR 0027).

## Documentation

- [Design of the desktop application](docs/design.md)
- [Privacy policy](docs/privacy.md)

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

No production without acceptance (ADR 0012, ADR 0053):

1. Set the new version in `pyproject.toml` and `edrockmaster/__init__.py` (`VERSION`), following SemVer, and add its entry to `CHANGELOG.md` and `CHANGELOG.fr.md`. Tests check that versions match and that both entries exist. Merge through a pull request.
2. **Candidate**: tag the merge commit `vX.Y.Z-rc.1` and push the tag. The Windows build packs it with Velopack for the **beta** update channel and leaves its GitHub release as a draft; the Gitea CI gives it its notes, copies its files to a Gitea release and publishes it as a **pre-release**. Applications on the beta channel update to it.
3. **Acceptance**: play with the candidate, installed with its `beta` installer or updated on the beta channel. A problem: fix it through a pull request, then tag `vX.Y.Z-rc.2` on the new merge commit.
4. **Production**: tag `vX.Y.Z` on the **same commit** as the accepted candidate and push. The CI refuses a production tag without a candidate on that commit (`scripts/release_plan.py`); the Windows build packs it for the **stable** and **beta** channels, and the Gitea CI publishes it as a release on GitHub, which announces it on Discord, and on Gitea. Installed applications update themselves.

The code keeps the version `X.Y.Z` from candidate to production; the packaging writes `edrockmaster/build.json` with the full version, the commit and the channel (ADR 0016).

## License

GPL-3.0-or-later — see [LICENSE](LICENSE).

The engineering catalogue (`edrockmaster/domain/engineering/catalogue.json`) is game data of Frontier Developments, not under this licence — see [NOTICE](NOTICE).
