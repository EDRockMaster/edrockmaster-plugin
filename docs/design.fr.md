# Conception du plugin

*[English](design.md) · Français*

Conception du plugin EDMC d'EDRockMaster. Périmètre : **jalon 1, étape 1A** (plugin local, premier essai en jeu), plus l'activité de chasse à la prime ([ADR 0011](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0011-plugin-activities.fr.md)). La liaison avec le serveur (étape 1B) est conçue ici pour ne pas avoir à reprendre 1A, mais elle n'est pas encore réalisée. Les contraintes viennent des [prérequis](prerequisites.fr.md) ; les règles d'ingénierie, de `edrockmaster-architecture`.

## Objectifs de l'étape 1A

- Assistance au minage en direct, sans serveur : alertes du prospecteur, cores, statistiques de session, drones.
- Interface bilingue (anglais, français), qui suit la langue d'EDMC.
- Un enregistreur de journal (sur activation) qui transforme de vraies parties en jeux de données de test.
- Une structure prête pour la liaison avec le serveur : ports déjà définis, adaptateurs ajoutés en 1B.

Hors périmètre de 1A : envois, connexion, estimation de la valeur de la soute (elle demande les prix du serveur), overlay.

## Architecture

Hexagonale, comme les services, dans les limites d'EDMC :

```
load.py                         points d'entrée EDMC uniquement, délègue à edrockmaster.edmc
edrockmaster/
  __init__.py                   VERSION
  domain/                       Python pur : ni EDMC, ni tkinter, ni entrées-sorties
    journal_reading.py          noyau partagé : lecture tolérante des entrées du journal (ADR 0011)
    commodities.py              noyau partagé : noms des commodités, normalisation
    mining/                     contexte du minage
      journal.py                entrée du journal → fait du minage
      prospecting.py            astéroïde prospecté, politique d'alerte
      session.py                agrégat MiningTracker (cycle de vie, statistiques, ventes)
    bounty/                     contexte de la chasse à la prime
      journal.py                entrée du journal → fait de la chasse
      hunting.py                agrégat HuntingTracker (sessions, bons, objectifs communautaires)
  application/
    activity.py                 les activités : minage, chasse à la prime
    companion.py                Companion : enregistre le journal une fois, passe chaque entrée à chaque activité, porte les réglages
    settings.py                 PluginSettings (alertes, son, enregistreur) et leurs valeurs par défaut
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder (et, en 1B, UploadQueue, Authenticator)
    mining_service.py           cas d'usage du minage : traiter une entrée du journal, réinitialiser la session, appliquer les réglages
    hunting_service.py          cas d'usage de la chasse : traiter une entrée du journal, réinitialiser la session
  infrastructure/
    settings_edmc.py            SettingsStore sur le config d'EDMC (clés préfixées « edrockmaster. »)
    recorder_jsonl.py           JournalRecorder : fichiers JSONL dans le dossier de données
    sound.py                    Notifier : alertes sonores (winsound sous Windows, cloche Tk ailleurs)
    paths.py                    dossier de données selon le système
    worker.py                   l'unique fil d'entrées-sorties du plugin et sa file
    clock.py                    Clock : heure système, en UTC
  edmc/
    plugin.py                   assemblage : construit le graphe d'objets, implémente les hooks
    i18n.py                     tl() relié au l10n d'EDMC, avec un repli pour les tests
    host.py                     services d'EDMC (theme, plug.show_error, l10n.Locale), avec replis
  ui/
    panel_model.py              PanelModel (textes) et mise en forme commune, sans tkinter
    presenter.py                ActivityPresenter : montre l'activité en cours
    mining_presenter.py         notifications du minage → PanelModel
    hunting_presenter.py        notifications de la chasse → PanelModel
    preferences_form.py         réglages <-> champs des préférences, validation, sans tkinter
    commodity_names.py          noms des commodités minables connues avant que le journal ne les nomme
    panel.py                    panneau de la fenêtre principale (tkinter, fil principal uniquement), recopie PanelModel
    preferences.py              onglet des préférences (myNotebook)
L10n/fr.strings                 traductions françaises
```

Règle de dépendance : `domain` n'importe rien du plugin ; `application` importe `domain` ; `infrastructure`, `edmc` et `ui` importent `application` et `domain`. Seuls `load.py` (qui ne s'exécute que dans EDMC), `edmc/`, `ui/` et les adaptateurs propres à EDMC importent des modules d'EDMC ; hormis dans `load.py`, toujours protégés par `try/except ImportError` pour que le reste soit testable hors d'EDMC.

## Circulation des données

1. EDMC appelle `journal_entry(...)` sur le fil principal.
2. `edmc/plugin.py` transmet l'entrée à `Companion.handle_journal_entry(entry, is_beta)`, qui la copie dans le `JournalRecorder` (si l'enregistrement est activé), puis la passe à chaque activité : `MiningService`, puis `HuntingService`. Chaque activité traduit le journal pour son propre compte ; ci-dessous, le chemin du minage.
3. `domain/mining/journal.py` transforme l'entrée brute en fait typé (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`…) ou l'ignore. Les événements et champs inconnus sont ignorés, jamais bloquants.
4. L'agrégat `MiningTracker` applique le fait et renvoie des notifications de session.
5. Le `ProspectingMonitor` évalue chaque astéroïde prospecté au regard des réglages d'alerte.
6. Le service distribue le résultat : l'alerte au `Notifier` (si le son est activé), et renvoie les notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) à l'appelant, qui les passe à l'`ActivityPresenter` : il montre la dernière activité dont la session a progressé.
7. Le panneau est rafraîchi sur le fil principal.

Tout ceci n'est que du calcul sur de petits objets (bien moins d'une milliseconde par événement) : ça reste sur le fil principal. Tout ce qui touche aux fichiers ou au réseau passe par le fil d'entrées-sorties.

`edmc/plugin.py` est la racine de composition. `load.py` lui fournit le `config` d'EDMC ; il construit le fil d'entrées-sorties, les adaptateurs et le `Companion` dans `plugin_start3`, et arrête le fil dans `plugin_stop`. L'interface s'abonne aux notifications et fournit le son d'alerte, qui a besoin d'un widget. Le bouton de réinitialisation termine la session de l'activité affichée. Toute exception pendant le traitement d'une entrée est journalisée et signalée dans la barre d'état d'EDMC ; les entrées suivantes sont traitées normalement. Le logger est celui qu'EDMC prépare pour le plugin, `<appname>.<dossier du plugin>`.

## Fils d'exécution

- **Fil principal** : hooks, domaine, interface.
- **Un fil d'entrées-sorties** (`infrastructure/worker.py`) : fil démon alimenté par une `queue.Queue` de tâches (ajout au fichier d'enregistrement en 1A ; envois et authentification en 1B). Il ne touche jamais à tkinter. En 1A, il n'a rien à signaler à l'interface. À partir de 1B (état des envois), il déposera un message dans une file de résultats et appellera `event_generate("<<EDRockMasterUpdate>>")` sur le panneau, sauf si `config.shutting_down` est vrai.
- `plugin_stop()` dépose une tâche d'arrêt, attend la fin du fil avec un délai maximal, et vide l'enregistreur.

## Cycle de vie d'une session de minage

| Situation | Effet |
| --- | --- |
| `SupercruiseExit`, `Location` ou `StartUp` avec `BodyType` = `PlanetaryRing` | Anneau courant connu (nom, système) |
| Première activité de minage (`LaunchDrone` prospecteur, `ProspectedAsteroid`, `MiningRefined`) | Une session démarre s'il n'y en a pas en cours |
| `ProspectedAsteroid` | Astéroïde enregistré, politique d'alerte évaluée |
| `MiningRefined` | Une tonne de la commodité comptée |
| `LaunchDrone` | Drone compté par type |
| `AsteroidCracked` | Core fissuré |
| `Cargo` (enrichi par EDMC) | Instantané de la soute : tonnes à bord, capacité utilisée |
| `EjectCargo` | Tonnes larguées comptées à part (hors production) |
| Aucune activité de minage pendant 10 minutes | Session en pause : le temps inactif n'est pas compté |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Fin de la session |
| `StartUp` (synthétique, EDMC lancé en cours de partie) | Anneau courant tiré de `Body`/`BodyType` de l'événement ; les chiffres de la soute arrivent avec le prochain événement `Cargo` (le jeu en écrit un à chaque raffinage) |
| `MarketSell` | Crédité à la session en cours, sinon à la dernière terminée : seulement ses tonnes minées ni éjectées ni encore vendues, au prix unitaire de la vente |
| Réinitialisation manuelle (bouton du panneau) | Fin de la session, une nouvelle peut démarrer |
| `is_beta`, ou `gameversion` autre que 4.x dans `LoadGame` | Tout fonctionne en local ; marqué comme non envoyable (1B) |

Statistiques d'une session : durée active, tonnes par commodité, tonnes totales, tonnes par heure, astéroïdes prospectés (par niveau de teneur), cores trouvés et fissurés, drones lancés (prospecteurs, collecteurs), raffinages par minute, tonnes vendues et crédits gagnés.

## Chasse à la prime

| Situation | Effet |
| --- | --- |
| `Bounty` (format vaisseau avec `Rewards`, ou format simple pour les skimmers et à pied) | Une victime ; crédits de prime ; un bon de prime par faction payeuse |
| `FactionKillBond` | Une victime ; crédits et bon d'obligation de combat |
| `CapShipBond` | Crédits et bon d'obligation de combat, sans victime |
| Première récompense | La session de chasse commence |
| Aucune récompense pendant 15 minutes | Session en pause : le temps inactif n'est pas compté |
| Amarrage, supercroisière, sauts | Rien : les chasseurs passent d'un site à l'autre et s'amarrent pour se réarmer |
| `Died` | La session se termine ; les bons non encaissés sont perdus |
| `Shutdown`, `ShutDown` | La session se termine |
| `RedeemVoucher` (primes, obligations de combat) | Les bons payés sont retirés, par faction, jamais en dessous de zéro |
| `CommunityGoal` | Les objectifs rejoints par le commandant : contribution, tranche de classement, palier atteint |
| Réinitialisation manuelle (bouton du panneau, chasse affichée) | La session se termine, une nouvelle peut commencer |

Statistiques d'une session de chasse : durée active, victimes (et victimes partagées), crédits de primes et d'obligations de combat, crédits par heure. Communs au panneau : les bons non encaissés (connus seulement depuis le lancement d'EDMC : le journal ne redonne pas les plus anciens) et les objectifs communautaires. Les superpuissances écrites `$faction_Federation;` sont ramenées à `Federation`.

## Alertes du prospecteur

- Seuil par commodité, en pourcentage de l'astéroïde, modifiable. Valeurs par défaut (2026-10-03, à ajuster après l'essai en jeu) : platine 20 %, diamants basse température 20 %, painite 25 %, osmium 25 %, palladium 25 %, or 25 %. Teneur minimale faible, pas de réserve minimale, alerte sur les cores, son activé, enregistreur du journal désactivé.
- Niveau de teneur minimal (High, Medium, Low).
- Réserve restante minimale (`Remaining`), facultative.
- Un motherlode (core) déclenche sa propre alerte, quels que soient les seuils.
- Prospecter deux fois le même astéroïde (même composition à moins de 60 secondes d'intervalle) ne déclenche pas de seconde alerte.

## Interface

**Panneau** (fenêtre principale d'EDMC) : état (aucune session, minage dans un anneau, session terminée et pourquoi), la dernière alerte du prospecteur, mise en évidence jusqu'au prochain astéroïde prospecté, puis les statistiques : temps actif, tonnes raffinées, rendement, tonnes par commodité, astéroïdes prospectés et, dès qu'ils sont connus, cores, drones, soute et ventes. Les statistiques d'une session terminée restent affichées, et ses ventes s'y ajoutent. Un bouton **Réinitialiser** termine la session en cours. Les nombres suivent les réglages régionaux du système, comme ceux d'EDMC.

**Onglet des préférences** : un champ de pourcentage par commodité minable (vide : pas d'alerte), teneur minimale, réserve minimale, alerte sur les cores, son, enregistreur du journal et un bouton qui ouvre le dossier des enregistrements. Les nombres se saisissent selon les réglages régionaux du système. À la fermeture de la fenêtre, une saisie invalide garde sa valeur précédente et est citée dans la barre d'état d'EDMC ; les saisies valides sont appliquées tout de suite.

## Réglages

Enregistrés avec le `config` d'EDMC (`config.set` / `config.get_*`), clés préfixées par `edrockmaster.`, lus au démarrage et dans `prefs_changed`. Le domaine reçoit un objet de réglages immuable, jamais le stockage.

| Clé | Type | Contenu |
| --- | --- | --- |
| `edrockmaster.settings_version` | texte | Version du format des clés ci-dessous (`1`), pour les migrations futures |
| `edrockmaster.alert.thresholds` | texte | Objet JSON, clé de commodité → pourcentage (`{"painite": 25.0, …}`) |
| `edrockmaster.alert.minimum_content` | texte | `low`, `medium` ou `high` |
| `edrockmaster.alert.minimum_remaining` | texte | Pourcentage, ou vide si aucune (en texte, pour tous les stockages de config d'EDMC) |
| `edrockmaster.alert.cores` | booléen | Alerte sur les cores |
| `edrockmaster.sound` | booléen | Alertes sonores |
| `edrockmaster.record_journal` | booléen | Enregistreur du journal |

Les valeurs sont lues une à une : une valeur absente ou invalide reprend sa propre valeur par défaut (avec un avertissement dans le journal), les autres sont conservées.

## Fichiers

Dossier de données, hors du dossier du plugin pour survivre aux mises à jour du plugin :

- Windows : `%LOCALAPPDATA%\EDRockMaster`
- Linux : `$XDG_DATA_HOME/EDRockMaster`, ou `~/.local/share/EDRockMaster`
- macOS : `~/Library/Application Support/EDRockMaster`

Contenu en 1A : `recordings/` (enregistrements du journal, JSONL, un fichier par lancement d'EDMC). En 1B : la file d'envoi (SQLite).

## Enregistreur de journal

- Désactivé par défaut ; activé dans les préférences (« Enregistrer le journal pour le débogage »).
- Écrit chaque entrée reçue par le plugin, sans modification, un objet JSON par ligne, avec l'indicateur `is_beta` : `{"is_beta": false, "entry": {…}}`. Fichier : `recordings/journal-<début, UTC, AAAAMMJJTHHMMSSZ>.jsonl`.
- L'entrée est sérialisée dès sa réception (EDMC partage le même dict avec tous les plugins), puis écrite par le fil d'entrées-sorties.
- C'est à partir de ces enregistrements que l'on constitue `tests/fixtures/` ; le joueur décide de ce qu'il partage.

## Internationalisation

- Textes source en anglais dans le code, passés par `tl()` (`edmc/i18n.py`, relié à `l10n.translations.tl` avec `context=__file__`).
- Français dans `L10n/fr.strings` (format `.strings`, UTF-8).
- Les textes affichés sont rafraîchis dans `prefs_changed` : le présentateur garde des objets du domaine, pas des textes, et reconstruit chaque texte dans la langue courante.
- Les décomptes évitent l'accord au pluriel (`prospecteurs : 3`), que les fichiers `.strings` ne savent pas exprimer.
- `tests/test_translations.py` échoue si un texte passé à `tl()` n'a pas de traduction française, si une traduction ne sert plus, ou si les paramètres diffèrent.
- Les noms de commodités viennent des champs `*_Localised` du journal quand ils existent (la langue du jeu), sinon de nos propres noms.

## Préparé pour l'étape 1B

Ports définis en 1A, réalisés en 1B :

- `UploadQueue` : file SQLite dans le dossier de données ; chaque fait envoyable reçoit un identifiant client (`uuid4`).
- `Authenticator` : device flow Keycloak ; refresh token stocké avec `config`.
- `Uploader` : lots (gzip) vers `edrockmaster-ingest`, sur le fil d'entrées-sorties, avec reprise progressive.
- Killswitch : module `killswitch` d'EDMC, relu toutes les 10 minutes depuis notre serveur.
- Galaxie au `StartUp` : il n'y a pas de `LoadGame` dans ce cas, la version du jeu doit donc être lue dans `state["GameVersion"]` pour distinguer Live et Legacy.

## Tests

- **Domaine et application : en TDD**, avec `pytest` seul, sans EDMC.
- **Jeux de données** : extraits de vrais journaux (`tests/fixtures/*.jsonl`), enregistrés avec l'enregistreur.
- **Tests de rejeu** : une session enregistrée complète est rejouée dans `MiningService`, et les statistiques finales sont vérifiées.
- **Adaptateurs EDMC** : testés avec de faux modules `config`, `l10n` et `theme` injectés par `tests/conftest.py`.
- **Interface** : le présentateur et le formulaire des préférences sont purs et entièrement testés. Les widgets tkinter restent minces ; leurs tests utilisent un vrai Tk et sont sautés là où il n'y a pas d'affichage (CI), ils tournent donc sur les postes des développeurs. Vérifiée en jeu pendant le test 1A.
- CI : `ruff`, `mypy --strict`, `pytest` avec couverture sur `domain/` et `application/`.
