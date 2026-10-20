# Privacy policy — EDRockMaster Companion

*English · [Français](privacy.fr.md)*

Last updated: 20 October 2026. Applies to the EDRockMaster Companion desktop application and to the EDRockMaster plugin for EDMarketConnector, published by DamScan, a personal and non-commercial project.

## In short

EDRockMaster reads the journal that Elite Dangerous writes on your computer, computes your session statistics **on your computer**, and **sends nothing to us**: EDRockMaster has no server. There is no account, no analytics, no advertising, no tracking. Only when you search the *Mining* or *Trade* tab, or estimate your cargo, does it ask community tools on the internet for what the journal does not tell (below).

## What the application reads

Elite Dangerous writes a journal of your play in your *Saved Games* folder. EDRockMaster reads it, without changing it, to show your mining, combat, trade and engineering sessions. This journal contains, among other things:

- your commander's name, your ship (type, the name and registration you gave it), your location (system, station) and your game mode (open, solo, private group and its name);
- what you did: prospected asteroids, refined commodities, purchases and sales, kills and bounties, materials collected, engineers' work;
- the names of **other players** in some events: members of your wing, targets of bounties.

Beside the journal, it reads the files the game writes with it: the cargo, the ship locker, the route plotted, and the last commodity market you opened (its prices).

The application does nothing else on your computer: it reads no other file, and uses no camera, microphone or location service.

## What the application keeps, and where

Everything stays on your computer, in `%LOCALAPPDATA%\EDRockMaster`:

- **your settings** (`settings.json`), with the link key of the *Phone and tablet* QR code once you have turned it on;
- **your engineering goals** (`edrockmaster.sqlite3`): the blueprints and effects you aim at, and how many rolls;
- **a technical log** (`logs\`): when the application starts and stops, which journal file it reads, errors; it holds no statistics of your play;
- **your unredeemed vouchers** (in `edrockmaster.sqlite3`): the bounties and combat bonds you hold, per faction and commander (by their Frontier id), and the names of the journal files already read for them, so that each is read only once;
- **answers of the community sources** (in `edrockmaster.sqlite3`): what Spansh and Ardent Insight published in answer to your searches (rings, markets, prices, trade routes), reused for a while instead of asking again; nothing about you (a trade route is kept under a digest of its request, without your credits);
- **journal recordings** (`recordings\`), **only if you turn them on** (off by default): copies of journal entries, for you to send with a bug report if you wish.

Apart from your unredeemed vouchers, your session statistics and your situation (commander, ship, location, wing) are **only in memory**, rebuilt from the journal each time the application starts, and never written anywhere.

## What the application sends

**Nothing to us**: EDRockMaster has no server, no analytics, no crash reports.

**An update check, to GitHub.** Installed with its installer, the application looks for a newer version at start, then once a day, in the public releases of its repository on GitHub (`github.com`, `api.github.com`), and downloads it from there. The requests carry nothing of yours: no identifier, no statistics; GitHub sees your computer's IP address and the time, as any web site does. The *beta* channel also reads the release candidates. Turned off in *Settings*, *Updates*: the application then asks nothing.

**To your phone or tablet, only if you turn it on.** *Settings*, *Phone and tablet* (off by default) lets a phone or a tablet of your home network open the application in its browser, by its QR code. The application then listens on your local network, on one port (47800 by default), and serves the devices that have the link everything the window shows, and lets them change it; nothing goes through the internet, and nothing reaches us. The link holds a random key; anyone on your network who has it sees and changes what the window does. It travels unencrypted on your network (no HTTPS for a local address): leave it off on a public network. Turned off, the application listens on nothing; *Use a new link* shuts out the devices already connected.

**Your searches, to community tools, and only when you make them.** The *Mining* and *Trade* tabs and the *Estimate the cargo* button ask two independent community tools for what the journal does not tell:

- **Spansh** (`spansh.co.uk`), for the rings and their hotspots around a system: it receives the commodity, the system's name and your filters; for a trade route (*Trade* tab), the starting system and station, your ship's cargo capacity, **the credits entered in the form** (filled with your credits at the game's load, which you can change before asking) and your filters;
- **Ardent Insight** (`ardent-insight.com`), for the markets that buy or sell a commodity: it receives the commodity, the system's name, the distance and the least demand or stock you set (the *Trade* tab fills it with your ship's cargo capacity); for an estimate, one request per commodity of your mining cargo (mining card) or of all your cargo (*Trade* tab), around your current system. For the galaxy's prices of a commodity, or to compare the station's market with them (*Trade* tab), it receives nothing of yours: one request gives every commodity's prices, asked at most once a day unless you refresh.

Nothing else is sent: not your commander's name, nor your statistics. As with any web site, they see your computer's IP address and the time. They are hobby projects run by other players, under no privacy policy of theirs that we know of. Each can be turned off in *Settings*, *Community sources*; turned off, it is never asked, and what it answered is forgotten.

## Third parties

- **GitHub**: publishes the application and its updates, under [GitHub's privacy statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement); asked by the update check, as said above.
- **Microsoft Edge WebView2**: the component of Windows that draws the application's window; it runs on your computer.
- **Game data**: the list of materials, blueprints, engineers and commodities comes from community data (EDCD) shipped inside the application; nothing is downloaded.
- **Spansh** and **Ardent Insight**: asked only when you search, as said above; turned off in *Settings*.

## Your choices

- **See or delete your data**: everything is in `%LOCALAPPDATA%\EDRockMaster`; delete the folder to erase it. Uninstalling the application keeps it, so that your goals survive a reinstall; delete it by hand if you wish.
- **Stop the reading**: close the application.
- **Check for no updates**: turn *Check for updates* off in *Settings*, *Updates*.
- **Close the phone and tablet's access**: turn it off in *Settings*, *Phone and tablet*, or *Use a new link*.
- **Ask no community tool**: turn Spansh and Ardent Insight off in *Settings*, *Community sources*.

## Children

The application is meant for players of Elite Dangerous, rated PEGI 7 / ESRB Teen; it collects nothing from anyone.

## Contact

Questions about this policy: [contact@edrm.space](mailto:contact@edrm.space). Source code: [github.com/EDRockMaster/edrockmaster-plugin](https://github.com/EDRockMaster/edrockmaster-plugin).

## Changes

Any change to this policy is published here, with its date, before the version of the application it concerns.

*Elite Dangerous is a trademark of Frontier Developments plc. EDRockMaster is not endorsed by or affiliated with Frontier Developments.*
