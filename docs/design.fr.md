# Conception du plugin

*[English](design.md) · Français*

Conception du plugin EDMC d'EDRockMaster. Périmètre de cette version : **jalon 1, étape 1A** (plugin local, premier essai en jeu). La liaison avec le serveur (étape 1B) est conçue ici pour ne pas avoir à reprendre 1A, mais elle n'est pas encore réalisée. Les contraintes viennent des [prérequis](prerequisites.fr.md) ; les règles d'ingénierie, de `edrockmaster-architecture`.

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
    journal.py                  entrée du journal → fait du domaine (lecteur tolérant)
    commodities.py              noms des commodités, normalisation
    prospecting.py              astéroïde prospecté, politique d'alerte
    session.py                  agrégat MiningSession (cycle de vie, statistiques)
  application/
    settings.py                 PluginSettings (alertes, son, enregistreur) et leurs valeurs par défaut
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder (et, en 1B, UploadQueue, Authenticator)
    mining_service.py           cas d'usage : traiter une entrée du journal, réinitialiser la session, modifier les réglages
  infrastructure/
    settings_edmc.py            SettingsStore sur le config d'EDMC (clés préfixées « edrockmaster. »)
    recorder_jsonl.py           JournalRecorder : fichiers JSONL dans le dossier de données
    sound.py                    Notifier : alertes sonores (winsound sous Windows, cloche Tk ailleurs)
    paths.py                    dossier de données selon le système
    worker.py                   l'unique fil d'entrées-sorties du plugin et sa file
  edmc/
    plugin.py                   assemblage : construit le graphe d'objets, implémente les hooks
    i18n.py                     tl() relié au l10n d'EDMC, avec un repli pour les tests
  ui/
    panel.py                    panneau de la fenêtre principale (tkinter, fil principal uniquement)
    preferences.py              onglet des préférences (myNotebook)
    presenter.py                modèles de vue construits à partir des notifications du domaine
L10n/fr.strings                 traductions françaises
```

Règle de dépendance : `domain` n'importe rien du plugin ; `application` importe `domain` ; `infrastructure`, `edmc` et `ui` importent `application` et `domain`. Seuls `edmc/`, `ui/` et les adaptateurs propres à EDMC importent des modules d'EDMC, toujours protégés par `try/except ImportError` pour que le reste soit testable hors d'EDMC.

## Circulation des données

1. EDMC appelle `journal_entry(...)` sur le fil principal.
2. `edmc/plugin.py` transmet l'entrée à `MiningService.handle_journal_entry(entry, is_beta)`.
3. `domain/journal.py` transforme l'entrée brute en fait typé (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`…) ou l'ignore. Les événements et champs inconnus sont ignorés, jamais bloquants.
4. L'agrégat `MiningTracker` applique le fait et renvoie des notifications de session.
5. Le `ProspectingMonitor` évalue chaque astéroïde prospecté au regard des réglages d'alerte.
6. Le service distribue le résultat : l'alerte au `Notifier` (si le son est activé), l'entrée telle quelle au `JournalRecorder` (si l'enregistrement est activé), et renvoie les notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) à l'appelant, qui les passe au présentateur.
7. Le panneau est rafraîchi sur le fil principal.

Tout ceci n'est que du calcul sur de petits objets (bien moins d'une milliseconde par événement) : ça reste sur le fil principal. Tout ce qui touche aux fichiers ou au réseau passe par le fil d'entrées-sorties.

## Fils d'exécution

- **Fil principal** : hooks, domaine, interface.
- **Un fil d'entrées-sorties** (`infrastructure/worker.py`) : fil démon alimenté par une `queue.Queue` de tâches (ajout au fichier d'enregistrement en 1A ; envois et authentification en 1B). Il ne touche jamais à tkinter. Quand il doit mettre à jour l'interface, il dépose un message dans une file de résultats et appelle `event_generate("<<EDRockMasterUpdate>>")` sur le panneau, sauf si `config.shutting_down` est vrai.
- `plugin_stop()` dépose une tâche d'arrêt, attend la fin du fil avec un délai maximal, et vide l'enregistreur.

## Cycle de vie d'une session de minage

| Situation | Effet |
| --- | --- |
| `SupercruiseExit` avec `BodyType` = `PlanetaryRing` | Anneau courant connu (nom, système) |
| Première activité de minage (`LaunchDrone` prospecteur, `ProspectedAsteroid`, `MiningRefined`) | Une session démarre s'il n'y en a pas en cours |
| `ProspectedAsteroid` | Astéroïde enregistré, politique d'alerte évaluée |
| `MiningRefined` | Une tonne de la commodité comptée |
| `LaunchDrone` | Drone compté par type |
| `AsteroidCracked` | Core fissuré |
| `Cargo` (enrichi par EDMC) | Instantané de la soute : tonnes à bord, capacité utilisée |
| `EjectCargo` | Tonnes larguées comptées à part (hors production) |
| Aucune activité de minage pendant 10 minutes | Session en pause : le temps inactif n'est pas compté |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Fin de la session |
| `StartUp` (EDMC lancé en cours de partie) | Contexte reconstruit à partir de `state` (vaisseau, soute, système) |
| Réinitialisation manuelle (bouton du panneau) | Fin de la session, une nouvelle peut démarrer |
| `is_beta`, ou `gameversion` autre que 4.x dans `LoadGame` | Tout fonctionne en local ; marqué comme non envoyable (1B) |

Statistiques d'une session : durée active, tonnes par commodité, tonnes totales, tonnes par heure, astéroïdes prospectés (par niveau de teneur), cores trouvés et fissurés, drones lancés (prospecteurs, collecteurs), raffinages par minute.

## Alertes du prospecteur

- Seuil par commodité, en pourcentage de l'astéroïde, modifiable. Valeurs par défaut (2026-10-03, à ajuster après l'essai en jeu) : platine 20 %, diamants basse température 20 %, painite 25 %, osmium 25 %, palladium 25 %, or 25 %. Teneur minimale faible, pas de réserve minimale, alerte sur les cores, son activé, enregistreur du journal désactivé.
- Niveau de teneur minimal (High, Medium, Low).
- Réserve restante minimale (`Remaining`), facultative.
- Un motherlode (core) déclenche sa propre alerte, quels que soient les seuils.
- Prospecter deux fois le même astéroïde (même composition à moins de 60 secondes d'intervalle) ne déclenche pas de seconde alerte.

## Réglages

Enregistrés avec le `config` d'EDMC (`config.set` / `config.get_*`), clés préfixées par `edrockmaster.`, lus au démarrage et dans `prefs_changed`. Le domaine reçoit un objet de réglages immuable, jamais le stockage.

## Fichiers

Dossier de données, hors du dossier du plugin pour survivre aux mises à jour du plugin :

- Windows : `%LOCALAPPDATA%\EDRockMaster`
- Linux : `$XDG_DATA_HOME/EDRockMaster`, ou `~/.local/share/EDRockMaster`
- macOS : `~/Library/Application Support/EDRockMaster`

Contenu en 1A : `recordings/` (enregistrements du journal, JSONL, un fichier par lancement d'EDMC). En 1B : la file d'envoi (SQLite).

## Enregistreur de journal

- Désactivé par défaut ; activé dans les préférences (« Enregistrer le journal pour le débogage »).
- Écrit chaque entrée reçue par le plugin, sans modification, un objet JSON par ligne, avec l'indicateur `is_beta`.
- C'est à partir de ces enregistrements que l'on constitue `tests/fixtures/` ; le joueur décide de ce qu'il partage.

## Internationalisation

- Textes source en anglais dans le code, passés par `tl()` (`edmc/i18n.py`, relié à `l10n.translations.tl` avec `context=__file__`).
- Français dans `L10n/fr.strings` (format `.strings`, UTF-8).
- Les textes affichés sont rafraîchis dans `prefs_changed`.
- Les noms de commodités viennent des champs `*_Localised` du journal quand ils existent (la langue du jeu), sinon de nos propres noms.

## Préparé pour l'étape 1B

Ports définis en 1A, réalisés en 1B :

- `UploadQueue` : file SQLite dans le dossier de données ; chaque fait envoyable reçoit un identifiant client (`uuid4`).
- `Authenticator` : device flow Keycloak ; refresh token stocké avec `config`.
- `Uploader` : lots (gzip) vers `edrockmaster-ingest`, sur le fil d'entrées-sorties, avec reprise progressive.
- Killswitch : module `killswitch` d'EDMC, relu toutes les 10 minutes depuis notre serveur.

## Tests

- **Domaine et application : en TDD**, avec `pytest` seul, sans EDMC.
- **Jeux de données** : extraits de vrais journaux (`tests/fixtures/*.jsonl`), enregistrés avec l'enregistreur.
- **Tests de rejeu** : une session enregistrée complète est rejouée dans `MiningService`, et les statistiques finales sont vérifiées.
- **Adaptateurs EDMC** : testés avec de faux modules `config`, `l10n` et `theme` injectés par `tests/conftest.py`.
- **Interface** : volontairement mince (présentateur testé, widgets non testés unitairement) ; vérifiée en jeu pendant le test 1A.
- CI : `ruff`, `mypy --strict`, `pytest` avec couverture sur `domain/` et `application/`.
