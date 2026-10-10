# Soumettre au Microsoft Store

*[English](store-submission.md) · Français*

Comment une version d'EDRockMaster Companion arrive dans le Microsoft Store, à la main, comme l'a décidé l'[ADR 0025](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0025-store-submissions.fr.md) : seul le MSIX que le workflow Windows a construit pour un tag est soumis, une candidate au vol de paquets des testeurs, une production à tous les clients. Le responsable des releases suit ces étapes ; les noms des écrans de Partner Center peuvent changer, les mettre à jour ici le cas échéant.

## Une fois

- **Identité du paquet** : les variables du dépôt GitHub `EDROCKMASTER_MSIX_NAME`, `EDROCKMASTER_MSIX_PUBLISHER`, `EDROCKMASTER_MSIX_PUBLISHER_NAME` et `EDROCKMASTER_MSIX_DISPLAY_NAME` portent les valeurs de Partner Center (*Gestion du produit → Identité du produit*). Sans elles, le workflow construit une identité de développement, que Partner Center refuse.
- **Fiche du Store** : les textes de [store-listing.md](store-listing.md) (anglais) et [store-listing.fr.md](store-listing.fr.md) (français), les captures d'écran, la politique de confidentialité ([privacy.fr.md](privacy.fr.md)).
- **Testeurs** : un groupe d'utilisateurs connus « testers » (*Paramètres → Groupes d'utilisateurs connus* : les comptes Microsoft des testeurs), utilisé par la première soumission ; une fois l'application publique, un vol de paquets « testers » pour ce groupe (*Vols de paquets → Nouveau vol de paquets*).
- **Première soumission** : les vols de paquets n'existent qu'une fois l'application publiée, donc la première soumission est celle de l'application elle-même, avec le MSIX de la première candidate (jamais un build de développement) et, dans *Tarification et disponibilité → Audience*, une **audience privée** limitée au groupe d'utilisateurs connus des testeurs : eux seuls la voient et l'installent. Tant qu'elle est privée, une nouvelle candidate est une simple mise à jour de l'application, puisque seuls les testeurs la voient. Elle passe en public avec la première production, ci-dessous.

## À chaque version

### 1. La version

1. Une pull request `chore(release): X.Y.Z` ne change que la version (`pyproject.toml`, `edrockmaster/__init__.py`, `uv.lock`) et le journal des modifications (`CHANGELOG.md`, `CHANGELOG.fr.md` : la section *Unreleased* devient `X.Y.Z`) ; le responsable des releases la fusionne ([ADR 0012](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0012-release-channels.fr.md)). Tant qu'une version est en recette, les nouveautés rejoignent sa section et la candidate suivante prend le numéro suivant, avec la même version.
2. Un tag annoté sur ce commit de `main`, poussé sur Gitea :

   ```sh
   git tag -a vX.Y.Z-rc.N -m "vX.Y.Z-rc.N (release candidate, for acceptance)"
   git push origin vX.Y.Z-rc.N
   ```

   Pour la production, après la recette, `vX.Y.Z` sur **le même commit** que la candidate recettée. La CI refuse un tag de production sans candidate sur son commit.
3. Le miroir de Gitea pousse le tag sur GitHub en quelques minutes (sinon `git push github vX.Y.Z-rc.N`). La tâche de release de Gitea publie les notes de version (sur Gitea seulement pour une candidate ; sur Gitea et GitHub pour une production, que Discord annonce).

### 2. Le paquet

1. Sur GitHub, *Actions → Windows build*, l'exécution **du tag** (sa colonne de branche affiche `vX.Y.Z-rc.N`, pas `main`) : elle doit être verte.
2. Télécharger son artefact `EDRockMaster-windows-X.Y.Z-rc.N` et en prendre `EDRockMaster-vX.Y.Z-rc.N.msix`. Jamais l'artefact d'une branche ou de `main` : son build dit `dev`.
3. La version du paquet suit l'[ADR 0022](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0022-microsoft-store-distribution.fr.md) : `X.Y.(Z×100+N).0` pour la candidate N, `X.Y.(Z×100+99).0` pour la production (`0.4.1.0` pour 0.4.0-rc.1, `0.4.99.0` pour 0.4.0). Elle doit être supérieure à tous les paquets déjà soumis : vérifier le dernier dans *Paquets* de la dernière soumission.

### 3. La soumission

- **Candidate** : tant que l'application est privée, en mise à jour de l'application (*Démarrer la mise à jour*) ; une fois publique, *Vols de paquets → testers → Créer une soumission* (ou *Mettre à jour*) ; dans *Paquets*, retirer le paquet précédent et envoyer le MSIX ; *Soumettre au Store*.
- **Production** : *Démarrer la mise à jour* depuis la vue d'ensemble de l'application ; dans *Paquets*, retirer le paquet précédent et envoyer le MSIX ; dans chaque *Fiche du Store* (anglais, français), *Nouveautés de cette version* : la section de la version dans le journal des modifications, dans cette langue, sans les liens ; pour la première production, *Tarification et disponibilité → Audience* : **audience publique** ; *Soumettre au Store*.
- Une soumission encore en certification bloque la suivante du même type : l'attendre, ou l'annuler d'abord dans Partner Center.
- **Capacités restreintes** (*Options de soumission*) : `runFullTrust` et `unvirtualizedResources` demandent une justification, qu'une nouvelle soumission reprend en général. Si elle est redemandée (en anglais, pour l'équipe de certification) :

  > **runFullTrust**: EDRockMaster is a packaged Win32 desktop application (Python, PyInstaller, WebView2 window). It reads the Elite Dangerous journal files the game writes in the user's Saved Games folder, as they are written, to show mining, trade and exploration statistics live.
  >
  > **unvirtualizedResources**: the application keeps its local database, session recordings and logs in %LOCALAPPDATA%\EDRockMaster. This folder is excluded from file system write virtualization so that the player's history survives a reinstall or an update path change, and so that the player can open the folder to send a recording or a log when reporting a problem. No other folder is unvirtualized and the application writes nowhere else.

### 4. Après la certification

La certification prend de quelques heures à quelques jours. Ensuite :

- **Candidate** : les testeurs installent ou mettent à jour depuis le Store ; la fenêtre affiche `X.Y.Z-rc.N` à côté de son nom. La recette se fait sur ce build signé par le Store. Un correctif demande une nouvelle pull request, une nouvelle candidate `rc.N+1` et une nouvelle soumission.
- **Production** : la fenêtre affiche `X.Y.Z` ; les notes de version sont sur GitHub et Discord les a annoncées.
- Si la certification échoue, le rapport de Partner Center dit pourquoi ; le correctif passe par une pull request et une nouvelle candidate, jamais par un paquet construit à la main.
