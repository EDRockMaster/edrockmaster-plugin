# Prérequis du plugin

Contraintes imposées par EDMarketConnector (EDMC) et par le registre officiel des plugins d'EDCD. Relevées le 2026-10-02 sur EDMC 6.1.2.

Sources :

- [EDMC `PLUGINS.md`](https://github.com/EDCD/EDMarketConnector/blob/main/PLUGINS.md) : API des plugins.
- [EDMC `docs/Bundled_Python_Dependencies.md`](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Bundled_Python_Dependencies.md) : modules embarqués.
- [EDMC `docs/Killswitches.md`](https://github.com/EDCD/EDMarketConnector/blob/main/docs/Killswitches.md) : coupure à distance.
- [EDMC-Plugin-Registry](https://github.com/EDCD/EDMC-Plugin-Registry) : `docs/STANDARDS.md` et `docs/CONTRIBUTING.md`.

## Environnement d'exécution

| Élément | Valeur | Conséquence |
| --- | --- | --- |
| Version d'EDMC visée | 6.1.x (6.1.2 au 2026-10-02) | Le registre exige la compatibilité avec la version mineure courante |
| Python | 3.13, **32 bits** sous Windows, embarqué dans l'exécutable | Pas de `pip` chez le joueur. Attention aux tailles d'entiers et à la mémoire |
| Interface | tkinter, fournie par EDMC | Widgets de `myNotebook` pour les préférences, `theme` pour suivre le thème |

## Dépendances

- **Aucune dépendance embarquée** dans le plugin. Le registre interdit d'embarquer plus que le nécessaire (« moindre privilège »).
- `requests` (avec `certifi`) est garanti par EDMC : c'est **le** client HTTP à utiliser, jamais `urllib`, qui dépend des certificats du système.
- Modules de la bibliothèque standard confirmés dans la build Windows : `sqlite3`, `gzip`, `json`, `uuid`, `secrets`, `hashlib`, `webbrowser`, `queue`, `threading`, `concurrent`, `ssl`, `tomllib`. **Absent : `zoneinfo`** (travailler en UTC).
- La liste des modules embarqués n'est **pas** une API garantie : tout import hors de la bibliothèque standard et de l'API d'EDMC passe par un `try/except` avec un comportement dégradé.

## API d'EDMC autorisée

Seuls ces imports sont supportés :

- `config` : uniquement `config.set()`, `config.get_str/int/bool/list()`, `config.delete()` pour **nos propres** réglages, et la propriété `config.shutting_down` (sans parenthèses).
- `theme`, `l10n` (traductions), `prefs.prefsVersion`, `monitor.game_running()`, `plug.show_error()`.
- `companion` (`CAPIData`, `SERVER_LIVE`, `SERVER_LEGACY`, `SERVER_BETA`) et `edmc_data` (constantes, dont les drapeaux de `Status.json`).
- `killswitch` : killswitch hébergé par le plugin (voir plus bas).

## Points d'entrée (`load.py`)

| Fonction | Rôle pour nous |
| --- | --- |
| `plugin_start3(plugin_dir)` | Obligatoire. Initialise le plugin, retourne son nom interne |
| `plugin_app(parent)` | Panneau dans la fenêtre principale |
| `plugin_prefs(parent, cmdr, is_beta)` / `prefs_changed(cmdr, is_beta)` | Onglet de préférences, enregistrement |
| `journal_entry(cmdr, is_beta, system, station, entry, state)` | Événements du journal : cœur de la collecte |
| `journal_entry_cqc(...)` | Arène (CQC) : à ignorer pour le minage |
| `dashboard_entry(cmdr, is_beta, entry)` | `Status.json`, environ une fois par seconde (drapeaux, soute) |
| `plugin_stop()` | Arrêter **et attendre** les fils d'exécution |

Événements particuliers à gérer : `StartUp` (synthétique, quand EDMC démarre en cours de partie : pas de `LoadGame` ni de `Location`, mais `state` est à jour), `ShutDown` (synthétique, plantage du jeu) et `Shutdown` (sortie normale), `Cargo` enrichi du contenu de `Cargo.json`.

## Règles d'exécution

- **Tous les hooks tournent sur le fil principal de tkinter.** Rien de long (plus d'une seconde) ni de réseau dans un hook.
- **Le réseau et les traitements longs vont dans un fil dédié**, alimenté par une file (`queue.Queue`).
- **Un fil secondaire ne touche jamais à tkinter.** Il prévient le fil principal par `event_generate()` sur un événement virtuel lié par `bind_all()`, **sauf pendant l'arrêt** (`config.shutting_down`), sinon EDMC se bloque.
- **Erreurs** : une chaîne retournée par un hook, ou `plug.show_error()` depuis un fil. La zone d'état est partagée et le message disparaît vite : l'état de la liaison serveur a son propre widget.
- **Journalisation** avec `logging`, selon le modèle de `PLUGINS.md` (logger nommé `f"{appname}.{nom_du_dossier}"`). Jamais de `print`.

## Nommage et paquetage

- Le dossier du plugin doit être **importable** : pas de tiret ni de point. Dossier retenu : `EDRockMaster`.
- **Les modules sont partagés entre tous les plugins** : un `import mining` charge le premier module `mining` trouvé, peut-être celui d'un autre plugin. Notre code vit donc dans un paquet au nom unique (`edrockmaster`), jamais dans un module au nom générique.
- `VERSION` au format SemVer strict (`MAJEUR.MINEUR.CORRECTIF`) dans `load.py` : le navigateur de plugins s'en sert pour comparer les versions, et la future mise à jour automatique aussi.
- Distribution : un zip contenant le dossier `EDRockMaster/`, sans `__pycache__`.

## Registre de plugins d'EDCD

Conditions pour être listé (et le rester) :

- Licence open source compatible GPL v2 ou ultérieure : GPL-3.0-or-later.
- Compatibilité maintenue avec la version mineure courante d'EDMC.
- Aucune action contraire au CLUF de Frontier, aucun scraping de services communautaires (API officielles uniquement), nom non trompeur.
- Code lisible, documenté, proche de PEP 8 : il est **relu à la main** avant inscription.
- Inscription par PR avec un unique fichier `plugins/EDRockMaster.json`. Champs requis : `pluginName`, `pluginVer`, `autoUpdateEnabled` et `autoInstallEnabled` (à `false` pour l'instant), `pluginAuthors`, `pluginMainLink`, `pluginLastUpdate`, `pluginDirName`, `pluginCategory` (au moins une parmi les catégories valides), `pluginDesc`, `pluginLastTestedEDMC`, `pluginLicense`. Recommandés : `pluginZip`, `pluginHash` (SHA-256 du zip) ; facultatifs : `pluginRequirements`, `pluginIcon`, `pluginVT` (analyse VirusTotal).
- Catégories envisagées : `Utility`, `Colonization`.

## Outils utiles d'EDMC

- **Killswitch hébergé** : `killswitch.get_kill_switches(target=URL)`, ou sa variante non bloquante `killswitch.get_kill_switch_thread` (rappel exécuté hors du fil principal), récupère un fichier de coupure publié par nous. Il permet de **désactiver à distance l'envoi** d'une version défectueuse du plugin.
- **Serveur de débogage HTTP** : lancé avec `--debug-sender edrockmaster`, EDMC redirige nos requêtes vers un serveur local qui les enregistre dans `$TEMP/EDMarketConnector/http_debug/`. Sert à tester l'envoi sans backend.

## Données de jeu à ne pas envoyer

- **Bêta** (`is_beta`) : serveurs de test de Frontier, données non représentatives.
- **Galaxie Legacy** (`gameversion` 3.x dans `LoadGame`) : galaxie séparée depuis la mise à jour 14 (fin 2022).

Le plugin fonctionne normalement dans ces deux cas ; seul l'envoi au serveur est coupé, et le panneau l'indique.

## Reste à vérifier

- Conditions d'utilisation de Frontier (CLUF, usage des journaux et de l'API CAPI), d'EDDN et de Spansh.
