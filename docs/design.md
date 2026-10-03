# Plugin design

*English · [Français](design.fr.md)*

Design of the EDRockMaster EDMC plugin. Scope of this version: **milestone 1, step 1A** (local plugin, first in-game test). The server link (step 1B) is designed here so that 1A does not have to be reworked, but it is not implemented yet. Constraints come from [prerequisites](prerequisites.md); engineering rules from `edrockmaster-architecture`.

## Goals of step 1A

- Live mining assistance with no server: prospector alerts, cores, session statistics, limpets.
- Bilingual interface (English, French), following EDMC's language.
- A journal recorder (opt-in) that turns real play sessions into test fixtures.
- Structure ready for the server link: ports already defined, adapters added in 1B.

Out of scope for 1A: uploads, sign-in, cargo value estimates (they need server prices), overlay.

## Architecture

Hexagonal, like the services, within EDMC's constraints:

```
load.py                         EDMC entry points only, delegates to edrockmaster.edmc
edrockmaster/
  __init__.py                   VERSION
  domain/                       pure Python: no EDMC, no tkinter, no I/O
    journal.py                  journal entry → domain fact (tolerant reader)
    commodities.py              commodity names, normalisation
    prospecting.py              prospected asteroid, alert policy
    session.py                  MiningSession aggregate (lifecycle, statistics)
  application/
    settings.py                 PluginSettings (alerts, sound, recorder) and their defaults
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder (and, in 1B, UploadQueue, Authenticator)
    mining_service.py           use cases: handle a journal entry, reset the session, change settings
  infrastructure/
    settings_edmc.py            SettingsStore on EDMC's config (keys prefixed "edrockmaster.")
    recorder_jsonl.py           JournalRecorder: JSONL files in the data directory
    sound.py                    Notifier: sound alerts (winsound on Windows, Tk bell elsewhere)
    paths.py                    data directory per platform
    worker.py                   the plugin's single I/O thread and its queue
  edmc/
    plugin.py                   wiring: builds the object graph, implements the hooks
    i18n.py                     tl() bound to EDMC's l10n, with a fallback for tests
  ui/
    panel.py                    main-window panel (tkinter, main thread only)
    preferences.py              preferences tab (myNotebook)
    presenter.py                view models built from domain notifications
L10n/fr.strings                 French translations
```

Dependency rule: `domain` imports nothing from the plugin; `application` imports `domain`; `infrastructure`, `edmc` and `ui` import `application` and `domain`. Only `edmc/`, `ui/` and the EDMC-specific adapters import EDMC modules, always guarded by `try/except ImportError` so that the rest is testable outside EDMC.

## Data flow

1. EDMC calls `journal_entry(...)` on the main thread.
2. `edmc/plugin.py` passes the entry to `MiningService.handle_journal_entry(entry, is_beta)`.
3. `domain/journal.py` turns the raw entry into a typed fact (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`, …) or ignores it. Unknown events and fields are ignored, never fatal.
4. The `MiningTracker` aggregate applies the fact and returns session notifications.
5. The `ProspectingMonitor` evaluates every prospected asteroid against the alert settings.
6. The service forwards the outcome: the alert to the `Notifier` (if sound is enabled), the verbatim entry to the `JournalRecorder` (if recording is enabled), and returns the notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) to the caller, which hands them to the presenter.
7. The panel is refreshed on the main thread.

All of this is pure computation on small objects (well under a millisecond per event): it stays on the main thread. Anything touching files or the network goes through the I/O thread.

## Threads

- **Main thread**: hooks, domain, UI.
- **One I/O thread** (`infrastructure/worker.py`): a daemon thread fed by a `queue.Queue` of jobs (append to the recording file in 1A; uploads and authentication in 1B). It never touches tkinter. When it needs to update the UI, it posts a message on a result queue and calls `event_generate("<<EDRockMasterUpdate>>")` on the panel, unless `config.shutting_down` is set.
- `plugin_stop()` posts a stop job, joins the thread with a timeout, and flushes the recorder.

## Mining session lifecycle

| Situation | Effect |
| --- | --- |
| `SupercruiseExit` with `BodyType` = `PlanetaryRing` | Current ring known (name, system) |
| First mining activity (`LaunchDrone` prospector, `ProspectedAsteroid`, `MiningRefined`) | Session starts if none is running |
| `ProspectedAsteroid` | Asteroid recorded, alert policy evaluated |
| `MiningRefined` | One ton of the commodity counted |
| `LaunchDrone` | Limpet counted by type |
| `AsteroidCracked` | Core cracked |
| `Cargo` (augmented by EDMC) | Cargo snapshot: tons on board, capacity used |
| `EjectCargo` | Ejected tons counted apart (not part of production) |
| No mining activity for 10 minutes | Session paused: inactive time is not counted |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Session ends |
| `StartUp` (EDMC started mid-game) | Context rebuilt from `state` (ship, cargo, system) |
| Manual reset (panel button) | Session ends, a new one can start |
| `is_beta`, or `gameversion` not 4.x in `LoadGame` | Everything works locally; flagged as not uploadable (1B) |

Statistics of a session: active duration, tons per commodity, total tons, tons per hour, asteroids prospected (by content level), cores found and cracked, limpets launched (prospector, collector), refinements per minute.

## Prospector alerts

- Threshold per commodity, in percent of the asteroid, editable. Defaults (2026-10-03, to be tuned after the in-game test): platinum 20 %, low temperature diamonds 20 %, painite 25 %, osmium 25 %, palladium 25 %, gold 25 %. Minimum content Low, no minimum reserve, core alerts on, sound on, journal recorder off.
- Minimum content level (High, Medium, Low).
- Optional minimum remaining reserve (`Remaining`).
- A motherlode (core) raises its own alert, whatever the thresholds.
- Duplicate prospecting of the same asteroid (same composition within 60 seconds) does not raise a second alert.

## Settings

Stored with EDMC's `config` (`config.set` / `config.get_*`), keys prefixed with `edrockmaster.`, read once at start and on `prefs_changed`. Domain code receives an immutable settings object, never the store.

## Files

Data directory, outside the plugin folder so that it survives plugin updates:

- Windows: `%LOCALAPPDATA%\EDRockMaster`
- Linux: `$XDG_DATA_HOME/EDRockMaster`, or `~/.local/share/EDRockMaster`
- macOS: `~/Library/Application Support/EDRockMaster`

Contents in 1A: `recordings/` (journal recordings, JSONL, one file per EDMC run). In 1B: the upload queue (SQLite).

## Journal recorder

- Off by default; enabled in preferences ("Record journal for debugging").
- Writes every entry received by the plugin, unmodified, one JSON object per line, with the `is_beta` flag.
- Recordings are what we turn into `tests/fixtures/`; the player decides what to share.

## Internationalisation

- English source strings in the code, wrapped with `tl()` (`edmc/i18n.py`, bound to `l10n.translations.tl` with `context=__file__`).
- French in `L10n/fr.strings` (UTF-8 `.strings` format).
- Displayed strings are refreshed in `prefs_changed`.
- Commodity names come from the journal's `*_Localised` fields when present (the game's own language), otherwise from our own names.

## Prepared for step 1B

Ports defined in 1A, implemented in 1B:

- `UploadQueue`: SQLite queue in the data directory; every uploadable fact gets a client id (`uuid4`).
- `Authenticator`: Keycloak device flow; refresh token stored with `config`.
- `Uploader`: batches (gzip) to `edrockmaster-ingest`, on the I/O thread, with backoff.
- Kill switch: EDMC's `killswitch` module, fetched every 10 minutes from our server.

## Testing

- **Domain and application: test-driven**, with plain `pytest`, no EDMC needed.
- **Fixtures**: real journal excerpts (`tests/fixtures/*.jsonl`), recorded with the recorder.
- **Replay tests**: a whole recorded session is replayed through `MiningService`, and the final statistics are asserted.
- **EDMC adapters**: tested with fake `config`, `l10n` and `theme` modules injected by `tests/conftest.py`.
- **UI**: kept thin (presenter tested, widgets not unit-tested); checked in game during test 1A.
- CI: `ruff`, `mypy --strict`, `pytest` with coverage on `domain/` and `application/`.
