# Design of the desktop application

*English · [Français](design.fr.md)*

Design of EDRockMaster Companion, the desktop application (design decision ADR 0020, in the project's architecture repository): it reads the game journal, computes mining, combat, trade and engineering live, and shows them in its own window. It replaced the EDMC plugin, retired before it had players (ADR 0024); the domain and its rules came from it unchanged. Scope: **milestone 1, step 1A** (local, no server), with combat, trade, engineering and the commander's situation (ADR 0011, 0013 to 0015, 0017 to 0019, 0023). The server link (step 1B) is designed here so that 1A does not have to be reworked, but it is not implemented yet. Engineering rules come from `edrockmaster-architecture`.

## Goals of step 1A

- Live mining assistance with no server: prospector alerts, cores, session statistics, limpets.
- Bilingual interface (English, French), in the system's language or the one chosen.
- A journal recorder (opt-in) that turns real play sessions into test fixtures.
- Structure ready for the server link: ports already defined, adapters added in 1B.

Out of scope for 1A: uploads, sign-in, cargo value estimates (they need server prices), overlay.

## Architecture

Hexagonal, like the services:

```
edrockmaster/
  __init__.py                   VERSION
  domain/                       pure Python: no I/O, no interface
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
    engineering/                engineering context (ADR 0017, ADR 0027 on foot)
      journal.py                journal entry → engineering fact
      on_foot_journal.py        on-foot journal entry → engineering fact (ADR 0027)
      session.py                EngineeringTracker aggregate (inventory, caps, collection, goals, engineers)
      on_foot.py                its on-foot part: ship locker, backpack, suits and weapons seen
      catalogue.py              game data: materials (grade, cap), blueprints, effects, module types, engineers, on-foot materials and engineers
      catalogue.json            that data, written by scripts/import_engineering_data.py (Frontier's, see NOTICE)
      goals.py                  blueprint and experimental effect goals
  application/
    activity.py                 the activities: mining, combat, trade, engineering
    build.py                    BuildInfo: full version, commit and channel of the running build (ADR 0016)
    companion.py                Companion: records the journal once, hands each entry to every activity, owns the settings
    settings.py                 PluginSettings (alerts, sound, recorder, activities shown) and their defaults
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder, GoalRepository (and, in 1B, UploadQueue, Authenticator)
    mining_service.py           mining use cases: handle a journal entry, reset the session, apply settings
    combat_service.py           combat use cases: handle a journal entry, reset the session
    trade_service.py            trade use cases: handle a journal entry, reset the session
    engineering_service.py      engineering use cases: journal, goals and their storage, reset
    situation_service.py        the commander's situation
  infrastructure/
    settings_store.py           SettingsStore on a key-value store (keys prefixed "edrockmaster.")
    settings_file.py            that store: settings.json in the data directory
    recorder_jsonl.py           JournalRecorder: JSONL files in the data directory
    database.py                 the local SQLite database: opening, migrations, copy, moving aside (ADR 0018)
    migrations.py               the database schema, one migration per version
    goal_repository.py          GoalRepository on the local database
    catalogue_file.py           reads the engineering catalogue shipped with the application
    build_file.py               reads edrockmaster/build.json, written by the packaging
    sound.py                    Notifier: alert sounds, played by the host's function
    strings_catalogue.py        the core's translations (L10n/*.strings), number formats, the system's language
    paths.py                    data directory per platform
    worker.py                   a thread fed by a queue of jobs: the I/O thread, the core thread
    clock.py                    Clock: system time, UTC
  ui/                           presenters: notifications in, texts out, no interface toolkit
    panel_model.py              PanelModel (texts of a block), local data notices, shared formatting
    presenter.py                ActivityPresenter: the blocks of the activities shown
    mining_presenter.py         mining notifications → PanelModel
    combat_presenter.py         combat notifications → PanelModel
    trade_presenter.py          trade notifications → PanelModel
    engineering_presenter.py    engineering notifications → PanelModel
    engineering_names.py        names of materials, blueprints, effects, module types, engineers and goals
    commodity_names.py          names of the mineable commodities known before the journal names them
  desktop/                      the application (ADR 0020): its composition root and its window
    journal_folder.py           where the game writes its journal; journal files in order
    journal_reader.py           JournalFollower (follows the journal as the game writes it), JournalWatcher (its thread)
    core.py                     DesktopCore: the composition root, the core thread, the live view pushed
    live_view.py                the live view, as schemas/live_view.schema.json describes it
    engineering_view.py         the engineering part of the live view, the catalogue for the goal form and the blueprints tab
    settings_view.py            the settings form: what it shows, what it asks for
    demo.py                     the demo journal (--demo)
    window.py                   the pywebview window, InterfaceApi, the entry point (python -m edrockmaster.desktop)
    schemas/                    JSON Schemas of what the core sends to the interface
    interface/index.html        the interface, built from web/ (not in git)
L10n/fr.strings                 French translations of the core's texts
web/                            the interface: Svelte 5 and TypeScript (ADR 0021)
```

Dependency rule: `domain` imports nothing else of the application; `application` imports `domain`; `infrastructure` and `ui` import `application` and `domain`, never the window; `desktop` composes them all. `lint-imports` (in the CI) checks it.

## Data flow

1. The journal reader (`JournalWatcher`, its own thread) reads what the game added to the current journal file, and queues each entry for the core thread.
2. On the core thread, `DesktopCore` passes the entry to `Companion.handle_journal_entry(entry, is_beta)`, which copies it to the `JournalRecorder` (if recording is enabled), then hands it to each activity and to the situation. Each activity translates the journal on its own; below, the mining path.
3. `domain/mining/journal.py` turns the raw entry into a typed fact (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`, …) or ignores it. Unknown events and fields are ignored, never fatal.
4. The `MiningTracker` aggregate applies the fact and returns session notifications.
5. The `ProspectingMonitor` evaluates every prospected asteroid against the alert settings.
6. The service forwards the outcome: the alert to the `Notifier` (if sound is enabled), and returns the notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) to the caller, which hands them to the `ActivityPresenter`.
7. The core builds the live view and pushes it to the interface.

All of this is pure computation on small objects (well under a millisecond per event): it stays on the core thread. Anything touching files goes through the I/O thread.

`desktop/core.py` is the composition root: it builds the I/O and core threads, the adapters and the `Companion` at start, and stops them at exit. The interface's reset button ends the session of its activity. Any exception while handling an entry is logged; the next entries are handled normally.

## Threads

- **Main thread**: pywebview's window and its event loop.
- **Journal thread** (`EDRockMaster journal`): `JournalWatcher` reads the journal every second.
- **Core thread** (`EDRockMaster core`, an `IoWorker` of its own): every call to the companion, the presenters and the view builders. The journal thread and the interface's calls only queue jobs for it; it calls `push`, which must not block.
- **One I/O thread** (`infrastructure/worker.py`): a daemon thread fed by a `queue.Queue` of jobs (append to the recording file, the local database, the settings file; in 1B, uploads and authentication). What it reads reaches the core thread as a job queued there.
- At exit: the watcher stops, then the core thread; the database closes in a last job of the I/O thread, which then stops.

## Mining session lifecycle

| Situation | Effect |
| --- | --- |
| `SupercruiseExit`, `Location` or `StartUp` with `BodyType` = `PlanetaryRing` | Current ring known (name, system) |
| First mining activity (`LaunchDrone` prospector, `ProspectedAsteroid`, `MiningRefined`) | Session starts if none is running |
| `ProspectedAsteroid` | Asteroid recorded, alert policy evaluated |
| `MiningRefined` | One ton of the commodity counted |
| `LaunchDrone` | Limpet counted by type |
| `AsteroidCracked` | Core cracked |
| `Cargo` | Cargo snapshot: tons on board, capacity used |
| `EjectCargo` | Ejected tons counted apart (not part of production) |
| No mining activity for 10 minutes | Session paused: inactive time is not counted |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Session ends |
| `StartUp` (written by EDMC, in older recordings) | Current ring from the event's `Body`/`BodyType`; cargo figures come with the next `Cargo` event (the game writes one at each refinement) |
| `MarketSell` | Credited to the running session, or else to the last one that ended: only its mined tons not yet ejected nor sold, at the sale's unit price |
| Manual reset (button of the block) | Session ends, a new one can start |
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
| Reward with no arrival seen (the game started on the site: `StartUp`, `Location` off station) | A segment of type **unknown**, from that reward; miscellaneous if the commander mines there (`ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`, prospector or collector limpets) |
| `CommitCrime` during a session | Counted by kind of crime: fines and bounties on the commander, never deducted from the credits |
| `Died` | Session ends; unredeemed vouchers are lost |
| `Shutdown`, `ShutDown` | Session ends |
| `RedeemVoucher` (bounties, combat bonds) | The vouchers paid are removed, per faction, never below zero |
| `CommunityGoal` | The goals the commander joined: contribution, percentile band, tier reached |
| Manual reset (button of the combat block) | Session ends, a new one can start; still on the site, the next segment starts at the reset |

Statistics of a combat session: its segments (site type, duration, kills, credits, rates), an average **per site type, weighted by time** (total kills and credits over total duration), time on combat sites, kills (and shared kills), bounty and combat bond credits, miscellaneous kills, crimes. Shown with the block: unredeemed vouchers (known since the journal file began only: the journal does not restate older ones) and the community goals. Superpower factions written `$faction_Federation;` are normalised to `Federation`. Another activity never ends a combat session: a miner may fight back and keep mining.

The *Activities* tab shows one block per activity the player chose (*Settings*), each with its own **Reset** button ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.md)); the block of the last activity to **progress** is highlighted. For combat, a session or a segment that starts or ends, a reward or a crime is progress; leaving a site without a segment, vouchers and community goals are not. For trade, a session that starts or ends, a purchase, a sale or a loss. A hidden activity is still followed: shown again, it is up to date.

## Trade

Trade follows purchases and sales of goods on markets ([ADR 0014](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0014-plugin-trade-activity.md)). Its active time is the **flight time**: a **leg** runs from undocking to the next docking, and counts once a trade follows it in the session.

| Situation | Effect |
| --- | --- |
| First `MarketBuy`, or first `MarketSell` of bought goods (`AvgPricePaid` above 0) | Trade session starts. The flight to that market does not count |
| `MarketBuy` | The goods are on board at their cost; the market is the origin of their route (the last purchase wins) |
| `MarketSell` of bought goods | Profit `(SellPrice - AvgPricePaid) × Count`, the game's own, even for goods bought before the journal file began (origin unknown). Counted on the route: commodity, market of purchase, market of sale |
| `MarketSell` with `AvgPricePaid` 0 | Not bought: **refined commodities** if a refinery produces them (their profit belongs to mining), **other goods** otherwise. In no profit and no rate; no session started |
| `Undocked`, then `Docked` | A leg. It counts once a purchase or a sale of bought goods follows it in the session: a stop without trade is part of the flight, a flight after the last trade does not count. Time docked never counts |
| `Location` or `StartUp` off station | In flight since an unknown time: the leg counts from there |
| `EjectCargo` of bought goods | Loss at the price paid, deducted from the profit |
| `CargoTransfer` to a fleet carrier, or to the ship while docked at one ([ADR 0019](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0019-fleet-carrier-transfers.md)) | A **deposit** or a **withdrawal**: counted per commodity and direction, with the number of transfers. Starts the session and counts the legs it follows, like a purchase; earns nothing. The goods keep their cost and origin at the carrier, and come back with them. Transfers with an SRV are ignored |
| `Cargo` | Bought goods that left without a sale (a mission) are no longer on board: never more than the ship carries |
| `Died` | The bought cargo is lost (a loss), the session ends |
| `Shutdown`, `ShutDown` | Session ends; the cargo stays known |
| Manual reset (button of the trade block) | Session ends, a new one can start |

Statistics of a trade session: flight time, profit (sales minus losses), profit and tons per hour of flight, tons sold, losses, the cost of the bought goods on board, one line per route (tons, profit, profit per ton, sales), the transfers with fleet carriers, refined commodities and other goods. In the block, a route too long names its destination only. Out of scope: the fleet carrier's market and stock, smuggling, missions. Trade is not uploaded.

## Engineering

Being built (design decision ADR 0017): materials, engineers and blueprint goals, ship engineering first.

**Game data.** The journal names materials (`chemicalmanipulators`), blueprints (`FSD_LongRange`) and experimental effects (`special_fsd_heavy`), but gives neither a material's grade nor the ingredients of a blueprint, nor which engineer offers it on which module. `scripts/import_engineering_data.py` reads them from EDCD/FDevIDs and EDCD/coriolis-data at pinned commits and writes `domain/engineering/catalogue.json`, one entry per line for readable diffs; `Catalogue.from_data` checks it when read. The script refuses a name it cannot map; the few fixes it makes are listed in it, each with its reason (a trailing space in FDevIDs, misspellings in coriolis-data). It keeps the module types that have blueprints, the engineers who offer them, and the effects an engineer still applies (legacy effects have no ingredients). To follow a game update: change the pinned commits, run the script, review the diff of the catalogue.

The data is Frontier's, not under the application's licence: `NOTICE`, shipped with the application, says so. Names are in English in the catalogue and translated by `L10n/fr.strings`; `tests/test_translations.py` checks that every name has its translation. Material names in French are the game's own, taken from a recorded journal, where known.

**The context.** `domain/engineering/journal.py` reads the ship materials events: `Materials` (the whole inventory, at load), `MaterialCollected`, `MaterialDiscarded`, `MaterialTrade`, `Synthesis`, `TechnologyBroker`, `EngineerContribution` (materials only), `ScientificResearch`, `MissionCompleted` (`MaterialsReward`), `EngineerCraft`, `EngineerProgress` (all engineers at load, then one at a time) and `Shutdown`. `EngineeringTracker` (`session.py`) is the aggregate:

- **Inventory**: unknown until `Materials` gives it (the journal reader reads the current file from its beginning, so the inventory stated at load is known even when the application starts after the game). Each change applies to it, never below 0, never above the material's **cap** (300 at grade 1 down to 100 at grade 5): reaching it is an alert, as what is collected beyond it is lost. A material the catalogue does not know (the game adds some before the community data) is counted, without cap. Never stored.
- **Collection**: from the first change of materials to `Shutdown` or reset; death does not end it. It counts the materials collected or rewarded per category, those used (rolls, effects, synthesis, brokers, contributions, research; a trade only converts), and those that reached their cap.
- **Goals**: a blueprint at a grade for a module type, with a number of rolls, or an experimental effect, with a number of applications. What a goal misses is its ingredients, times its rolls, minus the inventory; it is **ready** when it misses nothing. The **shopping list** adds up every goal. The engineers of a goal are the unlocked ones offering its grade on its module type. An `EngineerCraft` takes one roll (or application, with `ApplyExperimentalEffect`) off the first goal with the same blueprint and grade on the same module type, which `Catalogue.module_of` finds from the item (`int_powerdistributor_size7_class5`; armour by its name); a goal with nothing left is done and removed. The tracker reports these changes, and `EngineeringService` stores them through `GoalRepository` (local database, ADR 0018); the stored goals are loaded at start.
- **Engineers**: status and rank, from `EngineerProgress` (which names them: the catalogue gives their ids).

**On foot** (design decision ADR 0027; being built for 0.5.0). `domain/engineering/on_foot_journal.py` reads `ShipLocker` (the whole ship locker), `Backpack` (the whole backpack), `BackpackChange` (each change, with the material's kind), `Embark`, the loadouts on foot (`SuitLoadout`, `SwitchSuitLoadout`, `CreateSuitLoadout`, `LoadoutEquipModule`) and the purchases and sales of suits and weapons; `Died` is read by `journal.py`. `CollectItems`, `DropItems` and `UseConsumable` are not: the backpack's own events tell the same, and data downloads only show there. The catalogue adds the on-foot materials (196, with their kind: item, component, data, consumable) and the 13 on-foot engineers, from FDevIDs. `OnFoot` (`on_foot.py`), held by `EngineeringTracker`:

- **Inventory**: unknown until the first `ShipLocker` (one follows `LoadGame`). The last `ShipLocker` and the last `Backpack` each replace their place; `BackpackChange` applies between two. Boarding a ship, an SRV or a taxi moves the backpack into the locker until the game restates it, about a second later. Mission items (`MissionID`) are counted apart; stolen goods carry the `OwnerID` of the owner they were taken from, and are the player's all the same (the locker names them with an `OwnerID` of 0 once aboard). Consumables are held, never counted towards goals. Replayed on a real evening, the inventory after each boarding equals the game's next locker.
- **Collection**: the player's own materials brought into the backpack count, by kind, in the engineering collection (which they start if needed); what the backpack carried at a death is lost and counted as such.
- **Equipment**: each suit and weapon the journal showed, by id, as last shown: type, class (the suit's is in its name, `tacticalsuit_class3`; the flight suit has none) and modifications.
- **The player's fleet carrier** (ADR 0029): known from `CarrierLocation` (written at load for its owner) or `CarrierStats`; the ship is docked there while `Docked.MarketID` is its id, until `Undocked`. Moving on-foot materials to or from the carrier writes no event: while docked there, the change of the player's own materials between two statements of the locker is a **move** (fewer: to the carrier; more: from it), one per docking. A move is counted nowhere, since what the carrier holds is not known (the server will read it from Frontier, ADR 0028). Replayed on the evening of 5 October: 15 materials moved at 21:39, then 127 of 65 kinds at 23:22. The sanitiser keeps `CarrierLocation` and reduces `CarrierStats` to its id, both under the neutral id of every carrier.

**Activities block, on foot.** The engineering block adds the on-foot materials gained per kind (items, components, data) and those lost at a death.

**Activities block.** The engineering block shows the materials gained per category, used, at their cap, and the goals ready out of all goals (or that the inventory is unknown). Its alert is the last material at its cap, goal ready or goal done; a ready goal's alert goes when the player removes the goal. It progresses on a change of materials in game, a cap or a goal ready; the game's statement at load is no progress. Material names are the game's own when the journal gave them, else the catalogue's, translated. The *Engineering* and *Blueprints* tabs show the rest (below, Desktop application).

## Prospector alerts

- Threshold per commodity, in percent of the asteroid, editable. Defaults (2026-10-03, to be tuned after the in-game test): platinum 20 %, low temperature diamonds 20 %, painite 25 %, osmium 25 %, palladium 25 %, gold 25 %. Minimum content Low, no minimum reserve, core alerts on, sound on, journal recorder off.
- Minimum content level (High, Medium, Low).
- Optional minimum remaining reserve (`Remaining`).
- A motherlode (core) raises its own alert, whatever the thresholds.
- Duplicate prospecting of the same asteroid (same composition within 60 seconds) does not raise a second alert.

## User interface

**Activities** tab: one block per activity shown. For mining: status (no session, mining in a ring, session ended and why), the last prospector alert, highlighted, until the next asteroid is prospected, then the statistics: active time, refined tons, rate, tons per commodity, asteroids prospected and, once known, cores, limpets, cargo and sales. The statistics of an ended session stay displayed, and its sales are added to them. A **Reset** button ends the running session. Numbers are written as the interface's language writes them.

The other tabs (*Engineering*, *Blueprints*, *Settings*) and the banner of the commander's situation are described below (Desktop application).

## Settings

Stored in `settings.json` in the data directory (`infrastructure/settings_file.py`), keys prefixed with `edrockmaster.`, read at start and written by the I/O thread when the *Settings* tab saves them. Domain code receives an immutable settings object, never the store.

| Key | Type | Content |
| --- | --- | --- |
| `edrockmaster.settings_version` | text | Format version of the keys below (`1`), for future migrations |
| `edrockmaster.alert.thresholds` | text | JSON object, commodity key → percent (`{"painite": 25.0, …}`) |
| `edrockmaster.alert.minimum_content` | text | `low`, `medium` or `high` |
| `edrockmaster.alert.minimum_remaining` | text | Percent, or empty for none |
| `edrockmaster.alert.cores` | bool | Alert on cores |
| `edrockmaster.sound` | bool | Audible alerts |
| `edrockmaster.record_journal` | bool | Journal recorder |
| `edrockmaster.display.activities` | text | JSON list of the activities shown, at least one (`["mining", "combat"]`) |
| `edrockmaster.display.offered` | text | JSON list of the activities offered when saved (`["mining", "combat", "trade"]`). An activity a later version adds is shown until the player hides it; absent: mining and combat |
| `edrockmaster.display.mode` | text | `last_active` or `stacked`: kept from the plugin's panel; the application shows every activity chosen |
| `edrockmaster.desktop.language` | text | `auto` (the system's), `en` or `fr` |
| `edrockmaster.desktop.journal_folder` | text | The journal folder set by hand; empty: where the game writes it |

Values are read one by one: a missing or invalid value falls back to its own default (and is logged), the others are kept.

## Files

Data directory:

- Windows: `%LOCALAPPDATA%\EDRockMaster` (left unvirtualised by the MSIX package)
- Linux: `$XDG_DATA_HOME/EDRockMaster`, or `~/.local/share/EDRockMaster`
- macOS: `~/Library/Application Support/EDRockMaster`

Contents:

- `settings.json`: the settings (above);
- `logs/`: the technical log, rotating;
- `recordings/`: journal recordings, JSONL, one file per run;
- `edrockmaster.sqlite3`: the local database (below), with its `-wal` and `-shm` files while the application runs;
- `edrockmaster.sqlite3.v<N>.bak`: a copy of the database made before its last migration, from schema version N;
- `edrockmaster.sqlite3.unreadable-<date>`: a database the application could not read, moved aside.

## Local database

One SQLite file for the application's durable **state**, which is neither a setting nor a recording (design decision ADR 0018). Each need has its own tables and its own repository port: the engineering goals first (`GoalRepository`, ADR 0017), the upload queue in 1B (ADR 0005). Nothing in it is sent to the server unless an ADR says so.

- **The I/O thread only.** The database opens in a job of the I/O thread at start, and closes in one at exit. `LocalDatabase.connection()` refuses any other thread. Repositories turn each call into a job; what they read reaches the core thread as a job queued there.
- **Versioned schema.** `PRAGMA user_version` is the schema version; `infrastructure/migrations.py` lists the migrations, applied in order at opening, each in its own transaction, forward only. A released migration never changes. Before migrating a database of version N > 0, the file is copied (SQLite's backup API) to `edrockmaster.sqlite3.v<N>.bak`, and older copies are removed. WAL journal mode.
- **Unreadable file.** A corrupt file (SQLite says it is not a database, or the integrity check fails) or a file written by a newer version of the application (a downgrade) is moved aside as `edrockmaster.sqlite3.unreadable-<UTC date>`, and a new database is created. The log says why, and the interface shows a notice until the player dismisses it.
- **Unavailable database.** Any other failure (another instance holds the file, the disk refuses it, a migration fails and is rolled back) leaves the file as it is; nothing is stored until the application restarts, the log says why and the interface says so. The application never fails because of its database.
- **Tests.** Every schema version has a fixture, `tests/fixtures/database/schema-v<N>.sql`, kept as released; the tests migrate each one to the latest version, and check that the latest fixture has the schema the migrations create. A new migration therefore comes with its fixture.

## Journal recorder

- Off by default; enabled in the *Settings* tab.
- Writes every entry the application reads, unmodified, one JSON object per line, with the `is_beta` flag: `{"is_beta": false, "entry": {…}}`. File: `recordings/journal-<start, UTC, YYYYMMDDTHHMMSSZ>-<build version>.jsonl`, so a recording says which build counted it.
- The entry is serialised when read, and written by the I/O thread.
- Recordings are what we turn into `tests/fixtures/`; the player decides what to share.
- The repository is public, and a raw recording holds personal data (commander name and Frontier id, squadron, carrier, chat messages, other players' names, reputation). A recording becomes a fixture only through `scripts/sanitise_recording.py`: it keeps the events the application reads and a few harmless ones, reduces `LoadGame` to the game version, drops the reputation (`Factions` of `Location`, `FSDJump`, `StartUp`), the targets' pilot names (`Bounty.PilotName`) and crime victims (`CommitCrime.Victim`), per event, replaces every fleet carrier (name, callsign, id) with a neutral value, and refuses to write if the commander's name or id, or a carrier, remains. `tests/test_replay.py` replays each fixture, with figures checked by hand against the raw journal.

## Internationalisation

- The core's texts (the activity blocks): English source strings in the code, wrapped with `tl()`, translated by `infrastructure/strings_catalogue.py` from `L10n/fr.strings` (UTF-8 `.strings` format). The interface's own texts: JSON catalogues in `web/src/locales/`, with a test that every key is translated and used.
- The language is the system's (Windows' interface language, or the locale variables), or the one chosen in *Settings*, applied at once: the presenters keep domain objects, not texts, and rebuild every text in the current language.
- Counts avoid plural agreement (`prospectors: 3`), which `.strings` files cannot express.
- `tests/test_translations.py` fails if a text passed to `tl()` has no French translation, if a translation is no longer used, or if placeholders differ.
- Commodity names come from the journal's `*_Localised` fields when present (the game's own language), otherwise from our own names.

## Prepared for step 1B

Ports defined in 1A, implemented in 1B:

- `UploadQueue`: its own tables in the local database (ADR 0018); every uploadable fact gets a client id (`uuid4`).
- `Authenticator`: Keycloak device flow; refresh token kept in the data directory.
- `Uploader`: batches (gzip) to `edrockmaster-ingest`, on the I/O thread, with backoff.
- Kill switch: by version (ADR 0016), fetched every 10 minutes from our server.

## Desktop application

Design decision ADR 0020: the core in an application of its own, which reads the journal itself and shows a web interface in a native window. The **journal reader** is in `desktop/`:

- **Folder**: on Windows, the "Saved Games" known folder of the player's profile (wherever it was moved), else `%USERPROFILE%\Saved Games`, then `Frontier Developments\Elite Dangerous`; on Linux, the Proton prefix of the game (Steam app 359320) under the usual Steam folders. `EDROCKMASTER_JOURNAL_DIR` sets it by hand.
- **Files**: `Journal.<start>.<part>.log` (and `JournalBeta.…`), ordered by the start time in their name (two formats, before and since 2022), then by part.
- **Reading**: the first poll reads the current file **from its beginning**, and hands the core every entry: the application reaches the same figures as if it had run since the game started. Then each poll reads what was added; an incomplete line waits for the rest; a newer file (a new session, or the next part of a long one) is followed once the current one is finished. A line that is not an entry is logged and skipped. A beta says so in its file name or its game version (`Fileheader`, `LoadGame`), as EDMC read it.
- **Thread**: `JournalWatcher` polls every second on its own thread (`EDRockMaster journal`), as often as EDMC polled a running game.
- **Cargo**: since the game's 3.3, the journal's `Cargo` event lists the ship's cargo only at load; afterwards the list is in `Cargo.json`, next to the journal files. EDMC added it to the event, and mining (cargo) and trade (goods on board) rely on it: the follower adds it too, when `Cargo.json` describes that very event (same timestamp, the ship), so that an older event read at start never gets the current cargo. The game does not always write `Cargo.json` before the line (in a live session, once 22 ms after it): while the file still describes an earlier event, or cannot be read in full, the follower reads it again every 50 ms, for a second at most, then logs it. Otherwise the event is handed on as the game wrote it.
- **Ship locker** (ADR 0027): most `ShipLocker` lines hold the whole locker, but some only point to `ShipLocker.json`, which then holds the change (seen at a fleet carrier, where the locker emptied with bare lines only). The follower adds the file's content to such a line, on the same terms as `Cargo.json`.
- **Parity**: `tests/desktop/test_parity.py` writes every fixture back as journal files, reads them with the reader, and checks that the core gives exactly the notifications of the replay of the fixture, also for a session split in parts written while the reader follows. Reading 20,000 entries at start takes about 0.1 s, 0.3 s with the core.
- **Boundaries**: `lint-imports` (in the CI) checks that `domain/` and `application/` import no adapter, no host and no interface toolkit (`infrastructure`, `desktop`, `ui`, `webview`, `sqlite3`), that presenters and adapters know nothing of the window, and that the domain imports nothing else of the application.

**The application shell** (ADR 0020, ADR 0021):

- `desktop/core.py`, `DesktopCore`: the composition root. The core (companion, local database, goals, catalogue), fed by the journal reader. Every call to the companion and the presenter happens on the **core thread** (`EDRockMaster core`, an `IoWorker` of its own); the journal reader's thread and the interface's calls only queue jobs. After each change, the core pushes the **live view** to the interface.
- `desktop/live_view.py`, `desktop/schemas/live_view.schema.json`: the live view, described by a JSON Schema: the activities shown and their blocks (texts from the presenters, already in the player's language), the current activity, the local data notice, the journal read. The tests validate every view pushed against the schema; the interface's TypeScript types are generated from it (`pnpm types`), and the CI checks that they are up to date.
- `desktop/window.py`: pywebview shows the interface, one self-contained HTML file (`desktop/interface/index.html`, built from `web/`, not in git), given as a page: no server, no port. The interface calls the core through `InterfaceApi` (`window.pywebview.api`: `ready`, `reset`, `dismiss_notice`); the core pushes with `run_js`, in ASCII JSON (pywebview on GTK gives WebKit the length of a script in characters, not bytes). pywebview creates `window.pywebview` before adding the core's calls to it: the interface waits for `pywebviewready`.
- Settings in `settings.json` of the data directory (above); a rotating log in `logs/`; the language of the system's interface (Windows) or of the locale variables, English otherwise; the presenters' texts translated from `L10n/*.strings`, numbers written as the language writes them.
- **Interface** (`web/`): Svelte 5 and TypeScript, built by Vite into one HTML file; its own texts in `src/locales/*.json`, with a test that every key is translated and used; Vitest and Testing Library; a dark theme from design tokens. Node 22 and pnpm (through corepack) are build tools only.
- **Run it** (development): `cd web && corepack pnpm install && corepack pnpm build`, then `uv run python -m edrockmaster.desktop` (`--debug` opens the web inspector). On Linux, pywebview needs GTK and WebKit2GTK with their Python binding (PyGObject), usually from the system's Python; `EDROCKMASTER_JOURNAL_DIR` points to a journal folder, a recording written back as journal files for instance. `uv run python -m edrockmaster.desktop --demo` (or `EDRockMaster.exe --demo`, `--demo=en`, `--demo=fr`) shows the **demo**: see below.

**Settings** (the *Settings* tab): the settings of the table above (alert thresholds per commodity, minimum content and remaining reserve, cores, sound, journal recordings, activities shown), and the application's own: its **language** (the system's by default; the presenters translate through the core, so a new language applies at once) and its **journal folder** (empty: where the game writes it), used from the next start, since reading another folder at once would count its sessions on top of the current ones. Under the folder, the tab tells the journal file being read, or that the game's journal is awaited; above the tabs, the window says only that no journal folder was found, and its header shows the application's full version beside its name (the live view's `application.version`, from the build file, ADR 0016). The tab also shows where the journal recordings and the log file are (`recordingsFolder`, `logsFolder`), each with a button that opens the folder in the file manager (`open_folder("recordings" | "logs")`; the core refuses any other name, makes the recordings folder if no recording exists yet, and logs a failure; `desktop/folder_opener.py`: the Explorer on Windows, `open` or `xdg-open` elsewhere). In the demo, the recordings stay in its temporary folder, the log in the player's. The folder named by `EDROCKMASTER_JOURNAL_DIR` comes first, then the settings', then the usual one. `settings()` gives the form its content (`settings.schema.json`), `save_settings()` checks it field by field (`desktop/settings_view.py`) and logs what it refuses.

**The engineering view** (ADR 0017): the desktop application's *Engineering* tab, in place of the Tk window ADR 0017 planned. The live view's `engineering` part (`desktop/engineering_view.py`) carries the materials by category and grade with their count and cap, the ship engineers (status, rank; named in the player's language, through `L10n/`, since some carry a title such as *Professor Palin*), the goals with what each misses and the unlocked engineers offering it (ready goals first), and the shopping list. The engineers show in short rows, name and status side by side, the unlocked ones marked, with how many are unlocked; a button folds the list away for the session. The goal form asks the core once for the catalogue (`catalogue()`, schema `goal_catalogue.schema.json`): module types, their blueprints with their grades, their experimental effects. The interface adds, changes (rolls, applications) and removes goals (`add_goal`, `change_goal`, `remove_goal`); the core checks a new goal against the catalogue and the domain, logs what it refuses, and stores goals in the local database (ADR 0018). A switch at the top of the tab shows the ship part or the **on-foot part** (ADR 0027): the live view's `engineering.onFoot` carries the on-foot materials held, by kind (the player's own count, what of it is in the backpack, what is held for missions apart), the moves to and from the player's carrier, with the reminder that they no longer count, the suits and weapons seen with their class (suits named by the application, weapons as the game names them), and the 13 on-foot engineers with their status. Goals on foot come with the recipes, in a later change.

**The commander's situation** (ADR 0023): `domain/situation/` reads `Commander`, `LoadGame`, `Location`, the jumps and supercruise, `Docked`, `Undocked`, `Loadout`, `ShipyardSwap`, `SetUserShipName`, `Embark`, `Disembark` and the wing events, into the commander's name, the ship (its type in the game's language, the player's name and registration), on foot or not, the system, the station, the game mode with the private group's name, and the wing members. `Shutdown` keeps the last situation and says the game is closed. It is in memory only: never stored, never uploaded; the application shows it in a banner, through the live view's `situation`. Wing members are other players: the recording sanitiser names them `Wingmate 1`, `Wingmate 2`…

**The demo** (`--demo`, `desktop/demo.py`): the application reads a sample journal instead of the player's, for the Store's screenshots and the documentation, or to discover it without playing. `scripts/make_demo_journal.py` writes it (`desktop/demo_journal.jsonl`, checked by a test to be up to date) from published fixtures: a mining session in a resource extraction site with its combat bonds, under the fictional **Commander Jameson** in Open play, in the *Rock Hound*, with the materials, engineers and collected materials of the engineering fixture; it stops while the commander is still mining. At start, its timestamps are moved so that it ends now: the mining, combat and engineering sessions are running. The demo is in the system's language, or the one it names (`--demo=en`, `--demo=fr`); the journal was recorded with the game in French, so for a demo in English the names the game writes in its language and the application shows as they are (commodities, asteroid content, community goal) are replaced by the game's names in English, the game's names of the materials are left out so that the catalogue names them, and each screenshot is in one language only. Its settings and goals live in a temporary folder deleted at exit, so the player's own are neither read nor changed; the technical log stays the usual one and says "Demo mode" and its language. `EDROCKMASTER_JOURNAL_DIR` is ignored.

**The blueprints tab** (ADR 0017): the game data to browse, without going through a goal. A search (module, blueprint or effect name, or a material they take: what a material is for; case and accents ignored) and a module type filter; each blueprint shows one grade at a time (the highest first): its ingredients against the inventory, held or missing, how many rolls the inventory allows, and the engineers offering that grade, unlocked first with their rank; each module's experimental effects show their ingredients and how many applications are possible. A button adds the grade or the effect to the goals (`add_goal`, one roll). The catalogue call (`catalogue()`) carries, for each blueprint, one recipe per grade (ingredients, engineers' ids) and, for each effect, its ingredients, named in the core's language: the tab asks for it again when the language changes. The search and the arithmetic are in `web/src/lib/blueprints.ts`.

**Packaging for Windows** (ADR 0022): the Microsoft Store distributes the application as an MSIX package, which it signs.

- `.github/workflows/windows.yml` runs on the **GitHub mirror only** (`windows-latest`; Gitea reads `.gitea/workflows/` and ignores it), with no secret: it builds the interface, runs the Python tests on Windows, decides the release plan, packages, **starts the packaged application on a recorded journal**, then in demo mode (its log must say that the interface is ready and the journal read, with no error), and keeps the packages 14 days.
- `scripts/package_desktop.py` (on Windows): the build file (ADR 0016), the icons (`scripts/make_icons.py`, a placeholder rock until a designed icon), PyInstaller (`packaging/windows/EDRockMaster.spec`: one folder, no console, no Tk), the **portable zip** `EDRockMaster-v<version>-windows.zip` (unsigned: SmartScreen warns), and the **MSIX** `EDRockMaster-v<version>.msix` with `makeappx` (`packaging/windows/AppxManifest.xml.in`: full trust, `%LOCALAPPDATA%\EDRockMaster` unvirtualised so that the data survives a reinstall and the player can find it).
- The package identity comes from the GitHub repository variables `EDROCKMASTER_MSIX_NAME`, `EDROCKMASTER_MSIX_PUBLISHER` and `EDROCKMASTER_MSIX_PUBLISHER_NAME`, as Partner Center gives them for the reserved name, and `EDROCKMASTER_MSIX_DISPLAY_NAME`, the reserved name itself, which the Store requires as the package's display name; without them, a development identity.
- Package versions (`scripts/release_plan.py`): `X.Y.(Z×100+N).0` for candidate N, `X.Y.(Z×100+99).0` for production, `X.Y.(Z×100).0` for a development build. A candidate goes to the Store as a package flight to the testers; production is rebuilt from the candidate's commit. Submission is by hand in Partner Center for now.
- `scripts/fixture_to_journal.py` writes a fixture back as a journal file, to try the application by hand.

## Testing

- **Domain and application: test-driven**, with plain `pytest`.
- **Fixtures**: real journal excerpts (`tests/fixtures/*.jsonl`), recorded with the recorder.
- **Replay tests**: a whole recorded session is replayed through `Companion` and the presenters, and the final statistics, checked by hand against the raw journal, are asserted; the parity tests read the same fixtures back through the journal reader.
- **Desktop**: the core with a fake push, the window with a stand-in for pywebview, the views validated against their JSON Schemas; checked in a real window (GTK/WebKit on Linux, WebView2 in the Windows runner's smoke test).
- **Interface**: Vitest and Testing Library, its logic in `web/src/lib/` tested alone.
- CI: `ruff`, `mypy --strict`, `lint-imports`, `pytest` with coverage on `domain/`, `application/`, `ui/` and `desktop/`; the interface's lint, type check, tests and build.

