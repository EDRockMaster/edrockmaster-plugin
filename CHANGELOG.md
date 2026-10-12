# Changelog

*English · [Français](CHANGELOG.fr.md)*

All notable changes to EDRockMaster Companion, the desktop application (until 0.3.0, the EDMC plugin). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **The Mining tab** (design decisions ADR 0039 and ADR 0040). *Where to mine*: the rings with hotspots of a commodity around a system (your current one by default), nearest first, with their type, reserve, other hotspots, distance and how old the data is, filtered by hotspot count, reserve level and distance. *Where to sell*: the markets that buy the commodity around a system or a ring of the list, best price first, with demand, distance, landing pad and how old the price is; by default only the pads your ship can use, fleet carriers left out. Rings come from **Spansh**, markets from **Ardent Insight**, two community tools fed by EDDN, asked only when you search; their answers are kept a while (a day for rings, an hour for markets), and shown, with their age, when the source does not answer.
- **Estimate the cargo**: a button under the mining card prices the cargo mined and not sold yet at the best market around your current system, commodity by commodity.
- **Copy a system's name in one click**, wherever one is shown: your current system in the situation banner, an engineer's sheet, the rings and markets of the Mining tab. The same gesture everywhere: click the name, in pale yellow with a small copy mark, *Copied* shows for a moment; paste it in the galaxy map or another tool.
- The application's log names the **game version** at each game loaded (version, build, Odyssey or Horizons, beta), so that a bug report says which game it came from.
- **Combat by faction**: the combat card shows kills and credits against each faction you fought (the three with most kills, then the others together), handy in a conflict zone.
- **Crimes by kind** in the combat card: *Reckless weapons discharge: 1, Assault: 2*, named in your language.
- **Limpets on board** in the mining card, and an **alert before they run out**: one sound and *5 limpets left* when they fall to 5 during a mining session, once, not at every launch. The number is set in *Settings* (empty for no alert).
- **The current route**, on the right of the situation banner, while a route is plotted in the game: destination and jumps left, the next jump with its star in words and whether fuel can be scooped there, and where fuel can next be scooped. An **alert** before a dangerous star (white dwarf, neutron star, black hole), and when the fuel may not reach the next scoopable star (design decision ADR 0043).
- **Community sources** in *Settings*: Spansh and Ardent Insight can each be turned off; the privacy policy says what they receive.

### Fixed

- Goods handed to an engineer to unlock them (50 t of Bromellite for Bill Turner) now leave the cargo of the trade card, which says so: *Handed to Bill Turner: Bromellite, 50 t*.
- *Settings* no longer drops changes not saved when you open another tab: it asks whether to save them, drop them or keep editing.

## [0.5.0] - 2026-10-11

The first published version of **EDRockMaster Companion**, the desktop application, which replaces the EDMC plugin.

### Added

- **The desktop application** (design decisions ADR 0020 and ADR 0021): EDRockMaster in a window of its own, without EDMC. It reads the game journal itself, from the beginning of the current file, so that it reaches the same figures as if it had run since the game started, and follows the game as it writes. Its full version shows beside its name (`0.5.0`, `0.5.0-rc.1` for a candidate). Tabs *Activities*, *Engineering*, *Blueprints* and *Settings*; English and French, in the system's language or the one chosen; nothing listens on the network and nothing is sent anywhere. Distributed through the Microsoft Store (ADR 0022), and as a portable zip for testers.
- **The commander's situation** (ADR 0023): a banner with the commander, the ship (type, name and registration), the system and the station, the game mode with the private group's name, and the wing. A ship type the journal has not named yet shows its English name (from EDCD/FDevIDs) until the game gives its own, and a game loaded on foot shows the commander on foot.
- **Trade** (ADR 0014): a new activity. A trade session starts with the first purchase. Its profit is the game's own, `(SellPrice - AvgPricePaid) × Count`, even for goods bought before the journal file began; its rates count the **flight time** only, from undocking to the next docking, when a trade follows. Its block shows the profit, the profit per hour, the tons sold, the cost of the cargo bought, and one line per route (commodity, market of purchase, market of sale). On a real session of three round trips between Amano Terminal and Verne Venture: 164,316,218 CR in 1 h 21 min 50 s of flight, 120.5 M CR/h. Goods sold that were not bought are kept apart: **refined commodities** (their profit stays with mining) and **other goods**; bought goods ejected or lost with the ship are a loss.
- **Fleet carrier transfers** (ADR 0019): deposits and withdrawals per commodity, with the number of transfers, so that a deposit the game did not take (a known game bug) shows at once. A transfer starts a trade session and counts its flight; goods deposited are not counted as lost if the ship is destroyed afterwards.
- **Engineering** (ADR 0017): a new activity. It follows the inventory of ship materials, stated by the game at load, and each change: collected, rewarded, discarded, traded, synthesised, given to a broker, an engineer or research, spent on a roll. Its block shows the materials gained per category, used, and those that reached their cap, with an alert, since what is collected beyond the cap is lost, how many goals are ready, and the first three goals with what each misses (`missing 2 Arsenic`, *taken by a goal above*), then how many others. The *Engineering* tab shows the inventory by category and grade with each cap, the engineers (status and rank, foldable), the **blueprint goals** (a blueprint and grade for a module type, with a number of rolls, or an experimental effect) with what each misses and the unlocked engineers offering it, and the shopping list of every goal; goals are added, changed and removed there, and a roll in game counts one down. On a real session: 39 materials collected, five rolls of *High charge capacity* on a power distributor, the ingredients of each roll as in the catalogue.
- **The Blueprints tab**: every module's blueprints, grade by grade, against the inventory (held, missing, possible rolls), with the engineers offering each grade; experimental effects with their ingredients; a search by module, blueprint, effect or material (what a material is for); each grade or effect can be added to the goals.
- **Engineering catalogue** (ADR 0017): the game data of ship engineering (137 materials with their grade and cap, 81 blueprints, 86 experimental effects, 44 module types, 25 engineers), imported from EDCD/FDevIDs and EDCD/coriolis-data, with the names translated into French; material names in French are the game's own. This data belongs to Frontier Developments: the new `NOTICE` file says so.
- **Settings tab**: alert thresholds per commodity, minimum content and remaining reserve, cores, sound, journal recordings, activities shown, language, and the journal folder when the game's is not where it is usually found, with the journal file being read; buttons open the folders of the journal recordings and of the logs, to send them with a bug report.
- **Local database** (ADR 0018): `edrockmaster.sqlite3` in the data directory, for what must be kept across restarts, starting with the engineering goals. Its schema is migrated at start, after a copy of the file. A file the application cannot read, because it is damaged or written by a newer version, is kept aside as `edrockmaster.sqlite3.unreadable-<date>`, a new one is created, and the interface says so until dismissed.
- **Demo mode** (`--demo`, `--demo=en`, `--demo=fr`): a sample journal under the fictional Commander Jameson, for screenshots or to discover the application without playing; the player's settings and goals are not touched.
- The recording sanitiser keeps purchases, cargo transfers, the materials and engineers events, and reduces a completed mission to its materials reward.
- **Engineering on foot** (ADR 0027, ADR 0029). The *Engineering* tab gets an *On foot* part: the on-foot materials held (items, components, data, consumables), from the ship locker and the backpack as the game states them, with what is in the backpack and what is held for missions apart; the suits and weapons seen, with their class; the 13 on-foot engineers and their status. The *Activities* block counts, in one tile, the on-foot materials gained and those lost at a death (`+140, 5 lost`); their kinds are in the *On foot* part. Stolen goods count as the player's own. On a real evening, the inventory after each return aboard equals the game's.
- **Your fleet carrier**: on-foot materials moved between the ship locker and your own carrier write no event in the game's journal; the *On foot* part shows each move, and reminds that moved materials no longer count. What the carrier holds will come from Frontier through EDRockMaster's services (ADR 0028).
- **Class upgrade goals of suits and weapons** (ADR 0027, ADR 0030). In the *On foot* part, choose one of your suits or weapons (or any of a type, from the class you say) and the class to reach: the goal adds up the materials and credits of every step, against your ship locker and backpack, with its own shopping list. When the game shows the item at a higher class, the goal moves on, and goes once reached. The recipes of the 3 suits and 11 weapons were read in game, on 11 October 2026, up to class 4: those not seen on screen but deduced from what was are marked *not checked in game*, and the upgrades to class 5, not seen yet, are said to be unknown.
- **Modification goals of suits and weapons** (ADR 0027, ADR 0030). In the *Goals* card of the *On foot* part, choose one of your suits or weapons (or any of a type) and a modification it does not have yet: the goal shows what it takes against your ship locker and backpack, its credits and the unlocked engineers offering it, and goes once the game shows the item with the modification. The first recipes were read in game at Domino Green's, on 11 October 2026: three modifications of the Maverick suit and two of the TK Eclipse. A recipe is known only on the suit or weapon it was read on; elsewhere, the goal can be set and says that its recipe is not known yet.
- **Engineer sheets** (ADR 0031). Click an engineer, ship or on foot, to see their system and base, who makes them known, what gets you invited and what unlocks them, and, on foot, the task that refers the next ones. A click on the system copies its name, ready to paste into the galaxy map. The 38 sheets were written from public sources on 11 October 2026, marked *not checked in game* until read in game.
- **Engineer unlock goals** (ADR 0027, ADR 0031). From an engineer's sheet, aim at unlocking them: the *Goals* card of their part says what is left to do (referral, invitation, unlock). The on-foot materials a task asks you to give or sell (5 Push for Domino Green's referral, 5 Opinion Polls to unlock Kit Fowler…) are counted against your ship locker and backpack and join the on-foot shopping list; ranks, reputations and commodities are not, and are said so. The goal goes once the game states the engineer unlocked.
- **A priority over the engineering goals** (ADR 0033). The goals, ship and on foot, come in one order you choose: arrows on each goal, or drag its handle onto another goal of the same list; a new goal comes last. The materials held go to the goals in that order, so two goals after the same materials are not both ready when only one can be done: a goal is ready when nothing is missing once the goals above it have taken their share, and one that would be ready on its own says that a goal above takes its materials. The shopping list counts every goal, whatever their order.
- **Community goals** (ADR 0032): a card of their own in *Activities*, shown while you have joined a goal, whatever it is about (combat, trade, mining, exploration). One tile per goal: its full title and system, your contribution, your percentile band, the tier reached out of the top tier (`tier 3 of 5`), and the time left before it ends, counted down, or *Complete: reward to collect*. A goal goes once its reward is collected or it is discarded. In the demo, the goal ends as long after now as after the recording.
- **Cards you arrange**: the activities and the parts of the *Engineering* tab are cards, one below the other, each as wide as the window. Drag a card by its handle to move it (or use its arrows), and fold the ones you do not need; their order and those folded are kept from one session to the next. An activity's statistics show as tiles side by side, and the inventory shows each material category on its own row, its grades side by side, with each grade's cap at the top.

### Fixed

- In French, void opals are named as in the game: *Opales du vide*.

### Removed

- **The EDMC plugin** (ADR 0024): retired before it had players. Its last release, 0.2.2, stays on GitHub; it gets no further release. Its settings are not imported: the application has its own.

## [0.4.0] - not released

Candidates only, `0.4.0-rc.1` and `0.4.0-rc.2` (2026-10-10), kept as a demonstration; their content is part of 0.5.0.

## [0.3.0] - not released

Candidates only, `0.3.0-rc.1` to `0.3.0-rc.3` (2026-10-05 to 2026-10-06), for acceptance by the testers: the EDMC plugin was retired before this version reached players (ADR 0024).

### Changed

- **Bounty hunting becomes combat**, measured by site (design decision ADR 0013, in the project's architecture repository). A **segment** is one stay on a combat site (conflict zone, resource extraction site, navigation beacon), from the arrival to the departure; it opens with the first reward and counts the search from the arrival. The panel shows the current site and, for each site type, the kills and credits per hour, weighted by time. A site left without any reward is not counted.
- Time in normal space elsewhere no longer counts as combat: in a real session, 52 minutes of mining after two conflict zones showed 1 h 44 min and 664,594 CR/h; the zones alone are 49 min 19 s and 1,403,083 CR/h.
- The panel switches to combat only when it progresses (a reward, a segment that starts or ends, a crime): leaving a ring after mining no longer brings back a combat session ended hours before.

### Added

- **Display settings** (preferences, *Display*; design decision ADR 0013): the activities the panel shows, and the mode, either the **last active activity** (as before, the default) or **all of them, stacked**, each with its own *Reset* button. A hidden activity is still followed, and is up to date when shown again.
- **Miscellaneous** kills: a kill outside any combat site (a pirate while mining, near a station) counts in kills, credits and vouchers, but in no rate. Mining time is never combat time, and mining never ends a combat session.
- **Fines** and **bounties on you** during a combat session, never deducted from what was earned.
- Combat site types confirmed in game (4.4.1.1): conflict zones (low, medium, high), resource extraction sites (low, normal, high, hazardous), navigation beacon.
- The recording sanitiser keeps arrivals on sites and crimes, drops the reputation from jumps and crime victims, and replaces fleet carriers (name, callsign, id).
- **Ground conflict zones** (Odyssey, design decision ADR 0015): the Frontline Solutions dropship opens a segment, its retreat closes it, and the panel shows the settlement. On a real evening at Redonesses, two ground zones gave 35 kills at 68.1 kills/h and 1,309,320 CR/h.
- **Conflict zones the journal does not name**: a combat bond only exists in a conflict zone, so a bond outside any site opens a segment from the arrival, of unknown intensity by ship. On that same evening, 45 of 77 kills would otherwise have had no rate.
- The recording sanitiser keeps the moves on foot (settlements, dropship, disembark, embark) and drops the commander's killers.
- **Build identity** (design decision ADR 0016): each zip says which build it is, for example `0.3.0-rc.3`, in the EDMC log at start-up, at the bottom of the preferences tab, and in the name of journal recordings. CI builds are `0.3.0-dev+<commit>`.

### Fixed

- The preferences tab did not show in EDMC since 0.3.0-rc.2: the display settings mixed two Tk layouts in one frame, which EDMC's frames refuse.

## [0.2.2] - 2026-10-03

### Fixed

- Bounty hunting rate: active time is now the **time on site** (in normal space away from stations, from the arrival on the site of the first reward). Searching for targets counts; travelling and docking do not. A 20-minute search between two bounties used to be left out, which showed 36 M CR/h instead of 10 M CR/h in a real session.
- Bounties are now checked against a real session (game 4.4.1.1): kills, rewards paid by several factions, and redemption per faction match the game.

## [0.2.1] - 2026-10-03

### Changed

- Bounty hunting panel: when only combat bonds are earned, the status reads **Conflict zone** and the empty bounty line is left out.
- Checked against a real conflict zone session (game 4.4.1.1): combat bonds, active time, redemption and community goal figures match the game. Bounties themselves remain to be checked in game.

## [0.2.0] - 2026-10-03

### Added

- **Bounty hunting** (design decision ADR 0011, in the project's architecture repository): a hunting session starts with the first bounty or combat bond and ends on death, game exit or **Reset**; docking and jumps do not end it. Statistics: active time (pauses over 15 minutes left out), kills and shared kills, bounties, combat bonds, credits per hour. Unredeemed vouchers, which are lost on death. Community goals: contribution, percentile band, tier reached.
- The panel shows the activity in progress, mining or bounty hunting; **Reset** acts on it.

### Known limitations

- Unredeemed vouchers are known only from the moment EDMC started: the game journal does not restate older ones.
- The bounty hunting counter has not been checked against a real hunting session yet: please enable the journal recorder while hunting and report any wrong figure.

## [0.1.0] - 2026-10-03

First version, for the first in-game test. The plugin works on its own, without any server.

### Added

- **Prospector alerts**: a threshold per commodity, in percent of the asteroid. Defaults: platinum and low temperature diamonds 20 %, painite, osmium, palladium and gold 25 %. Also a minimum content level, an optional minimum remaining reserve, an alert on cores (motherlodes), and a sound. An asteroid prospected twice within 60 seconds raises only one alert.
- **Mining sessions**: a session starts with the first mining activity and ends on supercruise, jump, docking, game exit or the **Reset** button. Active time leaves out pauses longer than 10 minutes. Statistics: tons per commodity, tons per hour, refinements, asteroids prospected, cores found and cracked, limpets launched, cargo. Sales of the mined tons after the session are added to it (tons and credits).
- **Panel** in EDMC's main window and **preferences tab** in EDMC's settings.
- **English and French**, following EDMC's language, without restart.
- **Journal recorder** (off by default): keeps a copy of the journal events in JSONL files, to build test data and report bugs.
- EDMC started while the game is already running: the current ring is known.

### Known limitations

- No link with EDRockMaster services yet (sign-in, uploads): planned for the next version.
- No estimated value of the cargo: it needs the server's prices.
- Not checked yet: EDMC's dark theme, the alert sound on Windows.

[0.5.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.5.0
[0.2.2]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2
[0.2.1]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.1
[0.2.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.1.0
