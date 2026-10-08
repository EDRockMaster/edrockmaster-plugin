# Conception du plugin

*[English](design.md) · Français*

Conception du plugin EDMC d'EDRockMaster. Périmètre : **jalon 1, étape 1A** (plugin local, premier essai en jeu), plus les activités de combat et de commerce (décisions de conception ADR 0011, ADR 0013, ADR 0014 et ADR 0015, dans le dépôt d'architecture du projet). La liaison avec le serveur (étape 1B) est conçue ici pour ne pas avoir à reprendre 1A, mais elle n'est pas encore réalisée. Les contraintes viennent des [prérequis](prerequisites.fr.md) ; les règles d'ingénierie, de `edrockmaster-architecture`.

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
    commodities.py              noyau partagé : noms des commodités, normalisation, commodités issues du raffinage
    mining/                     contexte du minage
      journal.py                entrée du journal → fait du minage
      prospecting.py            astéroïde prospecté, politique d'alerte
      session.py                agrégat MiningTracker (cycle de vie, statistiques, ventes)
    combat/                     contexte du combat
      journal.py                entrée du journal → fait du combat
      sites.py                  sites de combat, tels que le jeu les nomme à l'arrivée
      session.py                agrégat CombatTracker (sessions par segments de site, bons, délits, objectifs communautaires)
    trade/                      contexte du commerce
      journal.py                entrée du journal → fait du commerce
      session.py                agrégat TradeTracker (sessions, routes, temps de vol, cargaison achetée, pertes)
    engineering/                contexte de l'ingénierie (ADR 0017)
      journal.py                entrée du journal → fait de l'ingénierie
      session.py                agrégat EngineeringTracker (inventaire, plafonds, collecte, objectifs, ingénieurs)
      catalogue.py              données du jeu : matériaux (grade, plafond), blueprints, effets, types de modules, ingénieurs
      catalogue.json            ces données, écrites par scripts/import_engineering_data.py (propriété de Frontier, voir NOTICE)
      goals.py                  objectifs de blueprint et d'effet expérimental
  application/
    activity.py                 les activités : minage, combat, commerce
    build.py                    BuildInfo : version complète, commit et canal du build en cours (ADR 0016)
    companion.py                Companion : enregistre le journal une fois, passe chaque entrée à chaque activité, porte les réglages
    settings.py                 PluginSettings (alertes, son, enregistreur) et leurs valeurs par défaut
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder, GoalRepository (et, en 1B, UploadQueue, Authenticator)
    mining_service.py           cas d'usage du minage : traiter une entrée du journal, réinitialiser la session, appliquer les réglages
    combat_service.py           cas d'usage du combat : traiter une entrée du journal, réinitialiser la session
    trade_service.py            cas d'usage du commerce : traiter une entrée du journal, réinitialiser la session
    engineering_service.py      cas d'usage de l'ingénierie : journal, objectifs et leur enregistrement, réinitialisation
  infrastructure/
    settings_edmc.py            SettingsStore sur le config d'EDMC (clés préfixées « edrockmaster. »)
    recorder_jsonl.py           JournalRecorder : fichiers JSONL dans le dossier de données
    database.py                 la base SQLite locale : ouverture, migrations, copie, mise de côté (ADR 0018)
    migrations.py               le schéma de la base, une migration par version
    goal_repository.py          GoalRepository sur la base locale
    catalogue_file.py           lit le catalogue d'ingénierie livré avec le plugin
    build_file.py               lit edrockmaster/build.json, écrit par l'emballage
    sound.py                    Notifier : alertes sonores (winsound sous Windows, cloche Tk ailleurs)
    paths.py                    dossier de données selon le système
    worker.py                   l'unique fil d'entrées-sorties du plugin et sa file
    clock.py                    Clock : heure système, en UTC
  desktop/                      l'application de bureau (ADR 0020), en construction : elle lit le journal sans EDMC
    journal_folder.py           où le jeu écrit son journal ; les fichiers du journal dans l'ordre
    journal_reader.py           JournalFollower (suit le journal au fil de l'écriture du jeu), JournalWatcher (son fil)
    core.py                     DesktopCore : la racine de composition, le fil du cœur, la vue en direct poussée
    live_view.py                la vue en direct, telle que la décrit schemas/live_view.schema.json
    window.py                   la fenêtre pywebview, InterfaceApi, le point d'entrée (python -m edrockmaster.desktop)
  edmc/
    plugin.py                   assemblage : construit le graphe d'objets, implémente les hooks
    i18n.py                     tl() relié au l10n d'EDMC, avec un repli pour les tests
    host.py                     services d'EDMC (theme, plug.show_error, l10n.Locale), avec replis
    main_thread.py              résultats du fil d'entrées-sorties exécutés sur le fil principal
    state.py                    inventaire et ingénieurs tirés de l'état d'EDMC, quand le plugin démarre après le jeu
  ui/
    panel_model.py              PanelModel (textes), avis sur les données locales et mise en forme commune, sans tkinter
    presenter.py                ActivityPresenter : les blocs à afficher, selon le mode
    mining_presenter.py         notifications du minage → PanelModel
    combat_presenter.py         notifications du combat → PanelModel
    trade_presenter.py          notifications du commerce → PanelModel
    engineering_presenter.py    notifications de l'ingénierie → PanelModel
    engineering_names.py        noms des matériaux, blueprints, effets, types de modules et objectifs
    preferences_form.py         réglages <-> champs des préférences, validation, sans tkinter
    commodity_names.py          noms des commodités minables connues avant que le journal ne les nomme
    panel.py                    panneau de la fenêtre principale (tkinter, fil principal uniquement), un bloc par activité affichée
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
- **Un fil d'entrées-sorties** (`infrastructure/worker.py`) : fil démon alimenté par une `queue.Queue` de tâches (ajout au fichier d'enregistrement, base locale ; en 1B, envois et authentification). Il ne touche jamais à tkinter.
- **Retour des résultats au fil principal** (`edmc/main_thread.py`) : le fil d'entrées-sorties dépose une fonction dans une file, et le fil principal l'exécute en relevant la file toutes les 100 ms avec `after()` sur le panneau. Réveiller le fil principal par `event_generate()` depuis le fil d'entrées-sorties, comme EDMC le fait pour ses propres fils, demande que la boucle principale de Tk tourne, or EDMC appelle `plugin_app` avant de la lancer : la relève ne fait aucun appel à Tk depuis le fil d'entrées-sorties. Les fonctions déposées avant que le panneau existe l'attendent.
- `plugin_stop()` ferme la base locale, dépose une tâche d'arrêt, attend la fin du fil avec un délai maximal, et vide l'enregistreur.

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

## Combat

Le combat couvre la chasse à la prime, les zones de conflit et toute victime ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.fr.md), [ADR 0015](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0015-unnamed-and-ground-conflict-zones.fr.md)). Il se mesure en **segments** : un séjour sur un site de combat, de l'arrivée (en vaisseau ou à pied) au départ.

| Situation | Effet |
| --- | --- |
| `Bounty` (format vaisseau avec `Rewards`, ou format simple pour les skimmers et à pied) | Une victime ; crédits de prime ; un bon de prime par faction payeuse |
| `FactionKillBond` | Une victime ; crédits et bon d'obligation de combat |
| `CapShipBond` | Crédits et bon d'obligation de combat, sans victime |
| Première récompense | La session de combat commence |
| `SupercruiseDestinationDrop` puis `SupercruiseExit` | Arrivée à une destination. Un site de combat si son type est connu : zone de conflit (faible, moyenne, forte), site d'extraction de ressources (pauvre, normal, riche, dangereux), balise de navigation |
| `SupercruiseExit` sans destination (anneau, planète, espace profond), `Undocked` | Arrivée quelque part que le journal ne nomme pas comme site de combat |
| `ApproachSettlement` | La colonie est retenue jusqu'au prochain départ |
| `DropshipDeploy` (Frontline Solutions) | Arrivée à pied dans une **zone de conflit au sol**, avec le nom de la colonie ; un redéploiement après une défaite prolonge le séjour |
| `Disembark` à la surface d'une planète | Arrivée à pied, non nommée comme site de combat |
| Première récompense sur un site de combat | Un segment s'ouvre, **depuis l'arrivée** : la recherche de cibles compte |
| `SupercruiseEntry`, `Docked`, `FSDJump`, `StartJump` vers l'hyperespace, `BookDropship` en retraite, `Embark` | Départ : le segment se ferme ; la session continue. Un site quitté sans aucune récompense ne compte pas. `Embark` hors station est une nouvelle arrivée, en vaisseau |
| `FactionKillBond` hors de tout segment | Une obligation de combat n'existe qu'en zone de conflit : un segment s'ouvre depuis la dernière arrivée (depuis l'obligation si aucune n'a été vue). En vaisseau : **zone de conflit, intensité inconnue** ; à pied : **zone de conflit au sol** |
| Prime ailleurs (un pirate pendant le minage, près d'une station, après une interdiction) : une prime ne dit rien du lieu | **Divers** : comptée dans les victimes, les crédits et les bons, dans aucun ratio |
| Récompense sans arrivée vue (EDMC ou le jeu a démarré sur le site : `StartUp`, `Location` hors station) | Un segment de type **inconnu**, depuis cette récompense ; divers si le commandant mine là (`ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`, drones de prospection ou de collecte) |
| `CommitCrime` pendant une session | Compté par type de délit : amendes et primes sur le commandant, jamais retirées des crédits |
| `Died` | La session se termine ; les bons non encaissés sont perdus |
| `Shutdown`, `ShutDown` | La session se termine |
| `RedeemVoucher` (primes, obligations de combat) | Les bons payés sont retirés, par faction, jamais en dessous de zéro |
| `CommunityGoal` | Les objectifs rejoints par le commandant : contribution, tranche de classement, palier atteint |
| Réinitialisation manuelle (bouton du panneau, combat affiché) | La session se termine, une nouvelle peut commencer ; toujours sur le site, le segment suivant commence à la réinitialisation |

Statistiques d'une session de combat : ses segments (type de site, durée, victimes, crédits, ratios), une moyenne **par type de site, pondérée par le temps** (total des victimes et des crédits sur la durée totale), le temps sur les sites de combat, les victimes (et victimes partagées), les crédits de primes et d'obligations de combat, les victimes diverses, les délits. Communs au panneau : les bons non encaissés (connus seulement depuis le lancement d'EDMC : le journal ne redonne pas les plus anciens) et les objectifs communautaires. Les superpuissances écrites `$faction_Federation;` sont ramenées à `Federation`. Une autre activité ne termine jamais une session de combat : un mineur peut riposter et continuer de miner.

Le panneau affiche les activités choisies par le joueur (préférences, **Affichage**), selon l'un de deux modes ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.fr.md)) :

- **dernière activité active** (par défaut) : un seul bloc, la dernière activité affichée qui a **progressé**. Pour le combat, une session ou un segment qui commence ou se termine, une récompense ou un délit ; quitter un site sans segment, les bons et les objectifs communautaires ne le font jamais basculer. Pour le commerce, une session qui commence ou se termine, un achat, une vente ou une perte. Une activité masquée ne prend jamais le panneau ;
- **toutes, empilées** : un bloc par activité affichée, le minage, le combat puis le commerce, chacun avec son bouton **Réinitialiser**.

Une activité masquée reste suivie : affichée de nouveau, elle est à jour.

## Commerce

Le commerce suit les achats et les ventes de marchandises sur les marchés ([ADR 0014](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0014-plugin-trade-activity.fr.md)). Son temps actif est le **temps de vol** : un **trajet** va du décollage à l'amarrage suivant, et compte dès qu'un échange le suit dans la session.

| Situation | Effet |
| --- | --- |
| Premier `MarketBuy`, ou premier `MarketSell` de marchandises achetées (`AvgPricePaid` supérieur à 0) | La session de commerce commence. Le vol jusqu'à ce marché ne compte pas |
| `MarketBuy` | Les marchandises sont à bord à leur coût ; le marché est l'origine de leur route (le dernier achat l'emporte) |
| `MarketSell` de marchandises achetées | Bénéfice `(SellPrice - AvgPricePaid) × Count`, celui du jeu, même pour des marchandises achetées avant le lancement d'EDMC (origine inconnue). Compté sur la route : marchandise, marché d'achat, marché de vente |
| `MarketSell` avec `AvgPricePaid` à 0 | Non achetées : **commodités raffinées** si une raffinerie les produit (leur bénéfice revient au minage), **autres marchandises** sinon. Ni dans le bénéfice ni dans les ratios ; aucune session ne commence |
| `Undocked`, puis `Docked` | Un trajet. Il compte dès qu'un achat ou une vente de marchandises achetées le suit dans la session : une escale sans échange fait partie du vol, un vol après le dernier échange ne compte pas. Le temps à quai ne compte jamais |
| `Location` ou `StartUp` hors station | En vol depuis un moment inconnu : le trajet compte à partir de là |
| `EjectCargo` de marchandises achetées | Perte au prix payé, déduite du bénéfice |
| `CargoTransfer` vers un porte-vaisseaux, ou vers le vaisseau amarré à l'un d'eux ([ADR 0019](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0019-fleet-carrier-transfers.fr.md)) | Un **dépôt** ou un **retrait** : compté par marchandise et par direction, avec le nombre de transferts. Démarre la session et fait compter les trajets qui le précèdent, comme un achat ; ne rapporte rien. Les marchandises gardent leur coût et leur origine au porte-vaisseaux, et reviennent avec. Les transferts avec un SRV sont ignorés |
| `Cargo` | Les marchandises achetées parties sans vente (une mission) ne sont plus à bord : jamais plus que ce que le vaisseau transporte |
| `Died` | La cargaison achetée est perdue (une perte), la session se termine |
| `Shutdown`, `ShutDown` | La session se termine ; la cargaison reste connue |
| Réinitialisation manuelle (bouton du panneau, commerce affiché) | La session se termine, une nouvelle peut commencer |

Statistiques d'une session de commerce : temps de vol, bénéfice (ventes moins pertes), bénéfice et tonnes par heure de vol, tonnes vendues, pertes, coût des marchandises achetées à bord, une ligne par route (tonnes, bénéfice, bénéfice par tonne, ventes), les transferts avec les porte-vaisseaux, commodités raffinées et autres marchandises. Sur le panneau, une route trop longue pour la fenêtre d'EDMC ne nomme que sa destination. Hors périmètre : le marché et le stock du porte-vaisseaux, la contrebande, les missions. Le commerce n'est pas envoyé au serveur.

## Ingénierie

En construction (décision de conception ADR 0017) : matériaux, ingénieurs et objectifs de blueprints, l'ingénierie des vaisseaux d'abord.

**Données du jeu.** Le journal nomme les matériaux (`chemicalmanipulators`), les blueprints (`FSD_LongRange`) et les effets expérimentaux (`special_fsd_heavy`), mais ne donne ni le grade d'un matériau, ni les ingrédients d'un blueprint, ni l'ingénieur qui le propose sur tel module. `scripts/import_engineering_data.py` les lit dans EDCD/FDevIDs et EDCD/coriolis-data à des commits épinglés et écrit `domain/engineering/catalogue.json`, une entrée par ligne pour des diffs lisibles ; `Catalogue.from_data` le vérifie à la lecture. Le script refuse un nom qu'il ne sait pas faire correspondre ; ses quelques corrections sont listées dans le script, chacune avec sa raison (une espace finale dans FDevIDs, des fautes de frappe dans coriolis-data). Il garde les types de modules qui ont des blueprints, les ingénieurs qui les proposent, et les effets qu'un ingénieur applique encore (les effets anciens n'ont pas d'ingrédients). Pour suivre une mise à jour du jeu : changer les commits épinglés, lancer le script, relire le diff du catalogue.

Les données appartiennent à Frontier et ne relèvent pas de la licence du plugin : `NOTICE`, livré dans le zip, le dit. Les noms sont en anglais dans le catalogue et traduits par `L10n/fr.strings` ; `tests/test_translations.py` vérifie que chaque nom a sa traduction. Les noms français des matériaux sont ceux du jeu, relevés dans un journal enregistré, quand ils sont connus.

**Le contexte.** `domain/engineering/journal.py` lit les événements des matériaux de vaisseau : `Materials` (tout l'inventaire, au chargement), `MaterialCollected`, `MaterialDiscarded`, `MaterialTrade`, `Synthesis`, `TechnologyBroker`, `EngineerContribution` (matériaux seulement), `ScientificResearch`, `MissionCompleted` (`MaterialsReward`), `EngineerCraft`, `EngineerProgress` (tous les ingénieurs au chargement, puis un à la fois) et `Shutdown`. `EngineeringTracker` (`session.py`) est l'agrégat :

- **Inventaire** : inconnu tant que `Materials` ou l'état d'EDMC ne le donne pas (`edmc/state.py` : quand le plugin démarre après le jeu, EDMC ne lui transmet aucun événement passé ; son `state` est lu après chaque entrée tant que l'inventaire est inconnu, et inclut déjà cette entrée). Chaque changement s'y applique, jamais en dessous de 0, jamais au-dessus du **plafond** du matériau (300 au grade 1, jusqu'à 100 au grade 5) : l'atteindre déclenche une alerte, car ce qui est collecté au-delà est perdu. Un matériau inconnu du catalogue (le jeu en ajoute avant les données communautaires) est compté, sans plafond. Jamais enregistré.
- **Collecte** : du premier changement de matériaux à `Shutdown` ou à la réinitialisation ; la mort ne la termine pas. Elle compte les matériaux collectés ou reçus en récompense par catégorie, ceux utilisés (passes, effets, synthèse, courtiers, contributions, recherche ; un échange ne fait que convertir), et ceux qui ont atteint leur plafond.
- **Objectifs** : un blueprint à un grade pour un type de module, avec un nombre de passes, ou un effet expérimental, avec un nombre d'applications. Ce qui manque à un objectif, ce sont ses ingrédients multipliés par ses passes, moins l'inventaire ; il est **prêt** quand il ne lui manque rien. La **liste de courses** additionne tous les objectifs. Les ingénieurs d'un objectif sont ceux, débloqués, qui proposent son grade sur son type de module. Un `EngineerCraft` retire une passe (ou une application, avec `ApplyExperimentalEffect`) au premier objectif de même blueprint et de même grade sur le même type de module, que `Catalogue.module_of` trouve à partir de l'objet (`int_powerdistributor_size7_class5` ; le blindage par son nom) ; un objectif à qui il ne reste rien est atteint et retiré. L'agrégat signale ces changements, et `EngineeringService` les enregistre par `GoalRepository` (base locale, ADR 0018) ; les objectifs enregistrés sont chargés au démarrage.
- **Ingénieurs** : statut et rang, d'après `EngineerProgress` ou l'état d'EDMC (qui les nomme : le catalogue donne leurs identifiants).

**Panneau.** Le bloc d'ingénierie affiche les matériaux gagnés par catégorie, utilisés, au plafond, et les objectifs prêts sur le total (ou que l'inventaire est inconnu). Son alerte est le dernier matériau au plafond, objectif prêt ou objectif atteint. Il progresse sur un changement de matériaux en jeu, un plafond ou un objectif prêt ; la déclaration du jeu au chargement n'est pas une progression. Les noms des matériaux sont ceux du jeu quand le journal les a donnés, sinon ceux du catalogue, traduits. La fenêtre séparée (inventaire, ingénieurs, objectifs) vient ensuite.

## Alertes du prospecteur

- Seuil par commodité, en pourcentage de l'astéroïde, modifiable. Valeurs par défaut (2026-10-03, à ajuster après l'essai en jeu) : platine 20 %, diamants basse température 20 %, painite 25 %, osmium 25 %, palladium 25 %, or 25 %. Teneur minimale faible, pas de réserve minimale, alerte sur les cores, son activé, enregistreur du journal désactivé.
- Niveau de teneur minimal (High, Medium, Low).
- Réserve restante minimale (`Remaining`), facultative.
- Un motherlode (core) déclenche sa propre alerte, quels que soient les seuils.
- Prospecter deux fois le même astéroïde (même composition à moins de 60 secondes d'intervalle) ne déclenche pas de seconde alerte.

## Interface

**Panneau** (fenêtre principale d'EDMC) : état (aucune session, minage dans un anneau, session terminée et pourquoi), la dernière alerte du prospecteur, mise en évidence jusqu'au prochain astéroïde prospecté, puis les statistiques : temps actif, tonnes raffinées, rendement, tonnes par commodité, astéroïdes prospectés et, dès qu'ils sont connus, cores, drones, soute et ventes. Les statistiques d'une session terminée restent affichées, et ses ventes s'y ajoutent. Un bouton **Réinitialiser** termine la session en cours. Les nombres suivent les réglages régionaux du système, comme ceux d'EDMC.

**Onglet des préférences** : un champ de pourcentage par commodité minable (vide : pas d'alerte), teneur minimale, réserve minimale, alerte sur les cores, son, enregistreur du journal, les activités affichées et le mode d'affichage, et un bouton qui ouvre le dossier des enregistrements ; il se termine par la version complète du build. Au moins une activité reste affichée. Les nombres se saisissent selon les réglages régionaux du système. À la fermeture de la fenêtre, une saisie invalide garde sa valeur précédente et est citée dans la barre d'état d'EDMC ; les saisies valides sont appliquées tout de suite.

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
| `edrockmaster.display.activities` | texte | Liste JSON des activités affichées, au moins une (`["mining", "combat"]`) |
| `edrockmaster.display.offered` | texte | Liste JSON des activités que l'onglet proposait à l'enregistrement (`["mining", "combat", "trade"]`). Une activité ajoutée par une version ultérieure est affichée jusqu'à ce que le joueur la masque ; absente (enregistré par la 0.3.0) : minage et combat |
| `edrockmaster.display.mode` | texte | `last_active` ou `stacked` |

Les valeurs sont lues une à une : une valeur absente ou invalide reprend sa propre valeur par défaut (avec un avertissement dans le journal), les autres sont conservées.

## Fichiers

Dossier de données, hors du dossier du plugin pour survivre aux mises à jour du plugin :

- Windows : `%LOCALAPPDATA%\EDRockMaster`
- Linux : `$XDG_DATA_HOME/EDRockMaster`, ou `~/.local/share/EDRockMaster`
- macOS : `~/Library/Application Support/EDRockMaster`

Contenu :

- `recordings/` : enregistrements du journal, JSONL, un fichier par lancement d'EDMC ;
- `edrockmaster.sqlite3` : la base locale (ci-dessous), avec ses fichiers `-wal` et `-shm` pendant qu'EDMC tourne ;
- `edrockmaster.sqlite3.v<N>.bak` : copie de la base faite avant sa dernière migration, depuis la version de schéma N ;
- `edrockmaster.sqlite3.unreadable-<date>` : une base que le plugin n'a pas pu lire, mise de côté.

## Base locale

Un fichier SQLite pour l'**état** durable du plugin, qui n'est ni un réglage (le `config` d'EDMC) ni un enregistrement (décision de conception ADR 0018). Chaque besoin a ses tables et son port de dépôt : d'abord les objectifs d'ingénierie (`GoalRepository`, ADR 0017), la file d'envoi en 1B (ADR 0005). Rien de ce qu'elle contient n'est envoyé au serveur, sauf si un ADR le prévoit.

- **Le fil d'entrées-sorties seulement.** La base s'ouvre dans une tâche du fil d'entrées-sorties à `plugin_start3`, et se ferme dans une autre à `plugin_stop`. `LocalDatabase.connection()` refuse tout autre fil. Les dépôts font de chaque appel une tâche ; ce qu'ils lisent parvient au fil principal par `edmc/main_thread.py`.
- **Schéma versionné.** `PRAGMA user_version` donne la version du schéma ; `infrastructure/migrations.py` liste les migrations, appliquées dans l'ordre à l'ouverture, chacune dans sa transaction, toujours vers l'avant. Une migration publiée ne change plus. Avant de migrer une base de version N > 0, le fichier est copié (API de sauvegarde de SQLite) dans `edrockmaster.sqlite3.v<N>.bak`, et les copies plus anciennes sont supprimées. Journal en mode WAL.
- **Fichier illisible.** Un fichier corrompu (SQLite dit que ce n'est pas une base, ou la vérification d'intégrité échoue) ou écrit par une version plus récente du plugin (retour à une version antérieure) est mis de côté sous le nom `edrockmaster.sqlite3.unreadable-<date UTC>`, et une base neuve est créée. Le journal d'EDMC dit pourquoi, et le panneau affiche un avis jusqu'à ce que le joueur l'ignore.
- **Base indisponible.** Tout autre échec (un autre EDMC tient le fichier, le disque le refuse, une migration échoue et est annulée) laisse le fichier tel quel ; rien n'est enregistré jusqu'au redémarrage d'EDMC, le journal dit pourquoi et le panneau le signale. Le plugin n'échoue jamais à cause de sa base.
- **Tests.** Chaque version du schéma a sa donnée de test, `tests/fixtures/database/schema-v<N>.sql`, gardée telle que publiée ; les tests migrent chacune jusqu'à la dernière version, et vérifient que la donnée de test la plus récente a le schéma que créent les migrations. Une nouvelle migration arrive donc avec sa donnée de test.

## Enregistreur de journal

- Désactivé par défaut ; activé dans les préférences (« Enregistrer le journal pour le débogage »).
- Écrit chaque entrée reçue par le plugin, sans modification, un objet JSON par ligne, avec l'indicateur `is_beta` : `{"is_beta": false, "entry": {…}}`. Fichier : `recordings/journal-<début, UTC, AAAAMMJJTHHMMSSZ>-<version du build>.jsonl`, pour qu'un enregistrement dise quel build l'a compté.
- L'entrée est sérialisée dès sa réception (EDMC partage le même dict avec tous les plugins), puis écrite par le fil d'entrées-sorties.
- C'est à partir de ces enregistrements que l'on constitue `tests/fixtures/` ; le joueur décide de ce qu'il partage.
- Le dépôt est public, et un enregistrement brut contient des données personnelles (nom et identifiant Frontier du commandant, escadron, porte-vaisseaux, messages, noms d'autres joueurs, réputation). Un enregistrement ne devient donnée de test qu'à travers `scripts/sanitise_recording.py` : il garde les événements lus par le plugin et quelques événements anodins, réduit `LoadGame` à la version du jeu, retire la réputation (`Factions` de `Location`, `FSDJump`, `StartUp`), le nom du pilote des cibles (`Bounty.PilotName`) et les victimes des délits (`CommitCrime.Victim`), événement par événement, remplace chaque porte-vaisseaux (nom, indicatif, identifiant) par une valeur neutre, et refuse d'écrire si le nom ou l'identifiant du commandant, ou un porte-vaisseaux, subsiste. `tests/test_replay.py` rejoue chaque jeu de données, avec des chiffres vérifiés à la main sur le journal brut.

## Internationalisation

- Textes source en anglais dans le code, passés par `tl()` (`edmc/i18n.py`, relié à `l10n.translations.tl` avec `context=__file__`).
- Français dans `L10n/fr.strings` (format `.strings`, UTF-8).
- Les textes affichés sont rafraîchis dans `prefs_changed` : le présentateur garde des objets du domaine, pas des textes, et reconstruit chaque texte dans la langue courante.
- Les décomptes évitent l'accord au pluriel (`prospecteurs : 3`), que les fichiers `.strings` ne savent pas exprimer.
- `tests/test_translations.py` échoue si un texte passé à `tl()` n'a pas de traduction française, si une traduction ne sert plus, ou si les paramètres diffèrent.
- Les noms de commodités viennent des champs `*_Localised` du journal quand ils existent (la langue du jeu), sinon de nos propres noms.

## Préparé pour l'étape 1B

Ports définis en 1A, réalisés en 1B :

- `UploadQueue` : ses propres tables dans la base locale (ADR 0018) ; chaque fait envoyable reçoit un identifiant client (`uuid4`).
- `Authenticator` : device flow Keycloak ; refresh token stocké avec `config`.
- `Uploader` : lots (gzip) vers `edrockmaster-ingest`, sur le fil d'entrées-sorties, avec reprise progressive.
- Killswitch : module `killswitch` d'EDMC, relu toutes les 10 minutes depuis notre serveur.
- Galaxie au `StartUp` : il n'y a pas de `LoadGame` dans ce cas, la version du jeu doit donc être lue dans `state["GameVersion"]` pour distinguer Live et Legacy.

## Application de bureau

En construction (décision de conception ADR 0020) : le cœur du plugin dans une application à lui, qui lit le journal sans EDMC et affiche une interface web dans une fenêtre native. L'étape 1, le **lecteur de journal**, est dans `desktop/` :

- **Dossier** : sous Windows, le dossier connu « Parties enregistrées » (Saved Games) du profil du joueur (où qu'il ait été déplacé), sinon `%USERPROFILE%\Saved Games`, puis `Frontier Developments\Elite Dangerous` ; sous Linux, le préfixe Proton du jeu (application Steam 359320) dans les dossiers Steam habituels. `EDROCKMASTER_JOURNAL_DIR` le fixe à la main.
- **Fichiers** : `Journal.<début>.<partie>.log` (et `JournalBeta.…`), triés par l'heure de début inscrite dans leur nom (deux formats, avant et depuis 2022), puis par partie.
- **Lecture** : la première relève lit le fichier courant **depuis son début** et transmet au cœur chaque entrée : contrairement à EDMC, qui garde les entrées passées pour son propre état et ne transmet aux plugins que les nouvelles, l'application arrive aux mêmes chiffres que si elle tournait depuis le lancement du jeu (son état n'a alors besoin d'aucun `state` d'un hôte). Ensuite, chaque relève lit ce qui a été ajouté ; une ligne incomplète attend la suite ; un fichier plus récent (nouvelle session, ou partie suivante d'une longue session) est suivi une fois le courant terminé. Une ligne qui n'est pas une entrée est journalisée et ignorée. Une bêta se reconnaît à son nom de fichier ou à sa version du jeu (`Fileheader`, `LoadGame`), comme EDMC la lit.
- **Fil** : `JournalWatcher` relève toutes les secondes sur son propre fil (`EDRockMaster journal`), aussi souvent qu'EDMC le fait quand le jeu tourne.
- **Parité** : `tests/desktop/test_parity.py` réécrit chaque donnée de test en fichiers de journal, les lit avec le lecteur, et vérifie que le cœur produit exactement les notifications du rejeu par EDMC, y compris pour une session découpée en parties écrites pendant que le lecteur suit. Lire 20 000 entrées au démarrage prend environ 0,1 s, 0,3 s avec le cœur.
- **Frontières** : `lint-imports` (dans la CI) vérifie que `domain/` et `application/` n'importent aucun adaptateur, aucun hôte ni aucune boîte à outils d'interface (`infrastructure`, `edmc`, `desktop`, `ui`, `tkinter`, `webview`, `sqlite3`), et que le domaine n'importe rien d'autre du plugin.

**Étape 2, la coquille de l'application** (ADR 0020, ADR 0021) :

- `desktop/core.py`, `DesktopCore` : la racine de composition de l'application de bureau, comme `edmc/plugin.py` est celle du plugin. Le même cœur (companion, base locale, objectifs, catalogue), alimenté par le lecteur de journal. Chaque appel au companion et au présentateur a lieu sur le **fil du cœur** (`EDRockMaster core`, un `IoWorker` à lui) ; le fil du lecteur de journal et les appels de l'interface ne font que déposer des tâches. Après chaque changement, le cœur pousse la **vue en direct** à l'interface.
- `desktop/live_view.py`, `desktop/schemas/live_view.schema.json` : la vue en direct, décrite par un schéma JSON : les activités affichées et leurs blocs (textes des présentateurs du plugin, déjà dans la langue du joueur), l'activité en cours, l'avis sur les données locales, le journal lu. Les tests valident chaque vue poussée contre le schéma ; les types TypeScript de l'interface en sont générés (`pnpm types`), et la CI vérifie qu'ils sont à jour.
- `desktop/window.py` : pywebview affiche l'interface, un seul fichier HTML autonome (`desktop/interface/index.html`, construit depuis `web/`, hors de git), remis comme une page : ni serveur, ni port. L'interface appelle le cœur par `InterfaceApi` (`window.pywebview.api` : `ready`, `reset`, `dismiss_notice`) ; le cœur pousse par `run_js`, en JSON ASCII (sous GTK, pywebview donne à WebKit la longueur d'un script en caractères et non en octets). pywebview crée `window.pywebview` avant d'y ajouter les appels du cœur : l'interface attend `pywebviewready`.
- Réglages dans `settings.json` du dossier de données, lus et vérifiés comme ceux du plugin (mêmes clés) ; un journal tournant dans `logs/` ; la langue de l'interface du système (Windows) ou des variables de localisation, l'anglais sinon ; les textes des présentateurs traduits depuis `L10n/*.strings`, les nombres écrits comme la langue les écrit.
- `lint-imports` vérifie aussi que `desktop/` et `infrastructure/` n'importent ni EDMC ni Tk.
- **Interface** (`web/`) : Svelte 5 et TypeScript, construite par Vite en un seul fichier HTML ; ses propres textes dans `src/locales/*.json`, avec un test qui vérifie que chaque clé est traduite et utilisée ; Vitest et Testing Library ; un thème sombre tiré de jetons de conception. Node 22 et pnpm (par corepack) ne sont que des outils de construction.
- **La lancer** (développement) : `cd web && corepack pnpm install && corepack pnpm build`, puis `uv run python -m edrockmaster.desktop` (`--debug` ouvre l'inspecteur web). Sous Linux, pywebview a besoin de GTK et de WebKit2GTK avec leur liaison Python (PyGObject), en général celle de la Python du système ; `EDROCKMASTER_JOURNAL_DIR` désigne un dossier de journal, par exemple un enregistrement réécrit en fichiers de journal.

## Tests

- **Domaine et application : en TDD**, avec `pytest` seul, sans EDMC.
- **Jeux de données** : extraits de vrais journaux (`tests/fixtures/*.jsonl`), enregistrés avec l'enregistreur.
- **Tests de rejeu** : une session enregistrée complète est rejouée dans `Companion` et le présentateur du panneau, et les statistiques finales, vérifiées à la main sur le journal brut, sont contrôlées.
- **Adaptateurs EDMC** : testés avec de faux modules `config`, `l10n` et `theme` injectés par `tests/conftest.py`.
- **Interface** : le présentateur et le formulaire des préférences sont purs et entièrement testés. Les widgets tkinter restent minces ; leurs tests utilisent un vrai Tk et sont sautés là où il n'y a pas d'affichage (CI), ils tournent donc sur les postes des développeurs. Vérifiée en jeu pendant le test 1A.
- CI : `ruff`, `mypy --strict`, `pytest` avec couverture sur `domain/` et `application/`.
