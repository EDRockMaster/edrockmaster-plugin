# Privacy policy — EDRockMaster Companion

*English · [Français](privacy.fr.md)*

Last updated: 9 October 2026. Applies to the EDRockMaster Companion desktop application and to the EDRockMaster plugin for EDMarketConnector, published by Nexagone.

## In short

EDRockMaster reads the journal that Elite Dangerous writes on your computer, computes your session statistics **on your computer**, and **sends nothing anywhere**. There is no account, no analytics, no advertising, no tracking.

## What the application reads

Elite Dangerous writes a journal of your play in your *Saved Games* folder. EDRockMaster reads it, without changing it, to show your mining, combat, trade and engineering sessions. This journal contains, among other things:

- your commander's name, your ship (type, the name and registration you gave it), your location (system, station) and your game mode (open, solo, private group and its name);
- what you did: prospected asteroids, refined commodities, purchases and sales, kills and bounties, materials collected, engineers' work;
- the names of **other players** in some events: members of your wing, targets of bounties.

The application does nothing else on your computer: it reads no other file, and uses no camera, microphone or location service.

## What the application keeps, and where

Everything stays on your computer, in `%LOCALAPPDATA%\EDRockMaster`:

- **your settings** (`settings.json`);
- **your engineering goals** (`edrockmaster.sqlite3`): the blueprints and effects you aim at, and how many rolls;
- **a technical log** (`logs\`): when the application starts and stops, which journal file it reads, errors; it holds no statistics of your play;
- **journal recordings** (`recordings\`), **only if you turn them on** (off by default): copies of journal entries, for you to send with a bug report if you wish.

Your session statistics and your situation (commander, ship, location, wing) are **only in memory**, rebuilt from the journal each time the application starts, and never written anywhere.

## What the application sends

**Nothing.** The application makes no network connection: no analytics, no crash reports, no update check (the Microsoft Store handles updates).

A later version will offer an **optional** link with EDRockMaster's online services (history of your sessions, shared statistics). It will be off unless you turn it on, will ask for your consent first, and this policy will be updated before that version is published, to say exactly what is sent, why, and for how long it is kept.

## Third parties

- **Microsoft Store**: installs and updates the application, under [Microsoft's privacy statement](https://privacy.microsoft.com/privacystatement). EDRockMaster receives no personal data from it.
- **Microsoft Edge WebView2**: the component of Windows that draws the application's window; it runs on your computer.
- **Game data**: the list of materials, blueprints and engineers comes from community data (EDCD) shipped inside the application; nothing is downloaded.

## Your choices

- **See or delete your data**: everything is in `%LOCALAPPDATA%\EDRockMaster`; delete the folder to erase it. Uninstalling the application keeps it, so that your goals survive a reinstall; delete it by hand if you wish.
- **Stop the reading**: close the application.

## Children

The application is meant for players of Elite Dangerous, rated PEGI 7 / ESRB Teen; it collects nothing from anyone.

## Contact

Questions about this policy: [contact@edrm.space](mailto:contact@edrm.space). Source code: [github.com/EDRockMaster/edrockmaster-plugin](https://github.com/EDRockMaster/edrockmaster-plugin).

## Changes

Any change to this policy is published here, with its date, before the version of the application it concerns.

*Elite Dangerous is a trademark of Frontier Developments plc. EDRockMaster is not endorsed by or affiliated with Frontier Developments.*
