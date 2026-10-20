# Design of the desktop application

*English · [Français](design.fr.md)*

Design of EDRockMaster Companion, the desktop application (design decision ADR 0020, in the project's architecture repository): it reads the game journal, computes mining, combat, trade and engineering live, and shows them in its own window. It replaced the EDMC plugin, retired before it had players (ADR 0024); the domain and its rules came from it unchanged. Scope: **milestone 1, step 1A** (local, no server), with combat, trade, engineering and the commander's situation (ADR 0011, 0013 to 0015, 0017 to 0019, 0023). The server link (step 1B) is designed here so that 1A does not have to be reworked, but it is not implemented yet. Engineering rules come from `edrockmaster-architecture`.

## Goals of step 1A

- Live mining assistance with no server: prospector alerts, cores, session statistics, limpets.
- Bilingual interface (English, French), in the system's language or the one chosen.
- A journal recorder (opt-in) that turns real play sessions into test fixtures.
- Structure ready for the server link: ports already defined, adapters added in 1B.

Out of scope for 1A: uploads, sign-in, overlay.

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
      hotspots.py               hotspot commodities, rings and their hotspots, the search (ADR 0040)
      markets.py                markets that buy a commodity, pad sizes, the sale search (ADR 0040)
    combat/                     combat context
      journal.py                journal entry → combat fact
      sites.py                  combat sites, as the game names them on arrival
      session.py                CombatTracker aggregate (sessions by site segments, crimes)
      vouchers.py               VoucherLedger aggregate: unredeemed vouchers per commander and galaxy (ADR 0052)
    trade/                      trade context
      journal.py                journal entry → trade fact
      session.py                TradeTracker aggregate (sessions, routes, flight time, cargo bought, losses)
    situation/                  the commander's situation (ADR 0023): who, ship, where, game mode, wing; route.py, the current route (ADR 0043)
    community_goals/            community goals context (ADR 0032)
      journal.py                journal entry → community goals fact
      goals.py                  CommunityGoals aggregate (the goals joined, until handed in)
    engineering/                engineering context (ADR 0017, ADR 0027 on foot)
      journal.py                journal entry → engineering fact
      on_foot_journal.py        on-foot journal entry → engineering fact (ADR 0027)
      session.py                EngineeringTracker aggregate: facts in, its state (inventory, caps, engineers, goals), events out (ADR 0041)
      progress.py               how far one goal is: what it takes, what is missing, who offers it (pure)
      reservation.py            the materials held shared along the priority (ADR 0033, pure)
      collection.py             the collection of materials and its statistics
      events.py                 what the aggregate tells the application: statistics, collection, caps, goals ready, progressed, done
      on_foot.py                its on-foot part: ship locker, backpack, suits and weapons seen
      catalogue.py              game data: materials (grade, cap), blueprints, effects, module types, engineers, on-foot materials, engineers, class upgrades and modifications
      catalogue.json            that data, written by scripts/import_engineering_data.py (Frontier's, see NOTICE)
      goals.py                  blueprint and experimental effect goals
  application/
    activity.py                 the activities: mining, combat, trade, engineering
    build.py                    BuildInfo: full version, commit and channel of the running build (ADR 0016)
    companion.py                Companion: records the journal once, hands each entry to every activity, owns the settings
    settings.py                 PluginSettings (alerts, sound, recorder, activities shown, sources) and their defaults
    community.py                what a community source answers: found, or off, busy, down (ADR 0039)
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder, GoalRepository, GalaxyCatalogue, CommodityMarkets, JournalArchive, PastJournalStore, UpdateSource
    mining_service.py           mining use cases: handle a journal entry, reset the session, apply settings
    combat_service.py           combat use cases: handle a journal entry, reset the session, the vouchers of past and live journals
    past_journals.py            PastJournalReader: the journals of past game sessions, each read once (ADR 0052)
    updates.py                  UpdateService: the channel, the newer version, never a lower one (ADR 0053)
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
    past_journal_store.py       PastJournalStore on the local database: the files read and the vouchers they gave
    catalogue_file.py           reads the engineering catalogue shipped with the application
    build_file.py               reads edrockmaster/build.json, written by the packaging
    sound.py                    Notifier: alert sounds, played by the host's function
    strings_catalogue.py        the core's translations (L10n/*.strings), number formats, the system's language
    paths.py                    data directory per platform
    worker.py                   a thread fed by a queue of jobs: the I/O thread, the core thread
    velopack_updates.py         UpdateSource: Velopack, the GitHub releases or EDROCKMASTER_UPDATE_SOURCE
    local_server.py             the phone and tablet's HTTP server: the page, the calls, the live view as events (ADR 0055)
    local_addresses.py          the computer's local addresses, the one towards the internet first
    clock.py                    Clock: system time, UTC
    sources/                    community sources (ADR 0039): polite HTTP client, cache, Spansh, Ardent Insight
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
    journal_archive.py          FolderArchive: the journal files of the folder, for the past journals' reading
    core.py                     DesktopCore: the composition root, the core thread, the live view pushed
    handlers/                   the interface's calls, one handler per context (ADR 0041), and the CoreContext they reach the core through
    live_view.py                the live view, as schemas/live_view.schema.json describes it
    engineering_view.py         the engineering part of the live view, the catalogue for the goal form and the blueprints tab
    settings_view.py            the settings form: what it shows, what it asks for
    demo.py                     the demo journal (--demo)
    updates.py                  the updates thread: at start, then every 24 hours
    phone.py                    the phone and tablet: the local server as the settings say, its link and QR code
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
- **Past journals thread** (`EDRockMaster past journals`, an `IoWorker`): `PastJournalReader` reads the journals of past game sessions at start and each time the game opens a new file (ADR 0052). Its ports block: it `call`s jobs of the I/O thread and waits for them. What it reads reaches the core thread as a job queued there.
- **Updates thread** (`EDRockMaster updates`, `desktop/updates.py`): an application installed by Velopack checks for a newer version at start, then every 24 hours, and at once when the update settings change (ADR 0053). A download holds neither the core nor the I/O thread; a version ready reaches the core thread as a job queued there.
- **Local server threads** (`EDRockMaster local server`, and one per request): only while *Phone and tablet* is on (ADR 0055); a call of a device runs on its request's thread, as pywebview runs the window's.
- At exit: the watcher stops, then the past journals thread (a first reading still running starts again next time), then the core thread; the database closes in a last job of the I/O thread, which then stops. Last, the updates thread stops (a download under way is dropped), and a version ready is handed to Velopack, which applies it once the application has quit.

## Mining session lifecycle

| Situation | Effect |
| --- | --- |
| `SupercruiseExit`, `Location` or `StartUp` with `BodyType` = `PlanetaryRing` | Current ring known (name, system) |
| First mining activity (`LaunchDrone` prospector, `ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`) | Session starts if none is running |
| `LaunchDrone` collector | Starts no session: it also picks up salvage, escape pods or engineering materials; what it brings back tells (fragments reach the refinery, `MiningRefined`) |
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

Statistics of a session: active duration, tons per commodity, total tons, tons per hour, asteroids prospected (by content level), cores found and cracked, limpets launched (prospector, collector), tons sold and credits earned.

**Limpets on board** ([ADR 0042](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0042-limpets-on-board.md)): the count `Cargo` gives (`drones`), shown in the mining card. When it falls from above the setting `edrockmaster.alert.limpets` (5 by default) to it or below, during a mining session, one alert (`LimpetMonitor`, `domain/mining/limpets.py`): the prospector's sound if the sound is on, and *N limpets left* in the card until the next asteroid prospected. It is re-armed when the count rises above the threshold, for a new session, or when the threshold changes.

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
| Reward with no arrival seen (the game started on the site: `StartUp`, `Location` off station) | A segment of type **unknown**, from that reward; miscellaneous if the commander mines there (`ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`, prospector limpets; not collectors, which also pick up what pirates drop) |
| `CommitCrime` during a session | Counted by kind of crime: fines and bounties on the commander, never deducted from the credits |
| `Died` | Session ends; the commander's unredeemed vouchers are lost |
| `Shutdown`, `ShutDown` | Session ends |
| `RedeemVoucher` (bounties, combat bonds) | Every voucher of that kind of each faction paid is removed: a broker pays less than the vouchers, combat bonds are paid more (ADR 0049) |
| `Fileheader`, `Commander`, `LoadGame` | Who plays (`FID`) and in which galaxy (`gameversion` below 4 since Update 14, 29 November 2022: Legacy): each save has its own vouchers |
| `CommunityGoal` | The goals the commander joined: contribution, percentile band, tier reached |
| Manual reset (button of the combat block) | Session ends, a new one can start; still on the site, the next segment starts at the reset |

Statistics of a combat session: its segments (site type, duration, kills, credits, rates), an average **per site type, weighted by time** (total kills and credits over total duration), time on combat sites, kills (and shared kills), bounty and combat bond credits earned (as the journal writes them, the game's notification amounts: a conflict zone's combat bonds were paid 3.3 to 3.7 times more at redemption, on the journals of 3 to 12 October 2026), miscellaneous kills, kills and credits **by victim faction** (`VictimFaction` of `Bounty` and `FactionKillBond`: the three with most kills, then the others together), crimes **by kind** (`CrimeType`, named in the player's language; a kind the application does not know is shown from its symbol, in English). Shown with the block: the unredeemed vouchers, below. Superpower factions written `$faction_Federation;` are normalised to `Federation`. Another activity never ends a combat session: a miner may fight back and keep mining.

The *Activities* tab shows one block per activity the player chose (*Settings*), each with its own **Reset** button ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.md)); the block of the last activity to **progress** is highlighted. For combat, a session or a segment that starts or ends, a reward or a crime is progress; leaving a site without a segment and vouchers are not. **Community goals** ([ADR 0032](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0032-community-goals-card.md)) have a card of their own, which is not a session and never progresses: shown only while a goal is joined, one tile per goal (title, system unless the title names it, contribution, percentile band, tier reached out of the top tier) with its expiry counted down by the interface, or "Complete: reward to collect". A goal goes when the game's list no longer has it, or at once with its reward (`CommunityGoalReward`) or its discard (`CommunityGoalDiscard`), after which the game writes no new list. For trade, a session that starts or ends, a purchase, a sale or a loss. A hidden activity is still followed: shown again, it is up to date.

**Cards** (ADR 0021). The activity blocks and the parts of the *Engineering* view (ship: goals, shopping list, inventory, engineers; on foot: goals, shopping list, inventory, carrier, suits and weapons, engineers) are cards, one below the other (`CardStack.svelte`). The player moves a card by dragging its handle onto another (it takes that one's place), or with its arrows from the keyboard, and folds or unfolds it; a card is draggable only while its handle is held, so that its text and inputs stay usable. The layout of each view, every card in order and those folded, is kept between sessions: the interface asks the core for it once (`layout()`, schema `layout.schema.json`) and sends back each change of a view (`save_layout`); the core keeps it in `settings.json` (`desktop/layout.py`), as one JSON text. A stored order that leaves out a card (a new one) puts it last, a card it names that no longer exists is dropped, and a stored layout that cannot be read falls back to the first one. With the cards as wide as the window, an activity's statistics show as tiles side by side, and the inventory shows each material category on its own row, its grades side by side, with each grade's cap at the top of its column.

### Unredeemed vouchers ([ADR 0052](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0052-journal-index.md))

The journal never restates the vouchers held: they are only known by following them from the kill to the redemption or the death, and a bounty hunter may hand them in days later. So the application reads **every journal of the folder once**, and keeps what lasts across game sessions in the local database.

- `VoucherLedger` (domain) follows the vouchers of every commander, per galaxy, per kind and paying faction, since the oldest one held.
- `PastJournalReader` (application, on its own thread) reads the **complete** files the index does not know, oldest first: a file is complete once a newer one exists, or once it ends with `Shutdown`. Only the lines of the events it needs are decoded (`FolderArchive` skips the others by their name); betas are left out. Each file is indexed with the ledger it led to in **one transaction**: counted in full or not at all. A file of the index whose size changed, or an unknown file older than the newest of the index, means the order is lost: everything is read again from the files present. Files removed from the folder keep what they gave. `VERSION` (in `past_journals.py`) is raised by a fix that changes what a file gives: the store kept under another version is emptied and everything is read again.
- The **current file** is read live, as before; `CombatService` keeps its voucher facts with their file, and adds them to what the past journals gave. When the reader counts that file later, its facts are dropped from the live ones: nothing is counted twice.
- The first start with this version reads the whole history, on its own thread: the live view does not wait, and the combat card says *Past journals: reading 120 / 860* until it ends. Then each start reads the new files only. *Settings* offers *Read past journals again*.
- **Shown**: one line per kind and paying faction, the largest first (*Unredeemed bounties, Lavigny's Legion: 33,552,700 CR, since 14 October 2026*), three at most, the others together; with several, their total first (*Unredeemed*); with none, once the past journals are read, *Unredeemed: none*, so that the earnings of a session are not taken for vouchers still held. Amounts are the journal's: combat bonds are paid more at redemption (ADR 0049).
- Without a local database, nothing is kept: every past journal is read again at each start, and the figures stay right.

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
| `CargoTransfer` to a fleet carrier, or to the ship while docked at one ([ADR 0019](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0019-fleet-carrier-transfers.md)) | A **deposit** or a **withdrawal**: counted as a balance per commodity, with the number of transfers both ways ([ADR 0044](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0044-net-carrier-transfers.md)); the card shows *At the carrier* for a positive balance, *Taken from the carrier* for a negative one, nothing for a zero balance. Starts the session and counts the legs it follows, like a purchase; earns nothing. The goods keep their cost and origin at the carrier, and come back with them. Transfers with an SRV are ignored |
| `EngineerContribution` of a commodity | Goods **handed to an engineer** to unlock them: they leave the hold for good, earning and losing nothing, shown per engineer and commodity in a running session (none starts). Materials belong to engineering |
| `Cargo` | Bought goods that left without a sale (a mission) are no longer on board: never more than the ship carries |
| `Died` | The bought cargo is lost (a loss), the session ends |
| `Shutdown`, `ShutDown` | Session ends; the cargo stays known |
| Manual reset (button of the trade block) | Session ends, a new one can start |

Statistics of a trade session: flight time, profit (sales minus losses), profit and tons per hour of flight, tons sold, losses, the cost of the bought goods on board, one line per route (tons, profit, profit per ton, sales), the transfers with fleet carriers, the goods handed to engineers, refined commodities and other goods. In the block, a route too long names its destination only. Out of scope: the fleet carrier's market and stock, smuggling, missions. Trade is not uploaded.

### The Trade tab ([ADR 0047](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0047-trade-tab.md))

- **The catalogue** (`domain/trade/catalogue.py`): the commodities the game trades, each with its key (the journal's symbol in lower case, which the sources use too), its category and whether it is rare. `scripts/import_commodities.py` writes it to `domain/trade/commodities.json` from FDevIDs' `commodity.csv` and `rare_commodity.csv`, at the commit the engineering catalogue pins; limpets are left out. Names are FDevIDs' English ones, translated in `L10n/fr.strings` with the game's own French names (read in a player's journals); a test fails when one is missing, or when a recorded journal trades a commodity the catalogue does not know.
- **The tab**: the categories folded, a field that keeps the commodities a word of whose name starts with what is typed (accents and case aside). On top, the **station's market**; below, a commodity chosen opens its **prices across the galaxy**, then **Where to buy** and **Where to sell** below it: around the current system, with the ship's pad and, as the least stock or demand, its cargo capacity (from `Loadout`), all changeable.
- **The galaxy's prices** (`GalaxyPrices` in `domain/commodities.py`, the `GalaxyPrices` component): the lowest, average and highest price the markets ask (`buy`) and pay (`sell`), each `None` when no market sells or buys the commodity, and when the source computed them. Ardent's `/commodities` gives every commodity in one answer, kept a day in the cache and read again for each commodity chosen (`MarketSearch.find_prices` picks it); choosing a commodity asks it, *Refresh* skips the cache. Ardent computes these figures from time to time: the tab says on which day.
- **The cargo to sell**: *Estimate the cargo* prices all the ship carries that may be sold (`domain/trade/cargo.py`: the last `Cargo` inventory, completed from `Cargo.json`, but neither limpets nor the goods of missions, which the journal lists apart with their `MissionID`), each commodity at the best market around the current system. It is the mining card's estimate (`MarketSearch.estimate_cargo`, `CargoEstimate` in `domain/commodities.py`, the `CargoEstimate` component), on another hold: `estimate_cargo({hold: "mining"})` prices the mining session's unsold cargo, `{hold: "ship"}` the whole hold. One request per commodity, at the sources' pace, only when the button is pressed.
- **Trade routes** (ADR 0057, `domain/trade/routes.py`, `application/route_planner.py`, `infrastructure/sources/spansh_routes.py`, the `TradeRoutes` component): the form starts from the current system and station, the ship's pad, cargo capacity and jump range unladen (`Loadout`'s `MaxJumpRange`, down to a tenth), and the commander's credits at load (`LoadGame`: the journal gives no running balance), 3 hops and prices of 2 days at most; all can be changed. `plan_route` sends Spansh the form its site sends (`POST /api/trade/route`, a form, not JSON) and answers at once: the route kept (15 minutes, by its parameters) or *pending* with Spansh's job. The interface then asks `follow_route` every 5 seconds, one request each, for 5 minutes at most, until the route comes (`CommunitySource.follow`: a `Pending` answer is handed on and not kept; the route is kept under the request). Cancelling, or asking another route, stops following. Each hop shows its stations, distance, and per commodity the tonnes, both prices and the profit. One `SourceClient` serves Spansh's searches and routes, so that they go at its pace together. A route of 3 hops from Sol took 87 seconds on 20 October 2026.
- **The station's market** (`domain/trade/station_market.py`): the journal's `Market` line says the player opened a station's commodity market, and `Market.json` holds its commodities; the journal reader adds them to the line when the file describes it (same time, same `MarketID`), as for `Cargo.json`. `StationMarketTracker` keeps the commodities the station sells (a stock) or buys (a demand), until the commander undocks, docks elsewhere, dies or leaves the game; it tells it with `StationMarketChanged`, which the live view turns into a stamp (`stationMarket`: the station, when it was read), and the tab asks `station_market` again when the stamp changes. By category and name, through the catalogue (a commodity it does not know yet is left out). *Compare with the galaxy* asks Ardent's prices of every commodity (the answer of the galaxy's prices, kept a day) and gives each price its gap with the average (`PriceRange.gap`): *+18 %*, in green when it favours the player (cheaper to buy, dearer to sell), red otherwise; once asked, each market opened afterwards is compared too. A commodity's name opens its prices and where to buy and sell it.
- **Where to buy and sell** is one search for both tabs (`application/market_search.py`, `desktop/market_view.py`, the `MarketSearch` component): a `MarketQuery` names its side (`Side.BUY`: the markets that sell, their stock; `Side.SELL`: those that buy, their demand), and `select_offers` keeps the offers the query accepts, the highest price paid or the lowest asked first. The *Mining* tab's *Where to sell* is the same search, on the side `sell`.

## Engineering

Being built (design decision ADR 0017): materials, engineers and blueprint goals, ship engineering first.

**Game data.** The journal names materials (`chemicalmanipulators`), blueprints (`FSD_LongRange`) and experimental effects (`special_fsd_heavy`), but gives neither a material's grade nor the ingredients of a blueprint, nor which engineer offers it on which module. `scripts/import_engineering_data.py` reads them from EDCD/FDevIDs and EDCD/coriolis-data at pinned commits and writes `domain/engineering/catalogue.json`, one entry per line for readable diffs; `Catalogue.from_data` checks it when read. The script refuses a name it cannot map; the few fixes it makes are listed in it, each with its reason (a trailing space in FDevIDs, misspellings in coriolis-data). It keeps the module types that have blueprints, the engineers who offer them, and the effects an engineer still applies (legacy effects have no ingredients). To follow a game update: change the pinned commits, run the script, review the diff of the catalogue.

The data is Frontier's, not under the application's licence: `NOTICE`, shipped with the application, says so. Names are in English in the catalogue and translated by `L10n/fr.strings`; `tests/test_translations.py` checks that every name has its translation. Material names in French are the game's own, taken from a recorded journal, where known.

**The context.** `domain/engineering/journal.py` reads the ship materials events: `Materials` (the whole inventory, at load), `MaterialCollected`, `MaterialDiscarded`, `MaterialTrade`, `Synthesis`, `TechnologyBroker`, `EngineerContribution` (materials only), `ScientificResearch`, `MissionCompleted` (`MaterialsReward`), `EngineerCraft`, `EngineerProgress` (all engineers at load, then one at a time) and `Shutdown`. `EngineeringTracker` (`session.py`) is the aggregate:

- **Inventory**: unknown until `Materials` gives it (the journal reader reads the current file from its beginning, so the inventory stated at load is known even when the application starts after the game). Each change applies to it, never below 0, never above the material's **cap** (300 at grade 1 down to 100 at grade 5): reaching it is an alert, as what is collected beyond it is lost. A material the catalogue does not know (the game adds some before the community data) is counted, without cap. Never stored.
- **Collection**: from the first change of materials to `Shutdown` or reset; death does not end it. It counts the materials collected or rewarded per category, those used (rolls, effects, synthesis, brokers, contributions, research; a trade only converts), and those that reached their cap.
- **Goals**: a blueprint at a grade for a module type, with a number of rolls, or an experimental effect, with a number of applications. What a goal misses is its ingredients, times its rolls, minus what is left of the inventory once the goals above it took their share: the goals come in the player's order, their **priority** ([ADR 0033](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0033-goal-priority.md)), one order over all of them, ship and on foot, a new goal last; the materials held go to them in that order, the ship's and the on-foot ones apart, each goal taking what it needs of what is left even when it cannot be completed (a goal the catalogue does not know, or that does not count materials, takes none). A goal is **ready** when it misses nothing after that; one ready alone but not after the goals above says so (`ready_alone`). The **shopping list** adds up every goal, whatever their order. The engineers of a goal are the unlocked ones offering its grade on its module type. An `EngineerCraft` takes one roll (or application, with `ApplyExperimentalEffect`) off the first goal with the same blueprint and grade on the same module type, which `Catalogue.module_of` finds from the item (`int_powerdistributor_size7_class5`; armour by its name); a goal with nothing left is done and removed. The tracker reports these changes, and `EngineeringService` stores them through `GoalRepository` (local database, ADR 0018); the stored goals are loaded at start.
- **Engineers**: status and rank, from `EngineerProgress` (which names them: the catalogue gives their ids).

**On foot** (design decision ADR 0027; being built for 0.5.0). `domain/engineering/on_foot_journal.py` reads `ShipLocker` (the whole ship locker), `Backpack` (the whole backpack), `BackpackChange` (each change, with the material's kind), `Embark`, the loadouts on foot (`SuitLoadout`, `SwitchSuitLoadout`, `CreateSuitLoadout`, `LoadoutEquipModule`) and the purchases and sales of suits and weapons; `Died` is read by `journal.py`. `CollectItems`, `DropItems` and `UseConsumable` are not: the backpack's own events tell the same, and data downloads only show there. The catalogue adds the on-foot materials (196, with their kind: item, component, data, consumable) and the 13 on-foot engineers, from FDevIDs. `OnFoot` (`on_foot.py`), held by `EngineeringTracker`:

- **Inventory**: unknown until the first `ShipLocker` (one follows `LoadGame`). The last `ShipLocker` and the last `Backpack` each replace their place; `BackpackChange` applies between two. Boarding a ship, an SRV or a taxi moves the backpack into the locker until the game restates it, about a second later. Mission items (`MissionID`) are counted apart; stolen goods carry the `OwnerID` of the owner they were taken from, and are the player's all the same (the locker names them with an `OwnerID` of 0 once aboard). Consumables are held, never counted towards goals. Replayed on a real evening, the inventory after each boarding equals the game's next locker.
- **Collection**: the player's own materials brought into the backpack count, by kind, in the engineering collection (which they start if needed); what the backpack carried at a death is lost and counted as such.
- **Equipment**: each suit and weapon the journal showed, by id, as last shown: type, class (the suit's is in its name, `tacticalsuit_class3`; the flight suit has none) and modifications.
- **The player's fleet carrier** (ADR 0029): known from `CarrierLocation` (written at load for its owner) or `CarrierStats`; the ship is docked there while `Docked.MarketID` is its id, until `Undocked`. Moving on-foot materials to or from the carrier writes no event: while docked there, the change of the player's own materials between two statements of the locker is a **move** (fewer: to the carrier; more: from it), one per docking. A move is counted nowhere, since what the carrier holds is not known (the server will read it from Frontier, ADR 0028). Replayed on the evening of 5 October: 15 materials moved at 21:39, then 127 of 65 kinds at 23:22. The sanitiser keeps `CarrierLocation` and reduces `CarrierStats` to its id, both under the neutral id of every carrier.

**Recipes on foot** (ADR 0027, ADR 0030). The journal names suits and weapons but not what their class upgrades take: the project reads them in game and writes them by hand in `data/odyssey/recipes.toml`, by journal symbol (`tacticalsuit`, `wpn_m_assaultrifle_kinetic_fauto`). The game shows a class upgrade only for an item the player owns, at its next class, so each recipe states its **confidence**: `game` (seen in game, with the date of the reading), `deduced` (from rules of the file, each resting on `game` readings) or `web` (figures read by hand from public sources, named and dated). An unknown recipe is absent: the upgrades to class 5 have not been seen yet. `scripts/import_engineering_data.py` writes them into the catalogue (`on_foot_items`, format 4) with the on-foot materials of FDevIDs, and refuses an ingredient FDevIDs does not know, a consumable, or a recipe without the proof its confidence asks for; `tests/test_odyssey_recipes.py` checks that the rules hold for every recipe, so that a reading in game which contradicts one shows at once. The suits' readings showed that the quantities depend on the step only (1, 1, 1, 2, 2 to class 2; 2, 2, 2, 5, 5 to class 3; 4, 4, 4, 9, 9 to class 4), with the suit's plating, and the weapons' that their ingredients are their maker's (Kinematic, Takada, Manticore); credits are those to class 2 times 1, 3.75 and 7.5.

**Class upgrade goals** (ADR 0027, ADR 0030). A goal raises a suit or a weapon type from one class to a higher one: one of the player's own items, followed by its id (`SuitID`, `SuitModuleID`), or any item of the type. It takes every step's ingredients and credits from the catalogue, against the on-foot materials the player owns (the locker and the backpack, mission items apart); a step the catalogue does not know (the upgrades to class 5) is said, and the goal is then never ready; a step not seen in game is marked as such. When the journal shows the goal's item (its loadout, a purchase, a weapon equipped), or for a goal on a type an item of it shown after the goal was set, at a higher class, the goal starts from that class; at the class aimed at, it is done and removed. Class upgrades are stored in their own table (schema version 2), as the ship goals' table checks their kinds. Their credits are shown, never counted.

**Modifications on foot** (ADR 0027, ADR 0030). The same file holds the modifications an on-foot engineer makes, by the journal symbol of `SuitMods` and `WeaponMods` (`suit_backpackcapacity`, `weapon_stability`). The engineer's screen shows a modification's recipe for the suit or weapon the player brings: a recipe holds for the item types it was read on only, until read on another, and `engineers` lists those seen offering it. A modification's symbol is proven too: the date the player's journal showed it, or the public sources it was read from, by hand, and the date (the journal shows a modification only once made). The script writes them into the catalogue (`on_foot_modifications`), and refuses an item type of the other kind, an engineer FDevIDs does not list among the on-foot ones, or a symbol without its proof. The first readings, on 11 October 2026 at Domino Green's, are three modifications of the Maverick suit and two of the TK Eclipse.

**Modification goals** (ADR 0027, ADR 0030). A goal asks for a modification on a suit or weapon type, or on one of the player's own items (which must not have it yet). It takes the recipe read on that type, its credits, and the unlocked engineers seen offering it; without a recipe on that type, the goal is unknown and never ready, but can be set. When the journal shows the goal's item, or for a goal on a type an item of it shown after the goal was set, with the modification, the goal is done and removed. Modifications are stored in their own table (schema version 3), and counted in the on-foot shopping list and credits with them.

**Engineer unlock goals** (ADR 0027, ADR 0031). A goal names an engineer, ship or on foot, by id, set from their sheet unless the game states them unlocked. What is left to do comes from the sheet and the engineer's state: while not known, the referral (for an on-foot engineer, the referring engineer's task); while not invited, a ship engineer's invitation; then the unlock. A task to give or sell exactly given on-foot materials (`unlock_gives`, `referral_gives` in `data/engineers.toml`) is counted against the on-foot materials held and in the on-foot shopping list; any other step (a rank, a reputation, a commodity, a sale in any mix) is not, and the goal is then never ready. Once `EngineerProgress` states the engineer unlocked, the goal is done and removed. Stored in their own table (schema version 4). The priority over all the goals is a table of its own, `goal_priority` (schema version 5: one rank per goal; the migration ranks the goals stored as they were read, ship goals, class upgrades, modifications, then engineer unlocks). The live view carries them in each part (`unlocks`), their conditions read from the catalogue's sheets; the *Goals* card of each part lists them (`UnlockList.svelte`), and an engineer's sheet has a button to aim at their unlock.

**Activities block, on foot.** The engineering block adds the on-foot materials gained per kind (items, components, data) and those lost at a death.

**Activities block.** The engineering block shows the materials gained per category, used, at their cap, and the goals ready out of all goals (or that the inventory is unknown), then the first three goals in the priority (ADR 0033), each *ready* or what it misses (`missing 2 Arsenic`, `missing 5 units of 2 materials`, *taken by a goal above*, *recipe unknown*, *conditions to meet in game*), and how many other goals. Its alert is the last material at its cap, goal ready or goal done; a ready goal's alert goes when the player removes the goal. It progresses on a change of materials in game, a cap or a goal ready; the game's statement at load is no progress. Material names are the game's own when the journal gave them, else the catalogue's, translated. The *Engineering* and *Blueprints* tabs show the rest (below, Desktop application).

## Prospector alerts

- Threshold per commodity, in percent of the asteroid, editable. Defaults (2026-10-03, to be tuned after the in-game test): platinum 20 %, low temperature diamonds 20 %, painite 25 %, osmium 25 %, palladium 25 %, gold 25 %. Minimum content Low, no minimum reserve, core alerts on, sound on, journal recorder off.
- Minimum content level (High, Medium, Low).
- Optional minimum remaining reserve (`Remaining`).
- A motherlode (core) raises its own alert, whatever the thresholds.
- Duplicate prospecting of the same asteroid (same composition within 60 seconds) does not raise a second alert.

## User interface

**Activities** tab: one block per activity shown. For mining: status (no session, mining in a ring, session ended and why), the last prospector alert, highlighted, until the next asteroid is prospected, then the statistics: active time, refined tons, rate, tons per commodity, asteroids prospected and, once known, cores, limpets, cargo and sales. The statistics of an ended session stay displayed, and its sales are added to them. A **Reset** button ends the running session. Numbers are written as the interface's language writes them.

**Mining** tab (ADR 0040): *where to mine* and *where to sell*, asked of the community sources when the player searches (see Community sources); the mining card gets an *Estimate the cargo* button. The core answers these calls on pywebview's thread, waiting at most 60 seconds for the sources (`MiningHandler.find_hotspots` in `desktop/handlers/mining.py`; where to sell and the estimate are the Trade handler's `find_markets` and `estimate_cargo`, shared by both tabs), as `schemas/mining.schema.json` and `schemas/markets.schema.json` describe.

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
| `edrockmaster.alert.limpets` | text | Limpets on board at which to alert, or empty for none; 5 when missing (ADR 0042) |
| `edrockmaster.sound` | bool | Audible alerts |
| `edrockmaster.record_journal` | bool | Journal recorder |
| `edrockmaster.display.activities` | text | JSON list of the activities shown, at least one (`["mining", "combat"]`) |
| `edrockmaster.display.offered` | text | JSON list of the activities offered when saved (`["mining", "combat", "trade"]`). An activity a later version adds is shown until the player hides it; absent: mining and combat |
| `edrockmaster.display.mode` | text | `last_active` or `stacked`: kept from the plugin's panel; the application shows every activity chosen |
| `edrockmaster.desktop.language` | text | `auto` (the system's), `en` or `fr` |
| `edrockmaster.desktop.journal_folder` | text | The journal folder set by hand; empty: where the game writes it |
| `edrockmaster.desktop.check_updates` | bool | Check for updates, and download them (ADR 0053); true when missing |
| `edrockmaster.desktop.update_channel` | text | `stable` or `beta`; empty: the build's channel |
| `edrockmaster.desktop.phone` | bool | The local server for a phone or a tablet listens (ADR 0055); false when missing |
| `edrockmaster.desktop.phone_port` | text | Its port, from 1024 to 65535; 47800 when missing or invalid |
| `edrockmaster.desktop.phone_key` | text | The link key of its QR code (128 random bits), drawn the first time it is turned on |
| `edrockmaster.desktop.phone_address` | text | The address the player chose for the QR code (ADR 0056); empty, or no longer the computer's: the most likely one |

Values are read one by one: a missing or invalid value falls back to its own default (and is logged), the others are kept.

## Files

Data directory:

- Windows: `%LOCALAPPDATA%\EDRockMaster`, apart from where the installer puts the application (`%LOCALAPPDATA%\EDRockMaster.Companion`), which an uninstall removes
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

One SQLite file for the application's durable **state**, which is neither a setting nor a recording (design decision ADR 0018). Each need has its own tables and its own repository port: the engineering goals (`GoalRepository`, ADR 0017), the answers of the community sources (ADR 0039), the journal files read and the unredeemed vouchers they gave (`PastJournalStore`, schema version 7, ADR 0052). Nothing in it leaves the computer.

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
- A text may name its context after a bar when the game names the same English text otherwise elsewhere: `Wreckage Components|commodity` (*Débris d'épave* on a market, *Composants d'épave* as a material). `tl()` takes the translation with the context, else the one without, and never shows the context.
- `tests/test_translations.py` fails if a text passed to `tl()` has no French translation, if a translation is no longer used, or if placeholders differ.
- Commodity names come from the journal's `*_Localised` fields when present (the game's own language), otherwise from our own names.

## Community sources

What the journal does not tell (hotspots of rings never visited, markets elsewhere) is asked of community tools, on the player's action only (ADR 0038, ADR 0039):

- **Ports** in `application/ports.py`: `GalaxyCatalogue` (rings and their hotspots) and `CommodityMarkets` (markets that buy or sell a commodity). Their answers (`application/community.py`) are what was found, with the time it was read, or why nothing could be had: the source is off, busy or down. A cached answer given because the source failed says why.
- **Adapters** in `infrastructure/sources/`: `spansh.py` (Spansh's body search, the request its site sends) and `ardent.py` (Ardent Insight's nearby importers and exporters). Only domain objects leave them (`domain/mining/hotspots.py`, `domain/commodities.py`). The hotspot commodities are a list of the domain; every source's spelling of their names is mapped onto it.
- **HTTP** (`http.py`): the standard library's client, one request at a time per source, at least one second apart, 15 seconds at most; a `429` or `5xx` makes the source busy for its `Retry-After`, or 30 seconds doubled up to 10 minutes. The `User-Agent` is `EDRockMaster/<full version> (<channel>; <system>) +https://edrm.space`.
- **Cache** (`source.py`): every answer kept as the source gave it in the `source_cache` table of the local database (schema version 6), used while fresh (hotspot searches a day, markets an hour), and when the source fails, however old. It holds nothing about the player; a source's answers are forgotten when it is turned off.
- **Switches**: one setting per source, on by default (`edrockmaster.sources.spansh`, `edrockmaster.sources.ardent`); a source turned off is never asked.
- **Tests**: answers recorded on 11 and 20 October 2026 in `tests/fixtures/sources/` are the contract each adapter reads; the HTTP client and the cache are tested without network.

## Desktop application

Design decision ADR 0020: the core in an application of its own, which reads the journal itself and shows a web interface in a native window. The **journal reader** is in `desktop/`:

- **Folder**: on Windows, the "Saved Games" known folder of the player's profile (wherever it was moved), else `%USERPROFILE%\Saved Games`, then `Frontier Developments\Elite Dangerous`; on Linux, the Proton prefix of the game (Steam app 359320) under the usual Steam folders. `EDROCKMASTER_JOURNAL_DIR` sets it by hand.
- **Files**: `Journal.<start>.<part>.log` (and `JournalBeta.…`), ordered by the start time in their name (two formats, before and since 2022), then by part.
- **Reading**: the first poll reads the current file **from its beginning**, and hands the core every entry: the application reaches the same figures as if it had run since the game started. The live view shows the **current game** only: the sessions ended in a past game are forgotten (`EndedSessionsForgotten`) when a game is loaded (`LoadGame`), and when the file read at start ends with a `Shutdown` older than the application's start; a running session, the unredeemed vouchers and the engineering goals stay. Then each poll reads what was added; an incomplete line waits for the rest; a newer file (a new session, or the next part of a long one) is followed once the current one is finished. A line that is not an entry is logged and skipped. A beta says so in its file name or its game version (`Fileheader`, `LoadGame`), as EDMC read it.
- **Thread**: `JournalWatcher` polls every second on its own thread (`EDRockMaster journal`), as often as EDMC polled a running game.
- **Cargo**: since the game's 3.3, the journal's `Cargo` event lists the ship's cargo only at load; afterwards the list is in `Cargo.json`, next to the journal files. EDMC added it to the event, and mining (cargo) and trade (goods on board) rely on it: the follower adds it too, when `Cargo.json` describes that very event (same timestamp, the ship), so that an older event read at start never gets the current cargo. The game does not always write `Cargo.json` before the line (in a live session, once 22 ms after it): while the file still describes an earlier event, or cannot be read in full, the follower reads it again every 50 ms, for a second at most, then logs it. Otherwise the event is handed on as the game wrote it.
- **Ship locker** (ADR 0027): most `ShipLocker` lines hold the whole locker, but some only point to `ShipLocker.json`, which then holds the change (seen at a fleet carrier, where the locker emptied with bare lines only). The follower adds the file's content to such a line, on the same terms as `Cargo.json`.
- **Parity**: `tests/desktop/test_parity.py` writes every fixture back as journal files, reads them with the reader, and checks that the core gives exactly the notifications of the replay of the fixture, also for a session split in parts written while the reader follows. Reading 20,000 entries at start takes about 0.1 s, 0.3 s with the core.
- **Boundaries**: `lint-imports` (in the CI) checks that `domain/` and `application/` import no adapter, no host and no interface toolkit (`infrastructure`, `desktop`, `ui`, `webview`, `sqlite3`), that presenters and adapters know nothing of the window, and that the domain imports nothing else of the application.

**The application shell** (ADR 0020, ADR 0021):

- `desktop/core.py`, `DesktopCore`: the composition root. The core (companion, local database, goals, catalogue), fed by the journal reader. Every call to the companion and the presenter happens on the **core thread** (`EDRockMaster core`, an `IoWorker` of its own); the journal reader's thread and the interface's calls only queue jobs. After each change, the core pushes the **live view** to the interface.
- `desktop/handlers/` (ADR 0041): the interface's calls, one handler per context: `settings.py` (settings, folders), `layout.py` (the cards' layout), `engineering.py` (the goal form's catalogue, the goals and their priority), `mining.py` (the Mining tab's searches), `trade.py` (the Trade tab, and where to buy and sell for both tabs; a search waits for the sources in `waiting.py`), `phone.py` (the *Phone and tablet* section: answered at once, the local server started or stopped, off the core's thread). A handler checks the request, runs the work on the core thread, and answers or applies the notifications. It reaches the core through a `CoreContext` only (`context.py`: submit to the core or I/O thread, the companion, apply notifications, push the view again, translate, the language, the clock, the logger); it knows neither the window nor the other handlers, which `lint-imports` checks. The tests build a handler on a context that runs each job at once (`tests/desktop/handlers/`). `InterfaceApi` hands each call to its handler: a new tab adds a handler, not methods to the core.
- `desktop/live_view.py`, `desktop/schemas/live_view.schema.json`: the live view, described by a JSON Schema: the activities shown and their blocks (texts from the presenters, already in the player's language), the current activity, the local data notice, the journal read. The tests validate every view pushed against the schema; the interface's TypeScript types are generated from it (`pnpm types`), and the CI checks that they are up to date.
- `desktop/window.py`: pywebview shows the interface, one self-contained HTML file (`desktop/interface/index.html`, built from `web/`, not in git), given as a page: no server, no port. The interface calls the core through `InterfaceApi` (`window.pywebview.api`: `ready`, `reset`, `dismiss_notice`); the core pushes with `run_js`, in ASCII JSON (pywebview on GTK gives WebKit the length of a script in characters, not bytes). pywebview creates `window.pywebview` before adding the core's calls to it: the interface waits for `pywebviewready`.
- Settings in `settings.json` of the data directory (above); a rotating log in `logs/`, which names, at each game loaded, its version, build and expansion (`Game loaded: Elite Dangerous 4.4.1.1 (build r332841/r0), Odyssey`), so that a bug report says which game the journal came from; the language of the system's interface (Windows) or of the locale variables, English otherwise; the presenters' texts translated from `L10n/*.strings`, numbers written as the language writes them.
- **Interface** (`web/`): Svelte 5 and TypeScript, built by Vite into one HTML file; its own texts in `src/locales/*.json`, with a test that every key is translated and used; Vitest and Testing Library; a dark theme from design tokens. Node 22 and pnpm (through corepack) are build tools only.
- **Run it** (development): `cd web && corepack pnpm install && corepack pnpm build`, then `uv run python -m edrockmaster.desktop` (`--debug` opens the web inspector). On Linux, pywebview needs GTK and WebKit2GTK with their Python binding (PyGObject), usually from the system's Python; `EDROCKMASTER_JOURNAL_DIR` points to a journal folder, a recording written back as journal files for instance. `uv run python -m edrockmaster.desktop --demo` (or `EDRockMaster.exe --demo`, `--demo=en`, `--demo=fr`) shows the **demo**: see below.

**Settings** (the *Settings* tab): the settings of the table above (alert thresholds per commodity, minimum content and remaining reserve, cores, sound, journal recordings, activities shown), and the application's own: its **language** (the system's by default; the presenters translate through the core, so a new language applies at once) and its **journal folder** (empty: where the game writes it), used from the next start, since reading another folder at once would count its sessions on top of the current ones. Under the folder, the tab tells the journal file being read, or that the game's journal is awaited; above the tabs, the window says only that no journal folder was found, and the window's title bar shows the application's name and full version (`EDRockMaster 0.6.0-rc.2`, from the build file, ADR 0016); the page repeats neither. The tab also shows where the journal recordings and the log file are (`recordingsFolder`, `logsFolder`), each with a button that opens the folder in the file manager (`open_folder("recordings" | "logs")`; the core refuses any other name, makes the recordings folder if no recording exists yet, and logs a failure; `desktop/folder_opener.py`: the Explorer on Windows, `open` or `xdg-open` elsewhere). In the demo, the recordings stay in its temporary folder, the log in the player's. The folder named by `EDROCKMASTER_JOURNAL_DIR` comes first, then the settings', then the usual one. `settings()` gives the form its content (`settings.schema.json`), `save_settings()` checks it field by field (`desktop/settings_view.py`) and logs what it refuses.

**Updates** (ADR 0053): `velopack.App().run()` is the first thing `python -m edrockmaster.desktop` runs, for Velopack's install, update and uninstall hooks. `application/updates.py` decides: the update channel is the one chosen in *Settings*, else the build's (`stable` for a production, `beta` for a candidate, none for a development build); a newer version of the channel (SemVer, `0.7.0-rc.3 < 0.7.0`) is downloaded, never a lower one, since a lower version may meet a database migrated beyond it; a version ready is forgotten if the channel changes or the check is turned off. `infrastructure/velopack_updates.py` asks Velopack: the GitHub releases of the repository, pre-releases on the beta channel only, or the source named by `EDROCKMASTER_UPDATE_SOURCE` (a folder or an address, for the update test of the Windows build); an application Velopack did not install (a clone, a CI build) has no updates, and its *Settings* tab shows none. A version ready shows above the banner, *Version 0.7.1 is ready*, with *Restart to update*: the window closes, Velopack applies it and starts the application again (`restart_to_update()`); otherwise it is applied when the application quits. The application never restarts by itself.

**Phone and tablet** (ADR 0055): *Settings*, *Phone and tablet* (off by default) lets a phone or a tablet of the home network open the application in its browser. Turned on, `infrastructure/local_server.py` listens on all the computer's IPv4 addresses, port 47800 unless the section changes it (a port another application holds says so); `desktop/phone.py` starts it, stops it, starts it again on another port, and makes the link: the address the player chose while it is still the computer's, else the home network's most likely (ADR 0056: `infrastructure/local_addresses.py` orders the addresses `192.168.0.0/16`, `172.16.0.0/12`, `10.0.0.0/8`, then any other, without link-local and loopback ones, and within a range the one towards the internet first, found by a UDP socket "connected" to a documentation address, nothing sent; a WireGuard VPN's `10.2.0.2` no longer hides the home network), the port, the link key; the section shows its QR code (segno, inline SVG, dark on white), the same link through the other local addresses, each with *Use this address* (`use_phone_address`, kept in the settings), a word about VPNs blocking the local network, and *Use a new link*, which draws another key. The server:

- `GET /?key=…` gives the device a cookie holding the key (`HttpOnly`, `SameSite=Strict`, a year) and sends it to `/`; without a valid cookie, a request gets a page asking to scan the QR code again; a `Host` that is not one of the computer's addresses with the port gets nothing (DNS rebinding);
- `GET /`: the window's own page, `<meta name="edrm-transport" content="http">` added to its head, so that `web/src/lib/bridge.ts` makes the calls over HTTP and follows the events; the page's Content Security Policy allows `connect-src 'self'`;
- `POST /api/<call>` (`{"args": [...]}`): the calls of `InterfaceApi`, the same methods, through `remote_call`; `open_folder` and `restart_to_update` act on the computer itself and stay the window's (`WINDOW_ONLY`), and the interface does not offer them on a device;
- `GET /events`: the live view as server-sent events, the last one at once, then each one the core pushes (`DesktopCore._send` hands it to the window and to the server); a comment every 15 seconds keeps the stream alive. A device that goes away is no error.

The page serves a phone's width: the tabs wrap, the statistics tiles go two by two under 30 rem. Plain HTTP on the local network: the section says that anyone on the network who has the link sees and changes what the window does, to leave it off on a public network, and that Windows may ask once to allow the application in its firewall.

**The engineering view** (ADR 0017): the desktop application's *Engineering* tab, in place of the Tk window ADR 0017 planned. The live view's `engineering` part (`desktop/engineering_view.py`) carries the materials by category and grade with their count and cap, the ship engineers (status, rank; named in the player's language, through `L10n/`, since some carry a title such as *Professor Palin*), the goals with what each misses and the unlocked engineers offering it, in the priority, and the shopping list; `priority` lists every goal's id, ship and on foot, in that order. Each list of goals (ship goals, class upgrades, modifications, engineer unlocks) moves its own goals within that one order, with the arrows of each goal or by dragging its handle onto another goal of the same list (`GoalMove.svelte`, `lib/goal-order.ts`); the interface sends the whole new order (`order_goals`), which the core applies and stores. A goal ready alone but not after the goals above says so, so that the player can raise it. The engineers show in short rows, name and status side by side, the unlocked ones marked, with how many are unlocked. Each engineer, ship or on foot, has a **sheet** ([ADR 0031](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0031-engineer-details.md)): written by hand in `data/engineers.toml` (system and base as the game names them, the engineers referring them, the invitation, the unlock, an on-foot engineer's referral task, and a confidence as for the recipes) and imported into the catalogue (`engineer_details`, format 5), refused when an engineer, a referral or a proof is missing. The sheets never change, so they come with the goal form's catalogue, asked once per language (`engineerSheets`, texts translated through `L10n/`), not with every push of the live view; clicking an engineer (`EngineerList.svelte`) unfolds it, with the system's name copied in one click (the web view's clipboard, else the page's copy command), and a note when the sheet was not checked in game. The goal form asks the core once for the catalogue (`catalogue()`, schema `goal_catalogue.schema.json`): module types, their blueprints with their grades, their experimental effects. The interface adds, changes (rolls, applications), removes and orders goals (`add_goal`, `change_goal`, `remove_goal`, `order_goals`); the core checks a new goal against the catalogue and the domain, logs what it refuses, and stores goals in the local database (ADR 0018). A switch at the top of the tab shows the ship part or the **on-foot part** (ADR 0027): the live view's `engineering.onFoot` carries the on-foot materials held, by kind (the player's own count, what of it is in the backpack, what is held for missions apart), the moves to and from the player's carrier, with the reminder that they no longer count, the suits and weapons seen with their class and modifications (suits named by the application, weapons as the game names them), and the 13 on-foot engineers with their status. The on-foot part also carries the **class upgrade goals** (below), with their own shopping list against the on-foot materials held and the credits they take; the goal form's catalogue carries the suits and weapons with their known upgrades and each one's confidence, and the core takes a class upgrade (`add_goal` with the kind `classUpgrade`: the item's type, the class aimed at, and one of the player's items or the class to start from; `change_goal` changes the class aimed at). It carries the **modification goals** too (`modifications`), and the catalogue the modifications with who offers them and their recipes (`onFootModifications`); the core takes a modification (`add_goal` with the kind `modification`: the item's type, the modification, and one of the player's items if chosen). The *On foot* part lists the class upgrades (in the priority) with what each misses, its credits, whether it follows one of the player's items, and a note when a step is unknown or not checked in game; the class aimed at is changed there and a goal removed; the on-foot shopping list follows, with the credits of all of them. Its form (`ClassUpgradeForm.svelte`) offers the player's own suits and weapons below class 5 that the catalogue knows, then any type, from a class the player says. The same *Goals* card lists the modifications (in the priority) with what each misses, its credits, the unlocked engineers offering it, and a note when its recipe is not known on that type or not checked in game; their form (`ModificationForm.svelte`) offers the player's own suits and weapons, then any type, and the modifications of its kind the item does not have yet, those without a known recipe marked so. The on-foot shopping list and credits count both kinds of goals.

**The commander's situation** (ADR 0023): `domain/situation/` reads `Commander`, `LoadGame`, `Location`, the jumps and supercruise, `Docked`, `Undocked`, `Loadout`, `ShipyardSwap`, `SetUserShipName`, `Embark`, `Disembark` and the wing events, into the commander's name, the ship (its type in the game's language, the player's name and registration), on foot or not, the system, the station, the game mode with the private group's name, and the wing members. The game names a ship type in its language only in `LoadGame` and `ShipyardSwap`; until it does, the type shows FDevIDs' English name (`domain/situation/ship_names.json`, written by `scripts/import_ship_names.py` from `shipyard.csv` at the commit the engineering catalogue pins), never the bare symbol. A game loaded on foot names the suit worn where a ship would be: the situation is then on foot, its ship given by the next `Loadout`. `Shutdown` keeps the last situation and says the game is closed. It is in memory only: never stored, never uploaded; the application shows it in a banner, through the live view's `situation`. Wherever the interface shows a system (this banner, an engineer's sheet, the rings and markets of the *Mining* tab), its name is copied in one click, with the same gesture (`CopySystem.svelte`): the name in pale yellow, with a small copy mark raised like an exponent, *Click to copy* on hover, *Copied* for a moment. Wing members are other players: the recording sanitiser names them `Wingmate 1`, `Wingmate 2`…

**The current route** (ADR 0043): `domain/situation/route.py` follows the route plotted on the galaxy map. `NavRoute` says a route was plotted; the journal reader adds its systems from `NavRoute.json` when the file carries the line's timestamp (two routes plotted 20 seconds apart leave the second in the file: the first line, read again at start, gets no list). The first system is the commander's, the last the destination; the file does not change along the route. Each jump writes `StartJump` (the system aimed at and its star), then during the jump `FSDTarget` (the following jump, its star, the jumps left), then `FSDJump` on arrival (fuel left and used), then `FuelScoop` when scooping; the game writes `NavRouteClear` during the last jump. Only an arrival (`FSDJump`, `CarrierJump`, `Location`) in a system of the list moves the route on; one off the list says *Off the route* until the game aims at a jump again, one back in a system of the list puts the route back there. A jump that ends elsewhere than it aimed is written to the application's log, and one back where it left is flagged as a possible Thargoid hyperdiction (which, read on the web, drops the ship back in the system it left; never seen in the player's journals). Fuel can be scooped at O, B, A, F, G, K and M stars, giants included; white dwarfs, neutron stars and black holes are dangerous on arrival. Two alerts, once per jump aimed at, with the alerts' sound when sound is on and the line is less than a minute old (so that reading the journal from its start sounds nothing): a dangerous star next, and fuel tight, when the jumps to the next star where fuel can be scooped need more than the fuel left, on the most one jump of the route used. The banner shows the route in a column on the right (`route.ts`): destination and jumps left, the next jump with its star in words and *fuel scoopable* or not (*carburant récupérable* in French, never *écopable*), where fuel can next be scooped, and the alert. Nothing is stored or sent.

**The demo** (`--demo`, `desktop/demo.py`): the application reads a sample journal instead of the player's, for screenshots and the documentation, or to discover it without playing. `scripts/make_demo_journal.py` writes it (`desktop/demo_journal.jsonl`, checked by a test to be up to date) from published fixtures: a mining session in a resource extraction site with its combat bonds, under the fictional **Commander Jameson** in Open play, in the *Rock Hound*, with the materials, engineers and collected materials of the engineering fixture; it stops while the commander is still mining. At start, its timestamps are moved so that it ends now, and so are the community goals' expiries: the mining, combat and engineering sessions are running, and the community goal still runs. The demo is in the system's language, or the one it names (`--demo=en`, `--demo=fr`); the journal was recorded with the game in French, so for a demo in English the names the game writes in its language and the application shows as they are (commodities, asteroid content, community goal) are replaced by the game's names in English, the game's names of the materials are left out so that the catalogue names them, and each screenshot is in one language only. Its settings and goals live in a temporary folder deleted at exit, so the player's own are neither read nor changed; the technical log stays the usual one and says "Demo mode" and its language. `EDROCKMASTER_JOURNAL_DIR` is ignored.

**The blueprints tab** (ADR 0017): the game data to browse, without going through a goal. A search (module, blueprint or effect name, or a material they take: what a material is for; case and accents ignored) and a module type filter; each blueprint shows one grade at a time (the highest first): its ingredients against the inventory, held or missing, how many rolls the inventory allows, and the engineers offering that grade, unlocked first with their rank; each module's experimental effects show their ingredients and how many applications are possible. A button adds the grade or the effect to the goals (`add_goal`, one roll). The catalogue call (`catalogue()`) carries, for each blueprint, one recipe per grade (ingredients, engineers' ids) and, for each effect, its ingredients, named in the core's language: the tab asks for it again when the language changes. The search and the arithmetic are in `web/src/lib/blueprints.ts`.

**Packaging for Windows** (ADR 0053): the application is installed and updated with **Velopack**, from the releases of the GitHub repository; nothing is signed yet, so Windows SmartScreen warns once, at the first install.

- `.github/workflows/windows.yml` runs on the **GitHub mirror only** (`windows-latest`; Gitea reads `.gitea/workflows/` and ignores it): it builds the interface, runs the Python tests on Windows, decides the release plan, packages, **starts the packaged application on a recorded journal**, then in demo mode (its log must say that the interface is ready and the journal read, with no error), runs the **update test**, and keeps the portable zip 14 days.
- **The update test**, on every run: the build is packed twice with `vpk`, as `1.0.0` and `1.0.1`, into a local feed, on the channel the build follows (`beta` for a candidate, `stable` for a production, a `test` channel otherwise); the `1.0.0` installer is run silently, the installed application started with `EDROCKMASTER_UPDATE_SOURCE` pointing at the feed, until its log says `1.0.1` is downloaded; its window is then closed, as the player would, and Velopack must have installed `1.0.1` (`current\sq.version`); the uninstall must leave a file planted in `%LOCALAPPDATA%\EDRockMaster`.
- Its result gates merging on Gitea too ([ADR 0034](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0034-windows-build-gates-merging.md)): the `windows` job of the Gitea CI runs `scripts/windows_build_gate.py`, which waits for the run of the same commit on the mirror and takes its result (20 minutes at most). A commit that changed only what the Windows workflow ignores (its `paths-ignore`, read from the workflow) takes the run of its nearest ancestor that has one; a branch that changed only such files needs none; a tag prefers its own run. The GitHub API is read anonymously, or with the read-only `GH_ACTIONS_READ_TOKEN` secret for the rate limit. The job is a required check of `main`.
- `scripts/package_desktop.py` (on Windows): the build file (ADR 0016), the icon (`scripts/make_icons.py`, a placeholder rock until a designed icon), PyInstaller (`packaging/windows/EDRockMaster.spec`: one folder, no console, no Tk), and the folder as a zip, for a quick check of a development build.
- **A tag**: `scripts/release_plan.py` gives its update channels, `beta` for a candidate, `stable` and `beta` for a production. For each, `vpk download github` fetches the channel's latest release (for the delta), then `vpk pack` makes the installer `EDRockMaster.Companion-<channel>-Setup.exe`, the portable zip, the full and delta packages and the feed `releases.<channel>.json` (pack id `EDRockMaster.Companion`: Velopack's folder is removed at uninstall, so it is not the data folder). A second job, `release`, leaves them on GitHub as a **draft release** (`vpk upload github --merge`, one release for both channels).
- The **release** job of the Gitea CI, once the Windows build passed: `scripts/github_release.py fetch` downloads the draft's files and adds `SHA256SUMS`; the Gitea release gets them with the notes; `scripts/github_release.py publish` gives the GitHub release its notes and publishes it, as a pre-release for a candidate. Updates read published releases only.
- `scripts/fixture_to_journal.py` writes a fixture back as a journal file, to try the application by hand.

## Testing

- **Domain and application: test-driven**, with plain `pytest`.
- **Fixtures**: real journal excerpts (`tests/fixtures/*.jsonl`), recorded with the recorder.
- **Replay tests**: a whole recorded session is replayed through `Companion` and the presenters, and the final statistics, checked by hand against the raw journal, are asserted; the parity tests read the same fixtures back through the journal reader.
- **Desktop**: the core with a fake push, the window with a stand-in for pywebview, the views validated against their JSON Schemas; checked in a real window (GTK/WebKit on Linux, WebView2 in the Windows runner's smoke test).
- **Interface**: Vitest and Testing Library, its logic in `web/src/lib/` tested alone.
- CI: `ruff`, `mypy --strict`, `lint-imports`, `pytest` with coverage on `domain/`, `application/`, `ui/` and `desktop/`; the interface's lint, type check, tests and build.

