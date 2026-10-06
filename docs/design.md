# Plugin design

*English · [Français](design.fr.md)*

Design of the EDRockMaster EDMC plugin. Scope: **milestone 1, step 1A** (local plugin, first in-game test), plus the combat activity (design decisions ADR 0011, ADR 0013 and ADR 0015, in the project's architecture repository). The server link (step 1B) is designed here so that 1A does not have to be reworked, but it is not implemented yet. Constraints come from [prerequisites](prerequisites.md); engineering rules from `edrockmaster-architecture`.

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
    journal_reading.py          shared kernel: tolerant reading of journal entries (ADR 0011)
    commodities.py              shared kernel: commodity names, normalisation
    mining/                     mining context
      journal.py                journal entry → mining fact
      prospecting.py            prospected asteroid, alert policy
      session.py                MiningTracker aggregate (lifecycle, statistics, sales)
    combat/                     combat context
      journal.py                journal entry → combat fact
      sites.py                  combat sites, as the game names them on arrival
      session.py                CombatTracker aggregate (sessions by site segments, vouchers, crimes, community goals)
  application/
    activity.py                 the activities: mining, combat
    build.py                    BuildInfo: full version, commit and channel of the running build (ADR 0016)
    companion.py                Companion: records the journal once, hands each entry to every activity, owns the settings
    settings.py                 PluginSettings (alerts, sound, recorder) and their defaults
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder (and, in 1B, UploadQueue, Authenticator)
    mining_service.py           mining use cases: handle a journal entry, reset the session, apply settings
    combat_service.py           combat use cases: handle a journal entry, reset the session
  infrastructure/
    settings_edmc.py            SettingsStore on EDMC's config (keys prefixed "edrockmaster.")
    recorder_jsonl.py           JournalRecorder: JSONL files in the data directory
    build_file.py               reads edrockmaster/build.json, written by the packaging
    sound.py                    Notifier: sound alerts (winsound on Windows, Tk bell elsewhere)
    paths.py                    data directory per platform
    worker.py                   the plugin's single I/O thread and its queue
    clock.py                    Clock: system time, UTC
  edmc/
    plugin.py                   wiring: builds the object graph, implements the hooks
    i18n.py                     tl() bound to EDMC's l10n, with a fallback for tests
    host.py                     EDMC services (theme, plug.show_error, l10n.Locale), with fallbacks
  ui/
    panel_model.py              PanelModel (texts) and shared formatting, no tkinter
    presenter.py                ActivityPresenter: the blocks to show, by display mode
    mining_presenter.py         mining notifications → PanelModel
    combat_presenter.py         combat notifications → PanelModel
    preferences_form.py         settings <-> preferences fields, validation, no tkinter
    commodity_names.py          names of the mineable commodities known before the journal names them
    panel.py                    main-window panel (tkinter, main thread only), one block per activity shown
    preferences.py              preferences tab (myNotebook)
L10n/fr.strings                 French translations
```

Dependency rule: `domain` imports nothing from the plugin; `application` imports `domain`; `infrastructure`, `edmc` and `ui` import `application` and `domain`. Only `load.py` (which only runs inside EDMC), `edmc/`, `ui/` and the EDMC-specific adapters import EDMC modules; except in `load.py`, always guarded by `try/except ImportError` so that the rest is testable outside EDMC.

## Data flow

1. EDMC calls `journal_entry(...)` on the main thread.
2. `edmc/plugin.py` passes the entry to `Companion.handle_journal_entry(entry, is_beta)`, which copies it to the `JournalRecorder` (if recording is enabled), then hands it to each activity: `MiningService`, then `HuntingService`. Each activity translates the journal on its own; below, the mining path.
3. `domain/mining/journal.py` turns the raw entry into a typed fact (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`, …) or ignores it. Unknown events and fields are ignored, never fatal.
4. The `MiningTracker` aggregate applies the fact and returns session notifications.
5. The `ProspectingMonitor` evaluates every prospected asteroid against the alert settings.
6. The service forwards the outcome: the alert to the `Notifier` (if sound is enabled), and returns the notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) to the caller, which hands them to the `ActivityPresenter`: it shows the last activity whose session progressed.
7. The panel is refreshed on the main thread.

All of this is pure computation on small objects (well under a millisecond per event): it stays on the main thread. Anything touching files or the network goes through the I/O thread.

`edmc/plugin.py` is the composition root. `load.py` hands it EDMC's `config`; it builds the I/O thread, the adapters and the `Companion` in `plugin_start3`, and stops the thread in `plugin_stop`. The UI subscribes to the notifications and provides the alert sound, which needs a widget. The reset button ends the session of the activity shown. Any exception while handling an entry is logged and reported in EDMC's status bar; the next entries are handled normally. The logger is the one EDMC prepares for the plugin, `<appname>.<plugin folder>`.

## Threads

- **Main thread**: hooks, domain, UI.
- **One I/O thread** (`infrastructure/worker.py`): a daemon thread fed by a `queue.Queue` of jobs (append to the recording file in 1A; uploads and authentication in 1B). It never touches tkinter. In 1A it has nothing to tell the UI. From 1B (upload status), it will post a message on a result queue and call `event_generate("<<EDRockMasterUpdate>>")` on the panel, unless `config.shutting_down` is set.
- `plugin_stop()` posts a stop job, joins the thread with a timeout, and flushes the recorder.

## Mining session lifecycle

| Situation | Effect |
| --- | --- |
| `SupercruiseExit`, `Location` or `StartUp` with `BodyType` = `PlanetaryRing` | Current ring known (name, system) |
| First mining activity (`LaunchDrone` prospector, `ProspectedAsteroid`, `MiningRefined`) | Session starts if none is running |
| `ProspectedAsteroid` | Asteroid recorded, alert policy evaluated |
| `MiningRefined` | One ton of the commodity counted |
| `LaunchDrone` | Limpet counted by type |
| `AsteroidCracked` | Core cracked |
| `Cargo` (augmented by EDMC) | Cargo snapshot: tons on board, capacity used |
| `EjectCargo` | Ejected tons counted apart (not part of production) |
| No mining activity for 10 minutes | Session paused: inactive time is not counted |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Session ends |
| `StartUp` (synthetic, EDMC started mid-game) | Current ring from the event's `Body`/`BodyType`; cargo figures come with the next `Cargo` event (the game writes one at each refinement) |
| `MarketSell` | Credited to the running session, or else to the last one that ended: only its mined tons not yet ejected nor sold, at the sale's unit price |
| Manual reset (panel button) | Session ends, a new one can start |
| `is_beta`, or `gameversion` not 4.x in `LoadGame` | Everything works locally; flagged as not uploadable (1B) |

Statistics of a session: active duration, tons per commodity, total tons, tons per hour, asteroids prospected (by content level), cores found and cracked, limpets launched (prospector, collector), refinements per minute, tons sold and credits earned.

## Combat

Combat covers bounty hunting, conflict zones and any kill ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.md), [ADR 0015](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0015-unnamed-and-ground-conflict-zones.md)). It is measured in **segments**: one stay on a combat site, from the arrival (by ship or on foot) to the departure.

| Situation | Effect |
| --- | --- |
| `Bounty` (ship format with `Rewards`, or flat format for skimmers and on foot) | One kill; bounty credits; a bounty voucher per paying faction |
| `FactionKillBond` | One kill; combat bond credits and voucher |
| `CapShipBond` | Combat bond credits and voucher, no kill |
| First reward | Combat session starts |
| `SupercruiseDestinationDrop` then `SupercruiseExit` | Arrival at a destination. A combat site if its type is known: conflict zone (low, medium, high), resource extraction site (low, normal, high, hazardous), navigation beacon |
| `SupercruiseExit` without a destination (ring, planet, deep space), `Undocked` | Arrival somewhere the journal does not name as a combat site |
| `ApproachSettlement` | The settlement is remembered until the next departure |
| `DropshipDeploy` (Frontline Solutions) | Arrival on foot in a **ground conflict zone**, carrying the settlement's name; a redeploy after a defeat continues the stay |
| `Disembark` on a planet's surface | Arrival on foot, not named as a combat site |
| First reward on a combat site | A segment opens, **from the arrival**: the search for targets counts |
| `SupercruiseEntry`, `Docked`, `FSDJump`, `StartJump` to hyperspace, `BookDropship` retreat, `Embark` | Departure: the segment closes; the session goes on. A site left without any reward is not counted. `Embark` off a station is a new arrival, by ship |
| `FactionKillBond` outside any segment | A combat bond only exists in a conflict zone: a segment opens from the last arrival (from the bond when none was seen). By ship: **conflict zone, unknown intensity**; on foot: **ground conflict zone** |
| Bounty elsewhere (a pirate while mining, near a station, after an interdiction): a bounty does not tell the place | **Miscellaneous**: counted in kills, credits and vouchers, in no rate |
| Reward with no arrival seen (EDMC or the game started on the site: `StartUp`, `Location` off station) | A segment of type **unknown**, from that reward; miscellaneous if the commander mines there (`ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`, prospector or collector limpets) |
| `CommitCrime` during a session | Counted by kind of crime: fines and bounties on the commander, never deducted from the credits |
| `Died` | Session ends; unredeemed vouchers are lost |
| `Shutdown`, `ShutDown` | Session ends |
| `RedeemVoucher` (bounties, combat bonds) | The vouchers paid are removed, per faction, never below zero |
| `CommunityGoal` | The goals the commander joined: contribution, percentile band, tier reached |
| Manual reset (panel button, combat shown) | Session ends, a new one can start; still on the site, the next segment starts at the reset |

Statistics of a combat session: its segments (site type, duration, kills, credits, rates), an average **per site type, weighted by time** (total kills and credits over total duration), time on combat sites, kills (and shared kills), bounty and combat bond credits, miscellaneous kills, crimes. Shared with the panel: unredeemed vouchers (known since EDMC started only: the journal does not restate older ones) and the community goals. Superpower factions written `$faction_Federation;` are normalised to `Federation`. Another activity never ends a combat session: a miner may fight back and keep mining.

The panel shows the activities the player chose (preferences, **Display**), in one of two modes ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.md)):

- **last active activity** (the default): one block, the last shown activity to **progress**. For combat, a session or a segment that starts or ends, a reward or a crime; leaving a site without a segment, vouchers and community goals never switch it. A hidden activity never takes the panel;
- **all of them, stacked**: one block per activity shown, mining then combat, each with its own **Reset** button.

A hidden activity is still followed: shown again, it is up to date.

## Prospector alerts

- Threshold per commodity, in percent of the asteroid, editable. Defaults (2026-10-03, to be tuned after the in-game test): platinum 20 %, low temperature diamonds 20 %, painite 25 %, osmium 25 %, palladium 25 %, gold 25 %. Minimum content Low, no minimum reserve, core alerts on, sound on, journal recorder off.
- Minimum content level (High, Medium, Low).
- Optional minimum remaining reserve (`Remaining`).
- A motherlode (core) raises its own alert, whatever the thresholds.
- Duplicate prospecting of the same asteroid (same composition within 60 seconds) does not raise a second alert.

## User interface

**Panel** (EDMC's main window): status (no session, mining in a ring, session ended and why), the last prospector alert, highlighted, until the next asteroid is prospected, then the statistics: active time, refined tons, rate, tons per commodity, asteroids prospected and, once known, cores, limpets, cargo and sales. The statistics of an ended session stay displayed, and its sales are added to them. A **Reset** button ends the running session. Numbers follow the system's locale, like EDMC's own.

**Preferences tab**: a percentage field per mineable commodity (empty means no alert), minimum content, minimum remaining reserve, alert on cores, sound, journal recorder, the activities shown and the display mode, and a button opening the recordings folder; it ends with the full build version. At least one activity stays shown. Numbers are typed in the system's locale. When the dialog closes, an invalid entry keeps its previous value and is named in EDMC's status bar; the valid ones are applied at once.

## Settings

Stored with EDMC's `config` (`config.set` / `config.get_*`), keys prefixed with `edrockmaster.`, read once at start and on `prefs_changed`. Domain code receives an immutable settings object, never the store.

| Key | Type | Content |
| --- | --- | --- |
| `edrockmaster.settings_version` | text | Format version of the keys below (`1`), for future migrations |
| `edrockmaster.alert.thresholds` | text | JSON object, commodity key → percent (`{"painite": 25.0, …}`) |
| `edrockmaster.alert.minimum_content` | text | `low`, `medium` or `high` |
| `edrockmaster.alert.minimum_remaining` | text | Percent, or empty for none (text, for every EDMC config back-end) |
| `edrockmaster.alert.cores` | bool | Alert on cores |
| `edrockmaster.sound` | bool | Audible alerts |
| `edrockmaster.record_journal` | bool | Journal recorder |
| `edrockmaster.display.activities` | text | JSON list of the activities shown, at least one (`["mining", "combat"]`) |
| `edrockmaster.display.mode` | text | `last_active` or `stacked` |

Values are read one by one: a missing or invalid value falls back to its own default (and is logged), the others are kept.

## Files

Data directory, outside the plugin folder so that it survives plugin updates:

- Windows: `%LOCALAPPDATA%\EDRockMaster`
- Linux: `$XDG_DATA_HOME/EDRockMaster`, or `~/.local/share/EDRockMaster`
- macOS: `~/Library/Application Support/EDRockMaster`

Contents in 1A: `recordings/` (journal recordings, JSONL, one file per EDMC run). In 1B: the upload queue (SQLite).

## Journal recorder

- Off by default; enabled in preferences ("Record journal for debugging").
- Writes every entry received by the plugin, unmodified, one JSON object per line, with the `is_beta` flag: `{"is_beta": false, "entry": {…}}`. File: `recordings/journal-<start, UTC, YYYYMMDDTHHMMSSZ>-<build version>.jsonl`, so a recording says which build counted it.
- The entry is serialised when received (EDMC shares the same dict with every plugin) and written by the I/O thread.
- Recordings are what we turn into `tests/fixtures/`; the player decides what to share.
- The repository is public, and a raw recording holds personal data (commander name and Frontier id, squadron, carrier, chat messages, other players' names, reputation). A recording becomes a fixture only through `scripts/sanitise_recording.py`: it keeps the events the plugin reads and a few harmless ones, reduces `LoadGame` to the game version, drops the reputation (`Factions` of `Location`, `FSDJump`, `StartUp`), the targets' pilot names (`Bounty.PilotName`) and crime victims (`CommitCrime.Victim`), per event, replaces every fleet carrier (name, callsign, id) with a neutral value, and refuses to write if the commander's name or id, or a carrier, remains. `tests/test_replay.py` replays each fixture, with figures checked by hand against the raw journal.

## Internationalisation

- English source strings in the code, wrapped with `tl()` (`edmc/i18n.py`, bound to `l10n.translations.tl` with `context=__file__`).
- French in `L10n/fr.strings` (UTF-8 `.strings` format).
- Displayed strings are refreshed in `prefs_changed`: the presenter keeps domain objects, not texts, and rebuilds every text in the current language.
- Counts avoid plural agreement (`prospectors: 3`), which `.strings` files cannot express.
- `tests/test_translations.py` fails if a text passed to `tl()` has no French translation, if a translation is no longer used, or if placeholders differ.
- Commodity names come from the journal's `*_Localised` fields when present (the game's own language), otherwise from our own names.

## Prepared for step 1B

Ports defined in 1A, implemented in 1B:

- `UploadQueue`: SQLite queue in the data directory; every uploadable fact gets a client id (`uuid4`).
- `Authenticator`: Keycloak device flow; refresh token stored with `config`.
- `Uploader`: batches (gzip) to `edrockmaster-ingest`, on the I/O thread, with backoff.
- Kill switch: EDMC's `killswitch` module, fetched every 10 minutes from our server.
- Galaxy on `StartUp`: there is no `LoadGame` then, so the game version must be read from `state["GameVersion"]` to tell Live from Legacy.

## Testing

- **Domain and application: test-driven**, with plain `pytest`, no EDMC needed.
- **Fixtures**: real journal excerpts (`tests/fixtures/*.jsonl`), recorded with the recorder.
- **Replay tests**: a whole recorded session is replayed through `MiningService`, and the final statistics are asserted.
- **EDMC adapters**: tested with fake `config`, `l10n` and `theme` modules injected by `tests/conftest.py`.
- **UI**: the presenter and the preferences form are pure and fully tested. The tkinter widgets are kept thin; their tests use a real Tk and are skipped where no display exists (CI), so they run on developers' machines. Checked in game during test 1A.
- CI: `ruff`, `mypy --strict`, `pytest` with coverage on `domain/` and `application/`.
