# Submitting to the Microsoft Store

*English · [Français](store-submission.fr.md)*

How a release of EDRockMaster Companion reaches the Microsoft Store, by hand, as [ADR 0025](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0025-store-submissions.md) decided: only the MSIX that the Windows workflow built for a tag is submitted, a candidate to the testers' package flight, a production to every customer. The release manager follows these steps; the names of Partner Center's screens may drift, update them here when they do.

## Once

- **Package identity**: the GitHub repository variables `EDROCKMASTER_MSIX_NAME`, `EDROCKMASTER_MSIX_PUBLISHER`, `EDROCKMASTER_MSIX_PUBLISHER_NAME` and `EDROCKMASTER_MSIX_DISPLAY_NAME` hold the values of Partner Center (*Product management → Product identity*). Without them the workflow builds a development identity, which Partner Center refuses.
- **Store listing**: the texts of [store-listing.md](store-listing.md) (English) and [store-listing.fr.md](store-listing.fr.md) (French), the screenshots, the privacy policy ([privacy.md](privacy.md)).
- **Testers**: a known user group "testers" (*Settings → Known user groups*: the Microsoft accounts of the testers), before the first submission; once the application is published, a package flight "testers" for that group (*Package flights → New package flight*).
- **First submission**: package flights only exist once the application is published, so the first submission is the application itself, with the first candidate's MSIX (never a development build) and, in *Pricing and availability → Audience*, a **private audience** limited to the testers' known user group: only they can see and install it. It goes public with the first production, below.

## Each release

### 1. The version

1. A pull request `chore(release): X.Y.Z` changes only the version (`pyproject.toml`, `edrockmaster/__init__.py`, `uv.lock`) and the changelog (`CHANGELOG.md`, `CHANGELOG.fr.md`: the *Unreleased* section becomes `X.Y.Z`); the release manager merges it ([ADR 0012](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0012-release-channels.md)). While a version is in acceptance, new changes join its section and the next candidate gets the next number, with the same version.
2. An annotated tag on that commit of `main`, pushed to Gitea:

   ```sh
   git tag -a vX.Y.Z-rc.N -m "vX.Y.Z-rc.N (release candidate, for acceptance)"
   git push origin vX.Y.Z-rc.N
   ```

   For production, after acceptance, `vX.Y.Z` on **the same commit** as the accepted candidate. The CI refuses a production tag without a candidate on its commit.
3. The Gitea mirror pushes the tag to GitHub within a few minutes (else `git push github vX.Y.Z-rc.N`). The Gitea release job publishes the release notes (Gitea only for a candidate; Gitea and GitHub for a production, which Discord announces).

### 2. The package

1. On GitHub, *Actions → Windows build*, the run **of the tag** (its branch column shows `vX.Y.Z-rc.N`, not `main`): it must be green.
2. Download its artifact `EDRockMaster-windows-X.Y.Z-rc.N` and take `EDRockMaster-vX.Y.Z-rc.N.msix` from it. Never the artifact of a branch or of `main`: its build says `dev`.
3. The package version follows [ADR 0022](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0022-microsoft-store-distribution.md): `X.Y.(Z×100+N).0` for candidate N, `X.Y.(Z×100+99).0` for production (`0.4.1.0` for 0.4.0-rc.1, `0.4.99.0` for 0.4.0). It must be higher than every package already submitted: check the last one in *Packages* of the latest submission.

### 3. The submission

- **Candidate**: *Package flights → testers → Create a new submission* (or *Update*); on *Packages*, remove the previous package and upload the MSIX; *Submit to the Store*.
- **Production**: *Start update* on the application's overview; on *Packages*, remove the previous package and upload the MSIX; in each *Store listing* (English, French), *What's new in this version*: the version's section of the changelog, in that language, without the links; for the first production, *Pricing and availability → Audience*: **public audience**; *Submit to the Store*.
- A submission still in certification blocks the next one of the same kind: wait for it, or cancel it in Partner Center first.
- **Restricted capabilities** (*Submission options*): `runFullTrust` and `unvirtualizedResources` need a justification, which a new submission usually takes over. If it is asked again:

  > **runFullTrust**: EDRockMaster is a packaged Win32 desktop application (Python, PyInstaller, WebView2 window). It reads the Elite Dangerous journal files the game writes in the user's Saved Games folder, as they are written, to show mining, trade and exploration statistics live.
  >
  > **unvirtualizedResources**: the application keeps its local database, session recordings and logs in %LOCALAPPDATA%\EDRockMaster. This folder is excluded from file system write virtualization so that the player's history survives a reinstall or an update path change, and so that the player can open the folder to send a recording or a log when reporting a problem. No other folder is unvirtualized and the application writes nowhere else.

### 4. After certification

Certification takes hours to days. Then:

- **Candidate**: the testers install or update from the Store; the window shows `X.Y.Z-rc.N` beside its name. Acceptance happens on this Store-signed build. A fix means a new pull request, a new candidate `rc.N+1` and a new submission.
- **Production**: the window shows `X.Y.Z`; the release notes are on GitHub and Discord announced them.
- If certification fails, Partner Center's report says why; the fix goes through a pull request and a new candidate, never a package built by hand.
