# Plugin prerequisites

*English · [Français](prerequisites.fr.md)*

Constraints set by EDMarketConnector (EDMC) and by EDCD's official plugin registry. Collected on 2026-10-02 against EDMC 6.1.2.

Sources:

- [EDMC `PLUGINS.md`](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md): plugin API.
- [EDMC `docs/Bundled_Python_Dependencies.md`](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Bundled_Python_Dependencies.md): bundled modules.
- [EDMC `docs/Killswitches.md`](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Killswitches.md): remote kill switches.
- [EDMC-Plugin-Registry](https://github.com/EDCD/EDMC-Plugin-Registry): `docs/STANDARDS.md` and `docs/CONTRIBUTING.md`.

## Runtime environment

| Item | Value | Consequence |
| --- | --- | --- |
| Target EDMC version | 6.1.x (6.1.2 on 2026-10-02) | The registry requires compatibility with the current minor version |
| Python | 3.13, **32-bit** on Windows, bundled in the executable | No `pip` on the player's machine. Mind integer sizes and memory |
| UI | tkinter, provided by EDMC | `myNotebook` widgets for preferences, `theme` to follow the theme |

## Dependencies

- **No bundled dependency** in the plugin. The registry forbids bundling more than needed ("least privilege").
- `requests` (with `certifi`) is guaranteed by EDMC: it is **the** HTTP client to use, never `urllib`, which relies on the system's certificates.
- Standard library modules confirmed in the Windows build: `sqlite3`, `gzip`, `json`, `uuid`, `secrets`, `hashlib`, `webbrowser`, `queue`, `threading`, `concurrent`, `ssl`, `tomllib`. **Missing: `zoneinfo`** (work in UTC).
- The list of bundled modules is **not** a guaranteed API: any import outside the standard library and EDMC's API goes through `try/except` with a degraded behaviour.

## Allowed EDMC API

Only these imports are supported:

- `config`: only `config.set()`, `config.get_str/int/bool/list()`, `config.delete()` for **our own** settings, and the `config.shutting_down` property (no parentheses).
- `theme`, `l10n` (translations), `prefs.prefsVersion`, `monitor.game_running()`, `plug.show_error()`.
- `companion` (`CAPIData`, `SERVER_LIVE`, `SERVER_LEGACY`, `SERVER_BETA`) and `edmc_data` (constants, including `Status.json` flags).
- `killswitch`: kill switches hosted by the plugin (see below).

## Entry points (`load.py`)

| Function | Role for us |
| --- | --- |
| `plugin_start3(plugin_dir)` | Mandatory. Initialises the plugin, returns its internal name |
| `plugin_app(parent)` | Panel in the main window |
| `plugin_prefs(parent, cmdr, is_beta)` / `prefs_changed(cmdr, is_beta)` | Preferences tab, saving |
| `journal_entry(cmdr, is_beta, system, station, entry, state)` | Journal events: the core of data collection |
| `journal_entry_cqc(...)` | Arena (CQC): ignored for mining |
| `dashboard_entry(cmdr, is_beta, entry)` | `Status.json`, about once per second (flags, cargo) |
| `plugin_stop()` | Stop **and join** worker threads |

Special events to handle: `StartUp` (synthetic, when EDMC starts while the game is running: no `LoadGame` nor `Location`, but `state` is up to date), `ShutDown` (synthetic, game crash) and `Shutdown` (normal exit), `Cargo` augmented with the content of `Cargo.json`.

## How EDMC dispatches events

- **Every plugin receives every event.** EDMC loops over all loaded plugins and calls each `journal_entry` with **its own copy** of the event and of the state (verified in `plug.py:notify_journal_entry`). There is no exclusive subscription; a crashing plugin does not affect the others.
- EDMC **drops events older than 60 minutes**: no history replay. Importing past journals, if ever needed, means reading the `Journal.*.log` files directly, read-only, on the player's explicit request.
- EDMC attaches the content of `Cargo.json`, `NavRoute.json` and `ModulesInfo.json`, but not `Market.json`, `Outfitting.json` or `Shipyard.json`: for those, the event is only a signal, and the plugin reads the file from the journal folder.

## Execution rules

- **All hooks run on the tkinter main thread.** Nothing long (more than a second) and no network call in a hook.
- **Network calls and long tasks run in a dedicated thread**, fed by a queue (`queue.Queue`).
- **A worker thread never touches tkinter.** It notifies the main thread with `event_generate()` on a virtual event bound with `bind_all()`, **except during shutdown** (`config.shutting_down`), otherwise EDMC hangs.
- **Errors**: a string returned by a hook, or `plug.show_error()` from a thread. The status area is shared and the message disappears quickly: the server link status has its own widget.
- **Logging** with `logging`, following the template in `PLUGINS.md` (logger named `f"{appname}.{folder_name}"`). Never `print`.
- **Translations**: English source strings wrapped with `functools.partial(l10n.translations.tl, context=__file__)`, French in `L10n/fr.strings` (UTF-8 `.strings` format); displayed strings are refreshed in `prefs_changed`, in case the player changed EDMC's language.

## Naming and packaging

- The plugin folder must be **importable**: no hyphen, no dot. Chosen folder: `EDRockMaster`.
- **Modules are shared between all plugins**: `import mining` loads the first `mining` module found, possibly another plugin's. Our code therefore lives in a uniquely named package (`edrockmaster`), never in a generically named module.
- `VERSION` in strict SemVer (`MAJOR.MINOR.PATCH`) in `load.py`: the plugin browser uses it to compare versions, and so will the upcoming auto-update.
- Distribution: a zip containing the `EDRockMaster/` folder, without `__pycache__`.

## EDCD plugin registry

Conditions to be listed (and stay listed):

- Open-source licence compatible with GPL v2 or later: GPL-3.0-or-later.
- Compatibility kept with EDMC's current minor version.
- Nothing against Frontier's EULA, no scraping of community services (official APIs only), no misleading name.
- Readable, documented code, close to PEP 8: it is **reviewed by hand** before listing.
- Listing through a PR with a single `plugins/EDRockMaster.json` file. Required fields: `pluginName`, `pluginVer`, `autoUpdateEnabled` and `autoInstallEnabled` (`false` for now), `pluginAuthors`, `pluginMainLink`, `pluginLastUpdate`, `pluginDirName`, `pluginCategory` (at least one valid category), `pluginDesc`, `pluginLastTestedEDMC`, `pluginLicense`. Recommended: `pluginZip`, `pluginHash` (SHA-256 of the zip); optional: `pluginRequirements`, `pluginIcon`, `pluginVT` (VirusTotal scan).
- Planned categories: `Utility`, `Colonization`.

## Useful EDMC tools

- **Hosted kill switch**: `killswitch.get_kill_switches(target=URL)`, or its non-blocking variant `killswitch.get_kill_switch_thread` (callback run off the main thread), fetches a kill switch file we publish. It lets us **remotely disable uploads** from a faulty plugin version.
- **HTTP debug server**: started with `--debug-sender edrockmaster`, EDMC redirects our requests to a local server that records them in `$TEMP/EDMarketConnector/http_debug/`. Useful to test uploads without a backend.

## Game data that must not be uploaded

- **Beta** (`is_beta`): Frontier's test servers, unrepresentative data.
- **Legacy galaxy** (`gameversion` 3.x in `LoadGame`): separate galaxy since Update 14 (late 2022).

The plugin works normally in both cases; only uploads are disabled, and the panel says so.

## Still to check

- Terms of use of Frontier (EULA, use of journals and of the CAPI), EDDN and Spansh.
