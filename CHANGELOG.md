# Changelog

*English · [Français](CHANGELOG.fr.md)*

All notable changes to the EDRockMaster plugin. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Trade** (design decision ADR 0014): a new activity, with its own block on the panel. A trade session starts with the first purchase. Its profit is the game's own, `(SellPrice - AvgPricePaid) × Count`, even for goods bought before EDMC started; its rates count the **flight time** only, from undocking to the next docking, when a trade follows. The panel shows the profit, the profit per hour, the tons sold, the cost of the cargo bought, and one line per route (commodity, market of purchase, market of sale). On a real session of three round trips between Amano Terminal and Verne Venture: 164,316,218 CR in 1 h 21 min 50 s of flight, 120.5 M CR/h.
- Goods sold that were not bought are kept apart: **refined commodities** (their profit stays with mining) and **other goods**. Bought goods ejected or lost with the ship are a loss.
- Trade is shown by default, even to players who had already chosen the activities shown: the plugin now remembers which activities the preferences tab offered.
- The recording sanitiser keeps purchases.

## [0.3.0] - 2026-10-06

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

[0.3.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.3.0
[0.2.2]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2
[0.2.1]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.1
[0.2.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.1.0
