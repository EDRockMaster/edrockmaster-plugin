# Conception de l'application de bureau

*[English](design.md) · Français*

Conception d'EDRockMaster Companion, l'application de bureau (décision de conception ADR 0020, dans le dépôt d'architecture du projet) : elle lit le journal du jeu, calcule en direct le minage, le combat, le commerce et l'ingénierie, et les affiche dans sa propre fenêtre. Elle a remplacé le plugin EDMC, retiré avant d'avoir des joueurs (ADR 0024) ; le domaine et ses règles en viennent sans changement. Périmètre : **jalon 1, étape 1A** (en local, sans serveur), avec le combat, le commerce, l'ingénierie et la situation du commandant (ADR 0011, 0013 à 0015, 0017 à 0019, 0023). La liaison avec le serveur (étape 1B) est conçue ici pour ne pas avoir à reprendre 1A, mais elle n'est pas encore réalisée. Les règles d'ingénierie viennent de `edrockmaster-architecture`.

## Objectifs de l'étape 1A

- Assistance au minage en direct, sans serveur : alertes du prospecteur, cores, statistiques de session, drones.
- Interface bilingue (anglais, français), dans la langue du système ou celle choisie.
- Un enregistreur de journal (sur activation) qui transforme de vraies parties en jeux de données de test.
- Une structure prête pour la liaison avec le serveur : ports déjà définis, adaptateurs ajoutés en 1B.

Hors périmètre de 1A : envois, connexion, estimation de la valeur de la soute (elle demande les prix du serveur), overlay.

## Architecture

Hexagonale, comme les services :

```
edrockmaster/
  __init__.py                   VERSION
  domain/                       Python pur : pas d'entrées-sorties, pas d'interface
    journal_reading.py          noyau partagé : lecture tolérante des entrées du journal (ADR 0011)
    commodities.py              noyau partagé : noms des marchandises, normalisation, produits d'une raffinerie
    mining/                     contexte du minage
      journal.py                entrée du journal → fait de minage
      prospecting.py            astéroïde prospecté, politique d'alerte
      session.py                agrégat MiningTracker (cycle de vie, statistiques, ventes)
    combat/                     contexte du combat
      journal.py                entrée du journal → fait de combat
      sites.py                  sites de combat, tels que le jeu les nomme à l'arrivée
      session.py                agrégat CombatTracker (sessions par segments de site, bons, délits, objectifs communautaires)
    trade/                      contexte du commerce
      journal.py                entrée du journal → fait de commerce
      session.py                agrégat TradeTracker (sessions, routes, temps de vol, cargaison achetée, pertes)
    situation/                  la situation du commandant (ADR 0023) : qui, vaisseau, où, mode de jeu, escadrille
    engineering/                contexte de l'ingénierie (ADR 0017)
      journal.py                entrée du journal → fait d'ingénierie
      session.py                agrégat EngineeringTracker (inventaire, plafonds, collecte, objectifs, ingénieurs)
      catalogue.py              données du jeu : matériaux (grade, plafond), blueprints, effets, types de modules, ingénieurs
      catalogue.json            ces données, écrites par scripts/import_engineering_data.py (celles de Frontier, voir NOTICE)
      goals.py                  objectifs de blueprints et d'effets expérimentaux
  application/
    activity.py                 les activités : minage, combat, commerce, ingénierie
    build.py                    BuildInfo : version complète, commit et canal du build en cours (ADR 0016)
    companion.py                Companion : enregistre le journal une fois, transmet chaque entrée à chaque activité, détient les réglages
    settings.py                 PluginSettings (alertes, son, enregistreur, activités affichées) et leurs valeurs par défaut
    ports.py                    Clock, SettingsStore, Notifier, JournalRecorder, GoalRepository (et, en 1B, UploadQueue, Authenticator)
    mining_service.py           cas d'usage du minage : traiter une entrée, réinitialiser la session, appliquer les réglages
    combat_service.py           cas d'usage du combat : traiter une entrée, réinitialiser la session
    trade_service.py            cas d'usage du commerce : traiter une entrée, réinitialiser la session
    engineering_service.py      cas d'usage de l'ingénierie : journal, objectifs et leur stockage, réinitialisation
    situation_service.py        la situation du commandant
  infrastructure/
    settings_store.py           SettingsStore sur un stockage clé-valeur (clés préfixées « edrockmaster. »)
    settings_file.py            ce stockage : settings.json dans le dossier de données
    recorder_jsonl.py           JournalRecorder : fichiers JSONL dans le dossier de données
    database.py                 la base SQLite locale : ouverture, migrations, copie, mise de côté (ADR 0018)
    migrations.py               le schéma de la base, une migration par version
    goal_repository.py          GoalRepository sur la base locale
    catalogue_file.py           lit le catalogue d'ingénierie livré avec l'application
    build_file.py               lit edrockmaster/build.json, écrit par l'emballage
    sound.py                    Notifier : sons d'alerte, joués par la fonction de l'hôte
    strings_catalogue.py        les traductions du cœur (L10n/*.strings), les formats de nombres, la langue du système
    paths.py                    dossier de données selon la plateforme
    worker.py                   un fil alimenté par une file de tâches : le fil d'entrées-sorties, le fil du cœur
    clock.py                    Clock : heure système, UTC
  ui/                           présentateurs : notifications en entrée, textes en sortie, sans boîte à outils d'interface
    panel_model.py              PanelModel (textes d'un bloc), avis sur les données locales, mise en forme commune
    presenter.py                ActivityPresenter : les blocs des activités affichées
    mining_presenter.py         notifications du minage → PanelModel
    combat_presenter.py         notifications du combat → PanelModel
    trade_presenter.py          notifications du commerce → PanelModel
    engineering_presenter.py    notifications de l'ingénierie → PanelModel
    engineering_names.py        noms des matériaux, blueprints, effets, types de modules, ingénieurs et objectifs
    commodity_names.py          noms des marchandises minables connues avant que le journal les nomme
  desktop/                      l'application (ADR 0020) : sa racine de composition et sa fenêtre
    journal_folder.py           où le jeu écrit son journal ; les fichiers de journal dans l'ordre
    journal_reader.py           JournalFollower (suit le journal au fil de son écriture), JournalWatcher (son fil)
    core.py                     DesktopCore : la racine de composition, le fil du cœur, la vue en direct poussée
    live_view.py                la vue en direct, telle que la décrit schemas/live_view.schema.json
    engineering_view.py         la partie ingénierie de la vue en direct, le catalogue du formulaire d'objectif et de l'onglet Blueprints
    settings_view.py            le formulaire des réglages : ce qu'il affiche, ce qu'il demande
    demo.py                     le journal de démo (--demo)
    window.py                   la fenêtre pywebview, InterfaceApi, le point d'entrée (python -m edrockmaster.desktop)
    schemas/                    schémas JSON de ce que le cœur envoie à l'interface
    interface/index.html        l'interface, construite depuis web/ (hors de git)
L10n/fr.strings                 traductions françaises des textes du cœur
web/                            l'interface : Svelte 5 et TypeScript (ADR 0021)
```

Règle de dépendance : `domain` n'importe rien d'autre de l'application ; `application` importe `domain` ; `infrastructure` et `ui` importent `application` et `domain`, jamais la fenêtre ; `desktop` les assemble tous. `lint-imports` (dans la CI) le vérifie.

## Circulation des données

1. Le lecteur de journal (`JournalWatcher`, sur son propre fil) lit ce que le jeu a ajouté au fichier de journal courant, et dépose chaque entrée pour le fil du cœur.
2. Sur le fil du cœur, `DesktopCore` passe l'entrée à `Companion.handle_journal_entry(entry, is_beta)`, qui la copie dans le `JournalRecorder` (si l'enregistrement est activé), puis la transmet à chaque activité et à la situation. Chaque activité traduit le journal de son côté ; ci-dessous, le chemin du minage.
3. `domain/mining/journal.py` transforme l'entrée brute en fait typé (`AsteroidProspected`, `CommodityRefined`, `LimpetLaunched`, `RingEntered`…) ou l'ignore. Les événements et champs inconnus sont ignorés, jamais bloquants.
4. L'agrégat `MiningTracker` applique le fait et renvoie des notifications de session.
5. Le `ProspectingMonitor` évalue chaque astéroïde prospecté au regard des réglages d'alerte.
6. Le service transmet le résultat : l'alerte au `Notifier` (si le son est activé), et renvoie les notifications (`SessionStarted`, `SessionUpdated`, `SessionEnded`, `ProspectorAlertRaised`) à l'appelant, qui les passe à l'`ActivityPresenter`.
7. Le cœur construit la vue en direct et la pousse à l'interface.

Tout cela est du calcul pur sur de petits objets (bien moins d'une milliseconde par événement) : il reste sur le fil du cœur. Tout ce qui touche aux fichiers passe par le fil d'entrées-sorties.

`desktop/core.py` est la racine de composition : il construit les fils d'entrées-sorties et du cœur, les adaptateurs et le `Companion` au démarrage, et les arrête à la fermeture. Le bouton de réinitialisation de l'interface termine la session de son activité. Toute exception pendant le traitement d'une entrée est journalisée ; les entrées suivantes sont traitées normalement.

## Fils d'exécution

- **Fil principal** : la fenêtre de pywebview et sa boucle d'événements.
- **Fil du journal** (`EDRockMaster journal`) : `JournalWatcher` lit le journal toutes les secondes.
- **Fil du cœur** (`EDRockMaster core`, un `IoWorker` à lui) : tous les appels au companion, aux présentateurs et aux constructeurs de vues. Le fil du journal et les appels de l'interface ne font qu'y déposer des tâches ; il appelle `push`, qui ne doit pas bloquer.
- **Un fil d'entrées-sorties** (`infrastructure/worker.py`) : fil démon alimenté par une `queue.Queue` de tâches (ajout au fichier d'enregistrement, base locale, fichier des réglages ; en 1B, envois et authentification). Ce qu'il lit parvient au fil du cœur par une tâche déposée sur celui-ci.
- À la fermeture : le lecteur s'arrête, puis le fil du cœur ; la base se ferme dans une dernière tâche du fil d'entrées-sorties, qui s'arrête ensuite.

## Cycle de vie d'une session de minage

| Situation | Effet |
| --- | --- |
| `SupercruiseExit`, `Location` ou `StartUp` avec `BodyType` = `PlanetaryRing` | Anneau courant connu (nom, système) |
| Première activité de minage (`LaunchDrone` prospecteur, `ProspectedAsteroid`, `MiningRefined`) | Une session démarre s'il n'y en a pas en cours |
| `ProspectedAsteroid` | Astéroïde enregistré, politique d'alerte évaluée |
| `MiningRefined` | Une tonne de la commodité comptée |
| `LaunchDrone` | Drone compté par type |
| `AsteroidCracked` | Core fissuré |
| `Cargo` | Instantané de la soute : tonnes à bord, capacité utilisée |
| `EjectCargo` | Tonnes larguées comptées à part (hors production) |
| Aucune activité de minage pendant 10 minutes | Session en pause : le temps inactif n'est pas compté |
| `SupercruiseEntry`, `FSDJump`, `Docked`, `Shutdown`, `ShutDown` | Fin de la session |
| `StartUp` (écrit par EDMC, dans d'anciens enregistrements) | Anneau courant tiré de `Body`/`BodyType` de l'événement ; les chiffres de la soute arrivent avec le prochain événement `Cargo` (le jeu en écrit un à chaque raffinage) |
| `MarketSell` | Crédité à la session en cours, sinon à la dernière terminée : seulement ses tonnes minées ni éjectées ni encore vendues, au prix unitaire de la vente |
| Réinitialisation manuelle (bouton du bloc) | Fin de la session, une nouvelle peut démarrer |
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
| Récompense sans arrivée vue (le jeu a démarré sur le site : `StartUp`, `Location` hors station) | Un segment de type **inconnu**, depuis cette récompense ; divers si le commandant mine là (`ProspectedAsteroid`, `MiningRefined`, `AsteroidCracked`, drones de prospection ou de collecte) |
| `CommitCrime` pendant une session | Compté par type de délit : amendes et primes sur le commandant, jamais retirées des crédits |
| `Died` | La session se termine ; les bons non encaissés sont perdus |
| `Shutdown`, `ShutDown` | La session se termine |
| `RedeemVoucher` (primes, obligations de combat) | Les bons payés sont retirés, par faction, jamais en dessous de zéro |
| `CommunityGoal` | Les objectifs rejoints par le commandant : contribution, tranche de classement, palier atteint |
| Réinitialisation manuelle (bouton du bloc de combat) | La session se termine, une nouvelle peut commencer ; toujours sur le site, le segment suivant commence à la réinitialisation |

Statistiques d'une session de combat : ses segments (type de site, durée, victimes, crédits, ratios), une moyenne **par type de site, pondérée par le temps** (total des victimes et des crédits sur la durée totale), le temps sur les sites de combat, les victimes (et victimes partagées), les crédits de primes et d'obligations de combat, les victimes diverses, les délits. Affichés avec le bloc : les bons non encaissés (connus seulement depuis le début du fichier de journal : le journal ne redonne pas les plus anciens) et les objectifs communautaires. Les superpuissances écrites `$faction_Federation;` sont ramenées à `Federation`. Une autre activité ne termine jamais une session de combat : un mineur peut riposter et continuer de miner.

L'onglet *Activités* affiche un bloc par activité choisie par le joueur (*Réglages*), chacun avec son bouton **Réinitialiser** ([ADR 0013](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0013-combat-segments-and-live-panel.fr.md)) ; le bloc de la dernière activité qui a **progressé** est mis en évidence. Pour le combat, une session ou un segment qui commence ou se termine, une récompense ou un délit sont une progression ; quitter un site sans segment, les bons et les objectifs communautaires n'en sont pas. Pour le commerce, une session qui commence ou se termine, un achat, une vente ou une perte. Une activité masquée reste suivie : affichée de nouveau, elle est à jour.

## Commerce

Le commerce suit les achats et les ventes de marchandises sur les marchés ([ADR 0014](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0014-plugin-trade-activity.fr.md)). Son temps actif est le **temps de vol** : un **trajet** va du décollage à l'amarrage suivant, et compte dès qu'un échange le suit dans la session.

| Situation | Effet |
| --- | --- |
| Premier `MarketBuy`, ou premier `MarketSell` de marchandises achetées (`AvgPricePaid` supérieur à 0) | La session de commerce commence. Le vol jusqu'à ce marché ne compte pas |
| `MarketBuy` | Les marchandises sont à bord à leur coût ; le marché est l'origine de leur route (le dernier achat l'emporte) |
| `MarketSell` de marchandises achetées | Bénéfice `(SellPrice - AvgPricePaid) × Count`, celui du jeu, même pour des marchandises achetées avant le début du fichier de journal (origine inconnue). Compté sur la route : marchandise, marché d'achat, marché de vente |
| `MarketSell` avec `AvgPricePaid` à 0 | Non achetées : **commodités raffinées** si une raffinerie les produit (leur bénéfice revient au minage), **autres marchandises** sinon. Ni dans le bénéfice ni dans les ratios ; aucune session ne commence |
| `Undocked`, puis `Docked` | Un trajet. Il compte dès qu'un achat ou une vente de marchandises achetées le suit dans la session : une escale sans échange fait partie du vol, un vol après le dernier échange ne compte pas. Le temps à quai ne compte jamais |
| `Location` ou `StartUp` hors station | En vol depuis un moment inconnu : le trajet compte à partir de là |
| `EjectCargo` de marchandises achetées | Perte au prix payé, déduite du bénéfice |
| `CargoTransfer` vers un porte-vaisseaux, ou vers le vaisseau amarré à l'un d'eux ([ADR 0019](https://git.nexagone.io/EDRockMaster/edrockmaster-architecture/src/branch/main/docs/adr/0019-fleet-carrier-transfers.fr.md)) | Un **dépôt** ou un **retrait** : compté par marchandise et par direction, avec le nombre de transferts. Démarre la session et fait compter les trajets qui le précèdent, comme un achat ; ne rapporte rien. Les marchandises gardent leur coût et leur origine au porte-vaisseaux, et reviennent avec. Les transferts avec un SRV sont ignorés |
| `Cargo` | Les marchandises achetées parties sans vente (une mission) ne sont plus à bord : jamais plus que ce que le vaisseau transporte |
| `Died` | La cargaison achetée est perdue (une perte), la session se termine |
| `Shutdown`, `ShutDown` | La session se termine ; la cargaison reste connue |
| Réinitialisation manuelle (bouton du bloc de commerce) | La session se termine, une nouvelle peut commencer |

Statistiques d'une session de commerce : temps de vol, bénéfice (ventes moins pertes), bénéfice et tonnes par heure de vol, tonnes vendues, pertes, coût des marchandises achetées à bord, une ligne par route (tonnes, bénéfice, bénéfice par tonne, ventes), les transferts avec les porte-vaisseaux, commodités raffinées et autres marchandises. Dans le bloc, une route trop longue ne nomme que sa destination. Hors périmètre : le marché et le stock du porte-vaisseaux, la contrebande, les missions. Le commerce n'est pas envoyé au serveur.

## Ingénierie

En construction (décision de conception ADR 0017) : matériaux, ingénieurs et objectifs de blueprints, l'ingénierie des vaisseaux d'abord.

**Données du jeu.** Le journal nomme les matériaux (`chemicalmanipulators`), les blueprints (`FSD_LongRange`) et les effets expérimentaux (`special_fsd_heavy`), mais ne donne ni le grade d'un matériau, ni les ingrédients d'un blueprint, ni l'ingénieur qui le propose sur tel module. `scripts/import_engineering_data.py` les lit dans EDCD/FDevIDs et EDCD/coriolis-data à des commits épinglés et écrit `domain/engineering/catalogue.json`, une entrée par ligne pour des diffs lisibles ; `Catalogue.from_data` le vérifie à la lecture. Le script refuse un nom qu'il ne sait pas faire correspondre ; ses quelques corrections sont listées dans le script, chacune avec sa raison (une espace finale dans FDevIDs, des fautes de frappe dans coriolis-data). Il garde les types de modules qui ont des blueprints, les ingénieurs qui les proposent, et les effets qu'un ingénieur applique encore (les effets anciens n'ont pas d'ingrédients). Pour suivre une mise à jour du jeu : changer les commits épinglés, lancer le script, relire le diff du catalogue.

Les données appartiennent à Frontier et ne relèvent pas de la licence de l'application : `NOTICE`, livré avec l'application, le dit. Les noms sont en anglais dans le catalogue et traduits par `L10n/fr.strings` ; `tests/test_translations.py` vérifie que chaque nom a sa traduction. Les noms français des matériaux sont ceux du jeu, relevés dans un journal enregistré, quand ils sont connus.

**Le contexte.** `domain/engineering/journal.py` lit les événements des matériaux de vaisseau : `Materials` (tout l'inventaire, au chargement), `MaterialCollected`, `MaterialDiscarded`, `MaterialTrade`, `Synthesis`, `TechnologyBroker`, `EngineerContribution` (matériaux seulement), `ScientificResearch`, `MissionCompleted` (`MaterialsReward`), `EngineerCraft`, `EngineerProgress` (tous les ingénieurs au chargement, puis un à la fois) et `Shutdown`. `EngineeringTracker` (`session.py`) est l'agrégat :

- **Inventaire** : inconnu tant que `Materials` ne le donne pas (le lecteur de journal lit le fichier courant depuis son début, donc l'inventaire déclaré au chargement est connu même quand l'application démarre après le jeu). Chaque changement s'y applique, jamais en dessous de 0, jamais au-dessus du **plafond** du matériau (300 au grade 1, jusqu'à 100 au grade 5) : l'atteindre déclenche une alerte, car ce qui est collecté au-delà est perdu. Un matériau inconnu du catalogue (le jeu en ajoute avant les données communautaires) est compté, sans plafond. Jamais enregistré.
- **Collecte** : du premier changement de matériaux à `Shutdown` ou à la réinitialisation ; la mort ne la termine pas. Elle compte les matériaux collectés ou reçus en récompense par catégorie, ceux utilisés (passes, effets, synthèse, courtiers, contributions, recherche ; un échange ne fait que convertir), et ceux qui ont atteint leur plafond.
- **Objectifs** : un blueprint à un grade pour un type de module, avec un nombre de passes, ou un effet expérimental, avec un nombre d'applications. Ce qui manque à un objectif, ce sont ses ingrédients multipliés par ses passes, moins l'inventaire ; il est **prêt** quand il ne lui manque rien. La **liste de courses** additionne tous les objectifs. Les ingénieurs d'un objectif sont ceux, débloqués, qui proposent son grade sur son type de module. Un `EngineerCraft` retire une passe (ou une application, avec `ApplyExperimentalEffect`) au premier objectif de même blueprint et de même grade sur le même type de module, que `Catalogue.module_of` trouve à partir de l'objet (`int_powerdistributor_size7_class5` ; le blindage par son nom) ; un objectif à qui il ne reste rien est atteint et retiré. L'agrégat signale ces changements, et `EngineeringService` les enregistre par `GoalRepository` (base locale, ADR 0018) ; les objectifs enregistrés sont chargés au démarrage.
- **Ingénieurs** : statut et rang, d'après `EngineerProgress` (qui les nomme : le catalogue donne leurs identifiants).

**Bloc des activités.** Le bloc d'ingénierie affiche les matériaux gagnés par catégorie, utilisés, au plafond, et les objectifs prêts sur le total (ou que l'inventaire est inconnu). Son alerte est le dernier matériau au plafond, objectif prêt ou objectif atteint ; l'alerte d'un objectif prêt disparaît quand le joueur supprime l'objectif. Il progresse sur un changement de matériaux en jeu, un plafond ou un objectif prêt ; la déclaration du jeu au chargement n'est pas une progression. Les noms des matériaux sont ceux du jeu quand le journal les a donnés, sinon ceux du catalogue, traduits. Les onglets *Ingénierie* et *Blueprints* montrent le reste (plus bas, Application de bureau).

## Alertes du prospecteur

- Seuil par commodité, en pourcentage de l'astéroïde, modifiable. Valeurs par défaut (2026-10-03, à ajuster après l'essai en jeu) : platine 20 %, diamants basse température 20 %, painite 25 %, osmium 25 %, palladium 25 %, or 25 %. Teneur minimale faible, pas de réserve minimale, alerte sur les cores, son activé, enregistreur du journal désactivé.
- Niveau de teneur minimal (High, Medium, Low).
- Réserve restante minimale (`Remaining`), facultative.
- Un motherlode (core) déclenche sa propre alerte, quels que soient les seuils.
- Prospecter deux fois le même astéroïde (même composition à moins de 60 secondes d'intervalle) ne déclenche pas de seconde alerte.

## Interface

Onglet **Activités** : un bloc par activité affichée. Pour le minage : état (aucune session, minage dans un anneau, session terminée et pourquoi), la dernière alerte du prospecteur, mise en évidence jusqu'au prochain astéroïde prospecté, puis les statistiques : temps actif, tonnes raffinées, rendement, tonnes par commodité, astéroïdes prospectés et, dès qu'ils sont connus, cores, drones, soute et ventes. Les statistiques d'une session terminée restent affichées, et ses ventes s'y ajoutent. Un bouton **Réinitialiser** termine la session en cours. Les nombres s'écrivent comme la langue de l'interface les écrit.

Les autres onglets (*Ingénierie*, *Blueprints*, *Réglages*) et le bandeau de la situation du commandant sont décrits plus bas (Application de bureau).

## Réglages

Enregistrés dans `settings.json` du dossier de données (`infrastructure/settings_file.py`), clés préfixées par `edrockmaster.`, lus au démarrage et écrits par le fil d'entrées-sorties quand l'onglet *Réglages* les enregistre. Le domaine reçoit un objet de réglages immuable, jamais le stockage.

| Clé | Type | Contenu |
| --- | --- | --- |
| `edrockmaster.settings_version` | texte | Version du format des clés ci-dessous (`1`), pour de futures migrations |
| `edrockmaster.alert.thresholds` | texte | Objet JSON, clé de commodité → pourcentage (`{"painite": 25.0, …}`) |
| `edrockmaster.alert.minimum_content` | texte | `low`, `medium` ou `high` |
| `edrockmaster.alert.minimum_remaining` | texte | Pourcentage, ou vide si aucune |
| `edrockmaster.alert.cores` | booléen | Alerte sur les cores |
| `edrockmaster.sound` | booléen | Alertes sonores |
| `edrockmaster.record_journal` | booléen | Enregistreur du journal |
| `edrockmaster.display.activities` | texte | Liste JSON des activités affichées, au moins une (`["mining", "combat"]`) |
| `edrockmaster.display.offered` | texte | Liste JSON des activités proposées à l'enregistrement (`["mining", "combat", "trade"]`). Une activité ajoutée par une version ultérieure est affichée jusqu'à ce que le joueur la masque ; absente : minage et combat |
| `edrockmaster.display.mode` | texte | `last_active` ou `stacked` : gardée du panneau du plugin ; l'application affiche toutes les activités choisies |
| `edrockmaster.desktop.language` | texte | `auto` (celle du système), `en` ou `fr` |
| `edrockmaster.desktop.journal_folder` | texte | Le dossier du journal indiqué à la main ; vide : là où le jeu l'écrit |

Les valeurs sont lues une par une : une valeur absente ou invalide revient à sa propre valeur par défaut (et est journalisée), les autres sont conservées.

## Fichiers

Dossier de données :

- Windows : `%LOCALAPPDATA%\EDRockMaster` (non virtualisé par le paquet MSIX)
- Linux : `$XDG_DATA_HOME/EDRockMaster`, ou `~/.local/share/EDRockMaster`
- macOS : `~/Library/Application Support/EDRockMaster`

Contenu :

- `settings.json` : les réglages (ci-dessus) ;
- `logs/` : le journal technique, tournant ;
- `recordings/` : enregistrements du journal, JSONL, un fichier par lancement ;
- `edrockmaster.sqlite3` : la base locale (ci-dessous), avec ses fichiers `-wal` et `-shm` pendant que l'application tourne ;
- `edrockmaster.sqlite3.v<N>.bak` : une copie de la base faite avant sa dernière migration, depuis la version de schéma N ;
- `edrockmaster.sqlite3.unreadable-<date>` : une base que l'application n'a pas pu lire, mise de côté.

## Base locale

Un fichier SQLite pour l'**état** durable de l'application, qui n'est ni un réglage ni un enregistrement (décision de conception ADR 0018). Chaque besoin a ses tables et son port de dépôt : d'abord les objectifs d'ingénierie (`GoalRepository`, ADR 0017), la file d'envoi en 1B (ADR 0005). Rien de ce qu'elle contient n'est envoyé au serveur, sauf si un ADR le prévoit.

- **Le fil d'entrées-sorties seulement.** La base s'ouvre dans une tâche du fil d'entrées-sorties au démarrage, et se ferme dans une autre à la fermeture. `LocalDatabase.connection()` refuse tout autre fil. Les dépôts font de chaque appel une tâche ; ce qu'ils lisent parvient au fil du cœur par une tâche déposée sur celui-ci.
- **Schéma versionné.** `PRAGMA user_version` donne la version du schéma ; `infrastructure/migrations.py` liste les migrations, appliquées dans l'ordre à l'ouverture, chacune dans sa transaction, toujours vers l'avant. Une migration publiée ne change plus. Avant de migrer une base de version N > 0, le fichier est copié (API de sauvegarde de SQLite) dans `edrockmaster.sqlite3.v<N>.bak`, et les copies plus anciennes sont supprimées. Journal en mode WAL.
- **Fichier illisible.** Un fichier corrompu (SQLite dit que ce n'est pas une base, ou la vérification d'intégrité échoue) ou écrit par une version plus récente de l'application (retour à une version antérieure) est mis de côté sous le nom `edrockmaster.sqlite3.unreadable-<date UTC>`, et une base neuve est créée. Le journal technique dit pourquoi, et l'interface affiche un avis jusqu'à ce que le joueur l'ignore.
- **Base indisponible.** Tout autre échec (une autre instance tient le fichier, le disque le refuse, une migration échoue et est annulée) laisse le fichier tel quel ; rien n'est enregistré jusqu'au redémarrage de l'application, le journal dit pourquoi et l'interface le signale. L'application n'échoue jamais à cause de sa base.
- **Tests.** Chaque version du schéma a sa donnée de test, `tests/fixtures/database/schema-v<N>.sql`, gardée telle que publiée ; les tests migrent chacune jusqu'à la dernière version, et vérifient que la donnée de test la plus récente a le schéma que créent les migrations. Une nouvelle migration arrive donc avec sa donnée de test.

## Enregistreur de journal

- Désactivé par défaut ; activé dans l'onglet *Réglages*.
- Écrit chaque entrée lue par l'application, sans modification, un objet JSON par ligne, avec l'indicateur `is_beta` : `{"is_beta": false, "entry": {…}}`. Fichier : `recordings/journal-<début, UTC, AAAAMMJJTHHMMSSZ>-<version du build>.jsonl`, pour qu'un enregistrement dise quel build l'a compté.
- L'entrée est sérialisée dès sa lecture, puis écrite par le fil d'entrées-sorties.
- C'est à partir de ces enregistrements que l'on constitue `tests/fixtures/` ; le joueur décide de ce qu'il partage.
- Le dépôt est public, et un enregistrement brut contient des données personnelles (nom et identifiant Frontier du commandant, escadron, porte-vaisseaux, messages, noms d'autres joueurs, réputation). Un enregistrement ne devient donnée de test qu'à travers `scripts/sanitise_recording.py` : il garde les événements lus par l'application et quelques événements anodins, réduit `LoadGame` à la version du jeu, retire la réputation (`Factions` de `Location`, `FSDJump`, `StartUp`), le nom du pilote des cibles (`Bounty.PilotName`) et les victimes des délits (`CommitCrime.Victim`), événement par événement, remplace chaque porte-vaisseaux (nom, indicatif, identifiant) par une valeur neutre, et refuse d'écrire si le nom ou l'identifiant du commandant, ou un porte-vaisseaux, subsiste. `tests/test_replay.py` rejoue chaque jeu de données, avec des chiffres vérifiés à la main sur le journal brut.

## Internationalisation

- Les textes du cœur (les blocs des activités) : chaînes sources en anglais dans le code, passées par `tl()`, traduites par `infrastructure/strings_catalogue.py` depuis `L10n/fr.strings` (format `.strings` en UTF-8). Les textes propres à l'interface : catalogues JSON dans `web/src/locales/`, avec un test qui vérifie que chaque clé est traduite et utilisée.
- La langue est celle du système (langue de l'interface de Windows, ou variables de localisation), ou celle choisie dans *Réglages*, appliquée aussitôt : les présentateurs gardent des objets du domaine, pas des textes, et reconstruisent chaque texte dans la langue courante.
- Les décomptes évitent les accords au pluriel (`prospecteurs : 3`), que les fichiers `.strings` ne savent pas exprimer.
- `tests/test_translations.py` échoue si un texte passé à `tl()` n'a pas de traduction française, si une traduction n'est plus utilisée, ou si les espaces réservés diffèrent.
- Les noms de commodités viennent des champs `*_Localised` du journal quand ils sont présents (la langue du jeu), sinon de nos propres noms.

## Préparé pour l'étape 1B

Ports définis en 1A, réalisés en 1B :

- `UploadQueue` : ses propres tables dans la base locale (ADR 0018) ; chaque fait envoyable reçoit un identifiant client (`uuid4`).
- `Authenticator` : device flow de Keycloak ; jeton de rafraîchissement gardé dans le dossier de données.
- `Uploader` : lots (gzip) vers `edrockmaster-ingest`, sur le fil d'entrées-sorties, avec reprise progressive.
- Killswitch : par version (ADR 0016), relu toutes les 10 minutes depuis notre serveur.

## Application de bureau

Décision de conception ADR 0020 : le cœur dans une application à lui, qui lit lui-même le journal et affiche une interface web dans une fenêtre native. Le **lecteur de journal** est dans `desktop/` :

- **Dossier** : sous Windows, le dossier connu « Parties enregistrées » (Saved Games) du profil du joueur (où qu'il ait été déplacé), sinon `%USERPROFILE%\Saved Games`, puis `Frontier Developments\Elite Dangerous` ; sous Linux, le préfixe Proton du jeu (application Steam 359320) dans les dossiers Steam habituels. `EDROCKMASTER_JOURNAL_DIR` le fixe à la main.
- **Fichiers** : `Journal.<début>.<partie>.log` (et `JournalBeta.…`), triés par l'heure de début inscrite dans leur nom (deux formats, avant et depuis 2022), puis par partie.
- **Lecture** : la première relève lit le fichier courant **depuis son début** et transmet au cœur chaque entrée : l'application arrive aux mêmes chiffres que si elle tournait depuis le lancement du jeu. Ensuite, chaque relève lit ce qui a été ajouté ; une ligne incomplète attend la suite ; un fichier plus récent (nouvelle session, ou partie suivante d'une longue session) est suivi une fois le courant terminé. Une ligne qui n'est pas une entrée est journalisée et ignorée. Une bêta se reconnaît à son nom de fichier ou à sa version du jeu (`Fileheader`, `LoadGame`), comme EDMC la lisait.
- **Fil** : `JournalWatcher` relève toutes les secondes sur son propre fil (`EDRockMaster journal`), aussi souvent qu'EDMC le faisait quand le jeu tourne.
- **Soute** : depuis la 3.3 du jeu, l'événement `Cargo` du journal ne liste la soute du vaisseau qu'au chargement ; ensuite, la liste est dans `Cargo.json`, à côté des fichiers du journal. EDMC l'ajoutait à l'événement, et le minage (soute) comme le commerce (marchandises à bord) en dépendent : le lecteur l'ajoute aussi, quand `Cargo.json` décrit cet événement-là (même horodatage, le vaisseau), pour qu'un événement plus ancien lu au démarrage ne reçoive jamais la soute actuelle. Le jeu n'écrit pas toujours `Cargo.json` avant la ligne (en session réelle, une fois 22 ms après) : tant que le fichier décrit encore un événement antérieur, ou ne se lit pas en entier, le lecteur le relit toutes les 50 ms, une seconde au plus, puis le journalise. Sinon, l'événement est transmis tel que le jeu l'a écrit.
- **Parité** : `tests/desktop/test_parity.py` réécrit chaque donnée de test en fichiers de journal, les lit avec le lecteur, et vérifie que le cœur produit exactement les notifications du rejeu de la donnée de test, y compris pour une session découpée en parties écrites pendant que le lecteur suit. Lire 20 000 entrées au démarrage prend environ 0,1 s, 0,3 s avec le cœur.
- **Frontières** : `lint-imports` (dans la CI) vérifie que `domain/` et `application/` n'importent aucun adaptateur, aucun hôte ni aucune boîte à outils d'interface (`infrastructure`, `desktop`, `ui`, `webview`, `sqlite3`), que les présentateurs et les adaptateurs ignorent tout de la fenêtre, et que le domaine n'importe rien d'autre de l'application.

**La coquille de l'application** (ADR 0020, ADR 0021) :

- `desktop/core.py`, `DesktopCore` : la racine de composition. Le cœur (companion, base locale, objectifs, catalogue), alimenté par le lecteur de journal. Chaque appel au companion et au présentateur a lieu sur le **fil du cœur** (`EDRockMaster core`, un `IoWorker` à lui) ; le fil du lecteur de journal et les appels de l'interface ne font que déposer des tâches. Après chaque changement, le cœur pousse la **vue en direct** à l'interface.
- `desktop/live_view.py`, `desktop/schemas/live_view.schema.json` : la vue en direct, décrite par un schéma JSON : les activités affichées et leurs blocs (textes des présentateurs, déjà dans la langue du joueur), l'activité en cours, l'avis sur les données locales, le journal lu. Les tests valident chaque vue poussée contre le schéma ; les types TypeScript de l'interface en sont générés (`pnpm types`), et la CI vérifie qu'ils sont à jour.
- `desktop/window.py` : pywebview affiche l'interface, un seul fichier HTML autonome (`desktop/interface/index.html`, construit depuis `web/`, hors de git), remis comme une page : ni serveur, ni port. L'interface appelle le cœur par `InterfaceApi` (`window.pywebview.api` : `ready`, `reset`, `dismiss_notice`) ; le cœur pousse par `run_js`, en JSON ASCII (sous GTK, pywebview donne à WebKit la longueur d'un script en caractères et non en octets). pywebview crée `window.pywebview` avant d'y ajouter les appels du cœur : l'interface attend `pywebviewready`.
- Réglages dans `settings.json` du dossier de données (plus haut) ; un journal tournant dans `logs/` ; la langue de l'interface du système (Windows) ou des variables de localisation, l'anglais sinon ; les textes des présentateurs traduits depuis `L10n/*.strings`, les nombres écrits comme la langue les écrit.
- **Interface** (`web/`) : Svelte 5 et TypeScript, construite par Vite en un seul fichier HTML ; ses propres textes dans `src/locales/*.json`, avec un test qui vérifie que chaque clé est traduite et utilisée ; Vitest et Testing Library ; un thème sombre tiré de jetons de conception. Node 22 et pnpm (par corepack) ne sont que des outils de construction.
- **La lancer** (développement) : `cd web && corepack pnpm install && corepack pnpm build`, puis `uv run python -m edrockmaster.desktop` (`--debug` ouvre l'inspecteur web). Sous Linux, pywebview a besoin de GTK et de WebKit2GTK avec leur liaison Python (PyGObject), en général celle de la Python du système ; `EDROCKMASTER_JOURNAL_DIR` désigne un dossier de journal, par exemple un enregistrement réécrit en fichiers de journal. `uv run python -m edrockmaster.desktop --demo` (ou `EDRockMaster.exe --demo`, `--demo=en`, `--demo=fr`) lance la **démo** : voir plus bas.

**Réglages** (l'onglet *Réglages*) : les réglages du tableau plus haut (seuils d'alerte par marchandise, teneur minimale et réserve restante, cœurs, son, enregistrements du journal, activités affichées), et ceux propres à l'application : sa **langue** (celle du système par défaut ; les présentateurs traduisent par le cœur, donc une nouvelle langue s'applique aussitôt) et son **dossier du journal** (vide : là où le jeu l'écrit), pris en compte au prochain démarrage, car lire aussitôt un autre dossier compterait ses sessions en plus des sessions en cours. Le dossier indiqué par `EDROCKMASTER_JOURNAL_DIR` passe en premier, puis celui des réglages, puis l'habituel. `settings()` donne au formulaire son contenu (`settings.schema.json`), `save_settings()` le vérifie champ par champ (`desktop/settings_view.py`) et journalise ce qu'il refuse.

**La vue Ingénierie** (ADR 0017) : l'onglet *Ingénierie* de l'application de bureau, à la place de la fenêtre Tk prévue par l'ADR 0017. La partie `engineering` de la vue en direct (`desktop/engineering_view.py`) porte les matériaux par catégorie et par grade avec leur nombre et leur plafond, les ingénieurs de vaisseau (statut, rang ; nommés dans la langue du joueur, par `L10n/`, car certains portent un titre comme *Professor Palin*), les objectifs avec ce qui manque à chacun et les ingénieurs débloqués qui le proposent (les objectifs prêts d'abord), et la liste de courses. Les ingénieurs s'affichent en lignes courtes, nom et statut côte à côte, les débloqués marqués, avec leur nombre ; un bouton replie la liste pour la session. Le formulaire d'objectif demande une fois le catalogue au cœur (`catalogue()`, schéma `goal_catalogue.schema.json`) : types de modules, leurs blueprints avec leurs grades, leurs effets expérimentaux. L'interface ajoute, modifie (passes, applications) et supprime des objectifs (`add_goal`, `change_goal`, `remove_goal`) ; le cœur vérifie un nouvel objectif d'après le catalogue et le domaine, journalise ce qu'il refuse, et enregistre les objectifs dans la base locale (ADR 0018).

**La situation du commandant** (ADR 0023) : `domain/situation/` lit `Commander`, `LoadGame`, `Location`, les sauts et le supercruise, `Docked`, `Undocked`, `Loadout`, `ShipyardSwap`, `SetUserShipName`, `Embark`, `Disembark` et les événements d'escadrille, pour en tirer le nom du commandant, le vaisseau (son type dans la langue du jeu, le nom et l'immatriculation donnés par le joueur), à pied ou non, le système, la station, le mode de jeu avec le nom du groupe privé, et les membres de l'escadrille. `Shutdown` garde la dernière situation et indique que le jeu est fermé. Elle vit en mémoire seulement : jamais enregistrée, jamais envoyée ; l'application l'affiche dans un bandeau, par le champ `situation` de la vue en direct. Les membres de l'escadrille sont d'autres joueurs : le script de nettoyage des enregistrements les nomme `Wingmate 1`, `Wingmate 2`…

**La démo** (`--demo`, `desktop/demo.py`) : l'application lit un journal d'exemple au lieu de celui du joueur, pour les captures d'écran du Store et la documentation, ou pour la découvrir sans jouer. `scripts/make_demo_journal.py` l'écrit (`desktop/demo_journal.jsonl`, dont un test vérifie qu'il est à jour) à partir de jeux de données publiés : une session de minage dans un site d'extraction de ressources avec ses obligations de combat, sous le nom du **commandant fictif Jameson** en jeu ouvert, à bord du *Rock Hound*, avec les matériaux, les ingénieurs et les matériaux collectés du jeu de données d'ingénierie ; il s'arrête alors que le commandant mine encore. Au démarrage, ses horodatages sont décalés pour qu'il se termine maintenant : les sessions de minage, de combat et d'ingénierie sont en cours. La démo est dans la langue du système, ou dans celle qu'elle nomme (`--demo=en`, `--demo=fr`) ; le journal a été enregistré avec le jeu en français : pour une démo en anglais, les noms que le jeu écrit dans sa langue et que l'application affiche tels quels (marchandises, teneur des astéroïdes, objectif communautaire) sont remplacés par ceux du jeu en anglais, les noms des matériaux donnés par le jeu sont retirés pour que le catalogue les nomme, et chaque capture est dans une seule langue. Ses réglages et objectifs vivent dans un dossier temporaire supprimé à la fermeture : ceux du joueur ne sont ni lus ni modifiés ; le journal technique reste le même et indique « Demo mode » et sa langue. `EDROCKMASTER_JOURNAL_DIR` est ignorée.

**L'onglet Blueprints** (ADR 0017) : les données du jeu à parcourir, sans passer par un objectif. Une recherche (nom d'un module, d'un blueprint ou d'un effet, ou d'un matériau qu'il demande : à quoi sert un matériau ; sans tenir compte de la casse ni des accents) et un filtre par type de module ; chaque blueprint affiche un grade à la fois (le plus haut d'abord) : ses ingrédients face à l'inventaire, en stock ou manquants, le nombre de passes que l'inventaire permet, et les ingénieurs qui proposent ce grade, les débloqués d'abord avec leur rang ; les effets expérimentaux de chaque module affichent leurs ingrédients et le nombre d'applications possibles. Un bouton ajoute le grade ou l'effet aux objectifs (`add_goal`, une passe). L'appel du catalogue (`catalogue()`) porte, pour chaque blueprint, une recette par grade (ingrédients, identifiants des ingénieurs) et, pour chaque effet, ses ingrédients, nommés dans la langue du cœur : l'onglet le redemande quand la langue change. La recherche et les calculs sont dans `web/src/lib/blueprints.ts`.

**Emballage pour Windows** (ADR 0022) : le Microsoft Store distribue l'application en paquet MSIX, qu'il signe.

- `.github/workflows/windows.yml` s'exécute sur le **miroir GitHub seulement** (`windows-latest` ; Gitea lit `.gitea/workflows/` et l'ignore), sans secret : il construit l'interface, rejoue les tests Python sous Windows, décide du plan de release, emballe, **lance l'application emballée sur un journal enregistré**, puis en démo (son journal doit dire que l'interface est prête et le journal du jeu lu, sans erreur), et garde les paquets 14 jours.
- `scripts/package_desktop.py` (sous Windows) : le fichier de build (ADR 0016), les icônes (`scripts/make_icons.py`, un rocher provisoire en attendant une icône dessinée), PyInstaller (`packaging/windows/EDRockMaster.spec` : un dossier, sans console, sans Tk), le **zip portable** `EDRockMaster-v<version>-windows.zip` (non signé : SmartScreen avertit), et le **MSIX** `EDRockMaster-v<version>.msix` avec `makeappx` (`packaging/windows/AppxManifest.xml.in` : confiance totale, `%LOCALAPPDATA%\EDRockMaster` non virtualisé pour que les données survivent à une réinstallation et que le joueur les trouve).
- L'identité du paquet vient des variables du dépôt GitHub `EDROCKMASTER_MSIX_NAME`, `EDROCKMASTER_MSIX_PUBLISHER` et `EDROCKMASTER_MSIX_PUBLISHER_NAME`, telles que Partner Center les donne pour le nom réservé, et `EDROCKMASTER_MSIX_DISPLAY_NAME`, le nom réservé lui-même, que le Store exige comme nom affiché du paquet ; sans elles, une identité de développement.
- Versions du paquet (`scripts/release_plan.py`) : `X.Y.(Z×100+N).0` pour la candidate N, `X.Y.(Z×100+99).0` pour la production, `X.Y.(Z×100).0` pour une construction de développement. Une candidate part au Store en package flight vers les testeurs ; la production est reconstruite depuis le commit de la candidate. La soumission se fait à la main dans Partner Center pour l'instant.
- `scripts/fixture_to_journal.py` réécrit une donnée de test en fichier de journal, pour essayer l'application à la main.

## Tests

- **Domaine et application : en TDD**, avec `pytest` seul.
- **Jeux de données** : extraits de vrais journaux (`tests/fixtures/*.jsonl`), enregistrés avec l'enregistreur.
- **Tests de rejeu** : une session enregistrée complète est rejouée dans `Companion` et les présentateurs, et les statistiques finales, vérifiées à la main sur le journal brut, sont contrôlées ; les tests de parité relisent les mêmes jeux de données par le lecteur de journal.
- **Application** : le cœur avec un faux `push`, la fenêtre avec une doublure de pywebview, les vues validées contre leurs schémas JSON ; vérifiée dans une vraie fenêtre (GTK/WebKit sous Linux, WebView2 dans le test de fumée du runner Windows).
- **Interface** : Vitest et Testing Library, sa logique dans `web/src/lib/` testée seule.
- CI : `ruff`, `mypy --strict`, `lint-imports`, `pytest` avec couverture sur `domain/`, `application/`, `ui/` et `desktop/` ; lint, vérification des types, tests et construction de l'interface.

