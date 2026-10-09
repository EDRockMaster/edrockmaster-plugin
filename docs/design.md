# Plugin design

*English · [Français](design.fr.md)*

Design of the EDRockMaster EDMC plugin. Scope: **milestone 1, step 1A** (local plugin, first in-game test), plus the combat and trade activities (design decisions ADR 0011, ADR 0013, ADR 0014 and ADR 0015, in the project's architecture repository). The server link (step 1B) is designed here so that 1A does not have to be reworked, but it is not implemented yet. Constraints come from [prerequisites](prerequisites.md); engineering rules from `edrockmaster-architecture`.

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
    commodities.py              shared kernel: commodity names, normalisation, commodities a refinery produces
    mining/                     mining context
      journal.py                journal entry → mining fact
      prospecting.py            prospected asteroid, alert policy
      session.py                MiningTracker aggregate (lifecycle, statistics, sales)
    combat/                     combat context
      journal.py                journal entry → combat fact
      sites.py                  combat sites, as the game names them on arrival
      session.py                CombatTracker aggregate (sessions by site segments, vouchers, crimes, community goals)
    trade/                      trade context
      journal.py                journal entry → trade fact
      session.py                TradeTracker aggregate (sessions, routes, flight time, cargo bought, losses)
    situation/                  the commander's situation (ADR 0023): who, ship, where, game mode, wing
    engineering/                engineering context (ADR 0017)
      journal.py                journal entry → engineering fact
      session.py                EngineeringTracker aggregate (inventory, caps, collection, goals, engineers)
      catalogue.py              game data: materials (grade, cap), blueprints, effects, module types, engineers
      catalogue.json            that data, written by scripts/import_engineering_data.py (Frontier's, see NOTICE)
      goals.py                  blueprint and experimental effect goals
  application/
    activity.py                 the activities: mining, combat, trade
    build.py                    BuildInfo: full version, commit and channel of the running build (ADR 0016)
    companion.py                Companion: records the journal once, hands each entry to every activity, owns the settings
    settings.py                 PluginSettings (alerts, sound, recorder) and their defaults
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder, GoalRepository (and, in 1B, UploadQueue, Authenticator)
    mining_service.py           mining use cases: handle a journal entry, reset the session, apply settings
    combat_service.py           combat use cases: handle a journal entry, reset the session
    trade_service.py            trade use cases: handle a journal entry, reset the session
    engineering_service.py      engineering use cases: journal, goals and their storage, reset
  infrastructure/
    settings_edmc.py            SettingsStore on EDMC's config (keys prefixed "edrockmaster.")
    recorder_jsonl.py           JournalRecorder: JSONL files in the data directory
    database.py                 the local SQLite database: opening, migrations, copy, moving aside (ADR 0018)
    migrations.py               the database schema, one migration per version
    goal_repository.py          GoalRepository on the local database
    catalogue_file.py           reads the engineering catalogue shipped with the plugin
    build_file.py               reads edrockmaster/build.json, written by the packaging
    sound.py                    Notifier: sound alerts (winsound on Windows, Tk bell elsewhere)
    paths.py                    data directory per platform
    worker.py                   the plugin's single I/O thread and its queue
    clock.py                    Clock: system time, UTC
  desktop/                      the desktop application (ADR 0020), being built: it reads the journal without EDMC
    journal_folder.py           where the game writes its journal; journal files in order
    journal_reader.py           JournalFollower (follows the journal as the game writes it), JournalWatcher (its thread)
    core.py                     DesktopCore: the composition root, the core thread, the live view pushed
    live_view.py                the live view, as schemas/live_view.schema.json describes it
    window.py                   the pywebview window, InterfaceApi, the entry point (python -m edrockmaster.desktop)
  edmc/
    plugin.py                   wiring: builds the object graph, implements the hooks
    i18n.py                     tl() bound to EDMC's l10n, with a fallback for tests
    host.py                     EDMC services (theme, plug.show_error, l10n.Locale), with fallbacks
    main_thread.py              results of the I/O thread run on the main thread
    state.py                    inventory and engineers from EDMC's state, when the plugin starts after the game
  ui/
    panel_model.py              PanelModel (texts), local data notices and shared formatting, no tkinter
    presenter.py                ActivityPresenter: the blocks to show, by display mode
    mining_presenter.py         mining notifications → PanelModel
    combat_presenter.py         combat notifications → PanelModel
    trade_presenter.py          trade notifications → PanelModel
    engineering_presenter.py    engineering notifications → PanelModel
    engineering_names.py        names of materials, blueprints, effects, module types and goals
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
- **One I/O thread** (`infrastructure/worker.py`): a daemon thread fed by a `queue.Queue` of jobs (append to the recording file, the local database; in 1B, uploads and authentication). It never touches tkinter.
- **Results back to the main thread** (`edmc/main_thread.py`): the I/O thread puts a callback in a queue, and the main thread runs it, polling the queue every 100 ms with `after()` on the panel. Waking the main thread with `event_generate()` from the I/O thread, as EDMC does for its own threads, needs Tk's main loop to run, and EDMC calls `plugin_app` before starting it: polling makes no Tk call from the I/O thread at all. Callbacks queued before the panel exists wait for it.
- `plugin_stop()` closes the local database, posts a stop job, joins the thread with a timeout, and flushes the recorder.

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

- **last active activity** (the default): one block, the last shown activity to **progress**. For combat, a session or a segment that starts or ends, a reward or a crime; leaving a site without a segment, vouchers and community goals never switch it. For trade, a session that starts or ends, a purchase, a sale or a loss. A hidden activity never takes the panel;
- **all of them, stacked**: one block per activity shown, mining, combat then trade, each with its own **Reset** button.

A hidden activity is still followed: shown again, it is up to date.

## Trade

Trade follows purchases and sales of goods on markets ([ADR 0014](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0014-plugin-trade-activity.md)). Its active time is the **flight time**: a **leg** runs from undocking to the next docking, and counts once a trade follows it in the session.

| Situation | Effect |
| --- | --- |
| First `MarketBuy`, or first `MarketSell` of bought goods (`AvgPricePaid` above 0) | Trade session starts. The flight to that market does not count |
| `MarketBuy` | The goods are on board at their cost; the market is the origin of their route (the last purchase wins) |
| `MarketSell` of bought goods | Profit `(SellPrice - AvgPricePaid) × Count`, the game's own, even for goods bought before EDMC started (origin unknown). Counted on the route: commodity, market of purchase, market of sale |
| `MarketSell` with `AvgPricePaid` 0 | Not bought: **refined commodities** if a refinery produces them (their profit belongs to mining), **other goods** otherwise. In no profit and no rate; no session started |
| `Undocked`, then `Docked` | A leg. It counts once a purchase or a sale of bought goods follows it in the session: a stop without trade is part of the flight, a flight after the last trade does not count. Time docked never counts |
| `Location` or `StartUp` off station | In flight since an unknown time: the leg counts from there |
| `EjectCargo` of bought goods | Loss at the price paid, deducted from the profit |
| `CargoTransfer` to a fleet carrier, or to the ship while docked at one ([ADR 0019](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0019-fleet-carrier-transfers.md)) | A **deposit** or a **withdrawal**: counted per commodity and direction, with the number of transfers. Starts the session and counts the legs it follows, like a purchase; earns nothing. The goods keep their cost and origin at the carrier, and come back with them. Transfers with an SRV are ignored |
| `Cargo` | Bought goods that left without a sale (a mission) are no longer on board: never more than the ship carries |
| `Died` | The bought cargo is lost (a loss), the session ends |
| `Shutdown`, `ShutDown` | Session ends; the cargo stays known |
| Manual reset (panel button, trade shown) | Session ends, a new one can start |

Statistics of a trade session: flight time, profit (sales minus losses), profit and tons per hour of flight, tons sold, losses, the cost of the bought goods on board, one line per route (tons, profit, profit per ton, sales), the transfers with fleet carriers, refined commodities and other goods. On the panel, a route too long for EDMC's window names its destination only. Out of scope: the fleet carrier's market and stock, smuggling, missions. Trade is not uploaded.

## Engineering

Being built (design decision ADR 0017): materials, engineers and blueprint goals, ship engineering first.

**Game data.** The journal names materials (`chemicalmanipulators`), blueprints (`FSD_LongRange`) and experimental effects (`special_fsd_heavy`), but gives neither a material's grade nor the ingredients of a blueprint, nor which engineer offers it on which module. `scripts/import_engineering_data.py` reads them from EDCD/FDevIDs and EDCD/coriolis-data at pinned commits and writes `domain/engineering/catalogue.json`, one entry per line for readable diffs; `Catalogue.from_data` checks it when read. The script refuses a name it cannot map; the few fixes it makes are listed in it, each with its reason (a trailing space in FDevIDs, misspellings in coriolis-data). It keeps the module types that have blueprints, the engineers who offer them, and the effects an engineer still applies (legacy effects have no ingredients). To follow a game update: change the pinned commits, run the script, review the diff of the catalogue.

The data is Frontier's, not under the plugin's licence: `NOTICE`, shipped in the zip, says so. Names are in English in the catalogue and translated by `L10n/fr.strings`; `tests/test_translations.py` checks that every name has its translation. Material names in French are the game's own, taken from a recorded journal, where known.

**The context.** `domain/engineering/journal.py` reads the ship materials events: `Materials` (the whole inventory, at load), `MaterialCollected`, `MaterialDiscarded`, `MaterialTrade`, `Synthesis`, `TechnologyBroker`, `EngineerContribution` (materials only), `ScientificResearch`, `MissionCompleted` (`MaterialsReward`), `EngineerCraft`, `EngineerProgress` (all engineers at load, then one at a time) and `Shutdown`. `EngineeringTracker` (`session.py`) is the aggregate:

- **Inventory**: unknown until `Materials` or EDMC's state gives it (`edmc/state.py`: when the plugin starts after the game, EDMC hands it no past event; its `state` is read after each entry while the inventory is unknown, and already includes that entry). Each change applies to it, never below 0, never above the material's **cap** (300 at grade 1 down to 100 at grade 5): reaching it is an alert, as what is collected beyond it is lost. A material the catalogue does not know (the game adds some before the community data) is counted, without cap. Never stored.
- **Collection**: from the first change of materials to `Shutdown` or reset; death does not end it. It counts the materials collected or rewarded per category, those used (rolls, effects, synthesis, brokers, contributions, research; a trade only converts), and those that reached their cap.
- **Goals**: a blueprint at a grade for a module type, with a number of rolls, or an experimental effect, with a number of applications. What a goal misses is its ingredients, times its rolls, minus the inventory; it is **ready** when it misses nothing. The **shopping list** adds up every goal. The engineers of a goal are the unlocked ones offering its grade on its module type. An `EngineerCraft` takes one roll (or application, with `ApplyExperimentalEffect`) off the first goal with the same blueprint and grade on the same module type, which `Catalogue.module_of` finds from the item (`int_powerdistributor_size7_class5`; armour by its name); a goal with nothing left is done and removed. The tracker reports these changes, and `EngineeringService` stores them through `GoalRepository` (local database, ADR 0018); the stored goals are loaded at start.
- **Engineers**: status and rank, from `EngineerProgress` or EDMC's state (which names them: the catalogue gives their ids).

**Panel.** The engineering block shows the materials gained per category, used, at their cap, and the goals ready out of all goals (or that the inventory is unknown). Its alert is the last material at its cap, goal ready or goal done. It progresses on a change of materials in game, a cap or a goal ready; the game's statement at load is no progress. Material names are the game's own when the journal gave them, else the catalogue's, translated. The separate window (inventory, engineers, goals) comes next.

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
| `edrockmaster.display.offered` | text | JSON list of the activities the tab offered when saved (`["mining", "combat", "trade"]`). An activity a later version adds is shown until the player hides it; absent (saved by 0.3.0): mining and combat |
| `edrockmaster.display.mode` | text | `last_active` or `stacked` |

Values are read one by one: a missing or invalid value falls back to its own default (and is logged), the others are kept.

## Files

Data directory, outside the plugin folder so that it survives plugin updates:

- Windows: `%LOCALAPPDATA%\EDRockMaster`
- Linux: `$XDG_DATA_HOME/EDRockMaster`, or `~/.local/share/EDRockMaster`
- macOS: `~/Library/Application Support/EDRockMaster`

Contents:

- `recordings/`: journal recordings, JSONL, one file per EDMC run;
- `edrockmaster.sqlite3`: the local database (below), with its `-wal` and `-shm` files while EDMC runs;
- `edrockmaster.sqlite3.v<N>.bak`: a copy of the database made before its last migration, from schema version N;
- `edrockmaster.sqlite3.unreadable-<date>`: a database the plugin could not read, moved aside.

## Local database

One SQLite file for the plugin's durable **state**, which is neither a setting (EDMC's `config`) nor a recording (design decision ADR 0018). Each need has its own tables and its own repository port: the engineering goals first (`GoalRepository`, ADR 0017), the upload queue in 1B (ADR 0005). Nothing in it is sent to the server unless an ADR says so.

- **The I/O thread only.** The database opens in a job of the I/O thread at `plugin_start3`, and closes in one at `plugin_stop`. `LocalDatabase.connection()` refuses any other thread. Repositories turn each call into a job; what they read reaches the main thread through `edmc/main_thread.py`.
- **Versioned schema.** `PRAGMA user_version` is the schema version; `infrastructure/migrations.py` lists the migrations, applied in order at opening, each in its own transaction, forward only. A released migration never changes. Before migrating a database of version N > 0, the file is copied (SQLite's backup API) to `edrockmaster.sqlite3.v<N>.bak`, and older copies are removed. WAL journal mode.
- **Unreadable file.** A corrupt file (SQLite says it is not a database, or the integrity check fails) or a file written by a newer version of the plugin (a downgrade) is moved aside as `edrockmaster.sqlite3.unreadable-<UTC date>`, and a new database is created. The log says why, and the panel shows a notice until the player dismisses it.
- **Unavailable database.** Any other failure (another EDMC holds the file, the disk refuses it, a migration fails and is rolled back) leaves the file as it is; nothing is stored until EDMC restarts, the log says why and the panel says so. The plugin never fails because of its database.
- **Tests.** Every schema version has a fixture, `tests/fixtures/database/schema-v<N>.sql`, kept as released; the tests migrate each one to the latest version, and check that the latest fixture has the schema the migrations create. A new migration therefore comes with its fixture.

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

- `UploadQueue`: its own tables in the local database (ADR 0018); every uploadable fact gets a client id (`uuid4`).
- `Authenticator`: Keycloak device flow; refresh token stored with `config`.
- `Uploader`: batches (gzip) to `edrockmaster-ingest`, on the I/O thread, with backoff.
- Kill switch: EDMC's `killswitch` module, fetched every 10 minutes from our server.
- Galaxy on `StartUp`: there is no `LoadGame` then, so the game version must be read from `state["GameVersion"]` to tell Live from Legacy.

## Desktop application

Being built (design decision ADR 0020): the plugin's core in an application of its own, which reads the journal without EDMC and shows a web interface in a native window. Step 1, the **journal reader**, is in `desktop/`:

- **Folder**: on Windows, the "Saved Games" known folder of the player's profile (wherever it was moved), else `%USERPROFILE%\Saved Games`, then `Frontier Developments\Elite Dangerous`; on Linux, the Proton prefix of the game (Steam app 359320) under the usual Steam folders. `EDROCKMASTER_JOURNAL_DIR` sets it by hand.
- **Files**: `Journal.<start>.<part>.log` (and `JournalBeta.…`), ordered by the start time in their name (two formats, before and since 2022), then by part.
- **Reading**: the first poll reads the current file **from its beginning**, and hands the core every entry: unlike EDMC, which keeps past entries for its own state and hands plugins only the new ones, the application reaches the same figures as if it had run since the game started (its state then needs no `state` from a host). Then each poll reads what was added; an incomplete line waits for the rest; a newer file (a new session, or the next part of a long one) is followed once the current one is finished. A line that is not an entry is logged and skipped. A beta says so in its file name or its game version (`Fileheader`, `LoadGame`), as EDMC reads it.
- **Thread**: `JournalWatcher` polls every second on its own thread (`EDRockMaster journal`), as often as EDMC polls a running game.
- **Parity**: `tests/desktop/test_parity.py` writes every fixture back as journal files, reads them with the reader, and checks that the core gives exactly the notifications of the replay through EDMC, also for a session split in parts written while the reader follows. Reading 20,000 entries at start takes about 0.1 s, 0.3 s with the core.
- **Boundaries**: `lint-imports` (in the CI) checks that `domain/` and `application/` import no adapter, no host and no interface toolkit (`infrastructure`, `edmc`, `desktop`, `ui`, `tkinter`, `webview`, `sqlite3`), and that the domain imports nothing else of the plugin.

**Step 2, the application shell** (ADR 0020, ADR 0021):

- `desktop/core.py`, `DesktopCore`: the composition root of the desktop application, as `edmc/plugin.py` is the plugin's. The same core (companion, local database, goals, catalogue), fed by the journal reader. Every call to the companion and the presenter happens on the **core thread** (`EDRockMaster core`, an `IoWorker` of its own); the journal reader's thread and the interface's calls only queue jobs. After each change, the core pushes the **live view** to the interface.
- `desktop/live_view.py`, `desktop/schemas/live_view.schema.json`: the live view, described by a JSON Schema: the activities shown and their blocks (texts from the plugin's presenters, already in the player's language), the current activity, the local data notice, the journal read. The tests validate every view pushed against the schema; the interface's TypeScript types are generated from it (`pnpm types`), and the CI checks that they are up to date.
- `desktop/window.py`: pywebview shows the interface, one self-contained HTML file (`desktop/interface/index.html`, built from `web/`, not in git), given as a page: no server, no port. The interface calls the core through `InterfaceApi` (`window.pywebview.api`: `ready`, `reset`, `dismiss_notice`); the core pushes with `run_js`, in ASCII JSON (pywebview on GTK gives WebKit the length of a script in characters, not bytes). pywebview creates `window.pywebview` before adding the core's calls to it: the interface waits for `pywebviewready`.
- Settings in `settings.json` of the data directory, read and checked as the plugin's (same keys); a rotating log in `logs/`; the language of the system's interface (Windows) or of the locale variables, English otherwise; the presenters' texts translated from `L10n/*.strings`, numbers written as the language writes them.
- `lint-imports` also checks that `desktop/` and `infrastructure/` import neither EDMC nor Tk.
- **Interface** (`web/`): Svelte 5 and TypeScript, built by Vite into one HTML file; its own texts in `src/locales/*.json`, with a test that every key is translated and used; Vitest and Testing Library; a dark theme from design tokens. Node 22 and pnpm (through corepack) are build tools only.
- **Run it** (development): `cd web && corepack pnpm install && corepack pnpm build`, then `uv run python -m edrockmaster.desktop` (`--debug` opens the web inspector). On Linux, pywebview needs GTK and WebKit2GTK with their Python binding (PyGObject), usually from the system's Python; `EDROCKMASTER_JOURNAL_DIR` points to a journal folder, a recording written back as journal files for instance. `uv run python -m edrockmaster.desktop --demo` (or `EDRockMaster.exe --demo`, `--demo=en`, `--demo=fr`) shows the **demo**: see below.

**Settings** (the *Settings* tab): the plugin's settings, with the same keys in `settings.json` (alert thresholds per commodity, minimum content and remaining reserve, cores, sound, journal recordings, activities shown), and two of the desktop application's own: its **language** (the system's by default; the presenters translate through the core, so a new language applies at once) and its **journal folder** (empty: where the game writes it), used from the next start, since reading another folder at once would count its sessions on top of the current ones. The folder named by `EDROCKMASTER_JOURNAL_DIR` comes first, then the settings', then the usual one. `settings()` gives the form its content (`settings.schema.json`), `save_settings()` checks it field by field (`desktop/settings_view.py`) and logs what it refuses.

**The engineering view** (ADR 0017): the desktop application's *Engineering* tab, in place of the Tk window ADR 0017 planned. The live view's `engineering` part (`desktop/engineering_view.py`) carries the materials by category and grade with their count and cap, the ship engineers (status, rank; named in the player's language, through `L10n/`, since some carry a title such as *Professor Palin*), the goals with what each misses and the unlocked engineers offering it (ready goals first), and the shopping list. The goal form asks the core once for the catalogue (`catalogue()`, schema `goal_catalogue.schema.json`): module types, their blueprints with their grades, their experimental effects. The interface adds, changes (rolls, applications) and removes goals (`add_goal`, `change_goal`, `remove_goal`); the core checks a new goal against the catalogue and the domain, logs what it refuses, and stores goals in the local database (ADR 0018).

**The blueprints tab** (ADR 0017): the game data to browse, without going through a goal. A search (module, blueprint or effect name, or a material they take: what a material is for; case and accents ignored) and a module type filter; each blueprint shows one grade at a time (the highest first): its ingredients against the inventory, held or missing, how many rolls the inventory allows, and the engineers offering that grade, unlocked first with their rank; each module's experimental effects show their ingredients and how many applications are possible. A button adds the grade or the effect to the goals (`add_goal`, one roll). The catalogue call (`catalogue()`) carries, for each blueprint, one recipe per grade (ingredients, engineers' ids) and, for each effect, its ingredients, named in the core's language: the tab asks for it again when the language changes. The search and the arithmetic are in `web/src/lib/blueprints.ts`.

**The commander's situation** (ADR 0023): `domain/situation/` reads `Commander`, `LoadGame`, `Location`, the jumps and supercruise, `Docked`, `Undocked`, `Loadout`, `ShipyardSwap`, `SetUserShipName`, `Embark`, `Disembark` and the wing events, into the commander's name, the ship (its type in the game's language, the player's name and registration), on foot or not, the system, the station, the game mode with the private group's name, and the wing members. `Shutdown` keeps the last situation and says the game is closed. It is in memory only: never stored, never uploaded; the plugin ignores it (EDMC shows it), the desktop application shows it in a banner, through the live view's `situation`. Wing members are other players: the recording sanitiser names them `Wingmate 1`, `Wingmate 2`…

**The demo** (`--demo`, `desktop/demo.py`): the application reads a sample journal instead of the player's, for the Store's screenshots and the documentation, or to discover it without playing. `scripts/make_demo_journal.py` writes it (`desktop/demo_journal.jsonl`, checked by a test to be up to date) from published fixtures: a mining session in a resource extraction site with its combat bonds, under the fictional **Commander Jameson** in Open play, in the *Rock Hound*, with the materials, engineers and collected materials of the engineering fixture; it stops while the commander is still mining. At start, its timestamps are moved so that it ends now: the mining, combat and engineering sessions are running. The demo is in the system's language, or the one it names (`--demo=en`, `--demo=fr`); the journal was recorded with the game in French, so for a demo in English the names the game writes in its language and the application shows as they are (commodities, asteroid content, community goal) are replaced by the game's names in English, the game's names of the materials are left out so that the catalogue names them, and each screenshot is in one language only. Its settings and goals live in a temporary folder deleted at exit, so the player's own are neither read nor changed; the technical log stays the usual one and says "Demo mode" and its language. `EDROCKMASTER_JOURNAL_DIR` is ignored.

**Packaging for Windows** (ADR 0022): the Microsoft Store distributes the application as an MSIX package, which it signs.

- `.github/workflows/windows.yml` runs on the **GitHub mirror only** (`windows-latest`; Gitea reads `.gitea/workflows/` and ignores it), with no secret: it builds the interface, runs the Python tests on Windows, decides the release plan, packages, **starts the packaged application on a recorded journal**, then in demo mode (its log must say that the interface is ready and the journal read, with no error), and keeps the packages 14 days.
- `scripts/package_desktop.py` (on Windows): the build file (ADR 0016), the icons (`scripts/make_icons.py`, a placeholder rock until a designed icon), PyInstaller (`packaging/windows/EDRockMaster.spec`: one folder, no console, no Tk), the **portable zip** `EDRockMaster-v<version>-windows.zip` (unsigned: SmartScreen warns), and the **MSIX** `EDRockMaster-v<version>.msix` with `makeappx` (`packaging/windows/AppxManifest.xml.in`: full trust, `%LOCALAPPDATA%\EDRockMaster` unvirtualized so that data stays shared with the plugin).
- The package identity comes from the GitHub repository variables `EDROCKMASTER_MSIX_NAME`, `EDROCKMASTER_MSIX_PUBLISHER` and `EDROCKMASTER_MSIX_PUBLISHER_NAME`, as Partner Center gives them for the reserved name, and `EDROCKMASTER_MSIX_DISPLAY_NAME`, the reserved name itself, which the Store requires as the package's display name; without them, a development identity.
- Package versions (`scripts/release_plan.py`): `X.Y.(Z×100+N).0` for candidate N, `X.Y.(Z×100+99).0` for production, `X.Y.(Z×100).0` for a development build. A candidate goes to the Store as a package flight to the testers; production is rebuilt from the candidate's commit. Submission is by hand in Partner Center for now.
- `scripts/fixture_to_journal.py` writes a fixture back as a journal file, to try the application by hand.

## Testing

- **Domain and application: test-driven**, with plain `pytest`, no EDMC needed.
- **Fixtures**: real journal excerpts (`tests/fixtures/*.jsonl`), recorded with the recorder.
- **Replay tests**: a whole recorded session is replayed through `Companion` and the panel's presenter, and the final statistics, checked by hand against the raw journal, are asserted.
- **EDMC adapters**: tested with fake `config`, `l10n` and `theme` modules injected by `tests/conftest.py`.
- **UI**: the presenter and the preferences form are pure and fully tested. The tkinter widgets are kept thin; their tests use a real Tk and are skipped where no display exists (CI), so they run on developers' machines. Checked in game during test 1A.
- CI: `ruff`, `mypy --strict`, `pytest` with coverage on `domain/` and `application/`.
