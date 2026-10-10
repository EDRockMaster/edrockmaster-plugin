# Journal des modifications

*[English](CHANGELOG.md) · Français*

Les changements notables d'EDRockMaster Companion, l'application de bureau (jusqu'à la 0.3.0, le plugin EDMC). Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et les versions suivent le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Ajouté

- **L'ingénierie à pied** (ADR 0027, ADR 0029), première partie. L'onglet *Ingénierie* gagne une partie *À pied* : les matériaux à pied détenus (objets, composants, données, consommables), d'après le casier du vaisseau et le sac tels que le jeu les donne, avec ce qui est dans le sac et ce qui est détenu pour des missions à part ; les combinaisons et armes vues, avec leur classe ; les 13 ingénieurs à pied et leur statut. Le bloc des *Activités* compte les matériaux à pied gagnés, par sorte, et ceux perdus à une mort. Les objets volés comptent comme ceux du joueur. Sur une vraie soirée, l'inventaire après chaque retour à bord égale celui du jeu.
- **Votre porte-vaisseaux** : les matériaux à pied déplacés entre le casier du vaisseau et votre propre porte-vaisseaux n'écrivent aucun événement dans le journal du jeu ; la partie *À pied* montre chaque déplacement, et rappelle que les matériaux déplacés ne comptent plus. Le contenu du porte-vaisseaux viendra de Frontier par les services d'EDRockMaster (ADR 0028).

### Corrigé

- Un casier du vaisseau que le jeu n'a écrit que dans `ShipLocker.json` est maintenant lu dans ce fichier, comme la soute l'est dans `Cargo.json`.

## [0.4.0] - 2026-10-10

La première version d'**EDRockMaster Companion**, l'application de bureau, qui remplace le plugin EDMC.

### Ajouté

- **L'application de bureau** (décisions de conception ADR 0020 et ADR 0021) : EDRockMaster dans sa propre fenêtre, sans EDMC. Elle lit elle-même le journal du jeu, depuis le début du fichier courant, pour arriver aux mêmes chiffres que si elle tournait depuis le lancement du jeu, et suit le jeu au fil de son écriture. Sa version complète s'affiche à côté de son nom (`0.4.0`, `0.4.0-rc.1` pour une candidate). Onglets *Activités*, *Ingénierie*, *Blueprints* et *Réglages* ; en français et en anglais, dans la langue du système ou celle choisie ; rien n'écoute sur le réseau et rien n'est envoyé nulle part. Distribuée par le Microsoft Store (ADR 0022), et en zip portable pour les testeurs.
- **La situation du commandant** (ADR 0023) : un bandeau avec le commandant, le vaisseau (type, nom et immatriculation), le système et la station, le mode de jeu avec le nom du groupe privé, et l'escadrille.
- **Le commerce** (ADR 0014) : une nouvelle activité. Une session de commerce commence au premier achat. Son bénéfice est celui du jeu, `(SellPrice - AvgPricePaid) × Count`, même pour des marchandises achetées avant le début du fichier de journal ; ses ratios ne comptent que le **temps de vol**, du décollage à l'amarrage suivant, quand un échange le suit. Son bloc affiche le bénéfice, le bénéfice par heure, les tonnes vendues, le coût de la cargaison achetée et une ligne par route (marchandise, marché d'achat, marché de vente). Sur une vraie session de trois allers-retours entre Amano Terminal et Verne Venture : 164 316 218 CR en 1 h 21 min 50 s de vol, 120,5 M CR/h. Les marchandises vendues sans avoir été achetées sont comptées à part : **commodités raffinées** (leur bénéfice reste au minage) et **autres marchandises** ; les marchandises achetées larguées ou perdues avec le vaisseau sont une perte.
- **Transferts avec un porte-vaisseaux** (ADR 0019) : dépôts et retraits par marchandise, avec le nombre de transferts, pour voir tout de suite un dépôt que le jeu n'a pas pris en compte (un bug connu du jeu). Un transfert démarre une session de commerce et fait compter son vol ; les marchandises déposées ne sont pas comptées comme perdues si le vaisseau est détruit ensuite.
- **L'ingénierie** (ADR 0017) : une nouvelle activité. Elle suit l'inventaire des matériaux de vaisseau, donné par le jeu au chargement, et chaque changement : collecte, récompense, abandon, échange, synthèse, don à un courtier, à un ingénieur ou à la recherche, passe d'ingénieur. Son bloc affiche les matériaux gagnés par catégorie, utilisés, et ceux qui ont atteint leur plafond, avec une alerte, car ce qui est collecté au-delà est perdu, et combien d'objectifs sont prêts. L'onglet *Ingénierie* affiche l'inventaire par catégorie et par grade avec chaque plafond, les ingénieurs (statut et rang, repliables), les **objectifs de blueprints** (un blueprint et un grade pour un type de module, avec un nombre de passes, ou un effet expérimental) avec ce qui manque à chacun et les ingénieurs débloqués qui le proposent, et la liste de courses de tous les objectifs ; on y ajoute, modifie et supprime les objectifs, et une passe en jeu en décompte une. Sur une vraie session : 39 matériaux collectés, cinq passes de *Grande capacité de charge* sur un distributeur d'énergie, les ingrédients de chaque passe conformes au catalogue.
- **L'onglet Blueprints** : les blueprints de chaque module, grade par grade, face à l'inventaire (en stock, manquants, passes possibles), avec les ingénieurs qui proposent chaque grade ; les effets expérimentaux avec leurs ingrédients ; une recherche par module, blueprint, effet ou matériau (à quoi sert un matériau) ; chaque grade ou effet peut être ajouté aux objectifs.
- **Catalogue d'ingénierie** (ADR 0017) : les données du jeu pour l'ingénierie des vaisseaux (137 matériaux avec leur grade et leur plafond, 81 blueprints, 86 effets expérimentaux, 44 types de modules, 25 ingénieurs), importées de EDCD/FDevIDs et EDCD/coriolis-data, avec leurs noms traduits en français ; les noms français des matériaux sont ceux du jeu. Ces données appartiennent à Frontier Developments : le nouveau fichier `NOTICE` le dit.
- **L'onglet Réglages** : seuils d'alerte par commodité, teneur minimale et réserve restante, cores, son, enregistrements du journal, activités affichées, langue, et le dossier du journal quand celui du jeu n'est pas là où on le trouve d'habitude, avec le fichier du journal en cours de lecture ; des boutons ouvrent les dossiers des enregistrements du journal et des logs, pour les envoyer avec un signalement de bogue.
- **Base locale** (ADR 0018) : `edrockmaster.sqlite3` dans le dossier de données, pour ce qui doit être gardé d'un lancement à l'autre, à commencer par les objectifs d'ingénierie. Son schéma est migré au démarrage, après une copie du fichier. Un fichier que l'application ne peut pas lire, parce qu'il est abîmé ou écrit par une version plus récente, est mis de côté sous le nom `edrockmaster.sqlite3.unreadable-<date>`, une base neuve est créée, et l'interface le signale jusqu'à ce qu'on l'ignore.
- **Mode démo** (`--demo`, `--demo=en`, `--demo=fr`) : un journal d'exemple sous le nom du commandant fictif Jameson, pour des captures d'écran ou pour découvrir l'application sans jouer ; les réglages et objectifs du joueur ne sont pas touchés.
- Le script de nettoyage des enregistrements conserve les achats, les transferts de cargaison, les événements des matériaux et des ingénieurs, et réduit une mission terminée à sa récompense en matériaux.

### Retiré

- **Le plugin EDMC** (ADR 0024) : retiré avant d'avoir des joueurs. Sa dernière version, la 0.2.2, reste sur GitHub ; il n'en aura plus d'autre. Ses réglages ne sont pas importés : l'application a les siens.

## [0.3.0] - non publiée

Candidates seulement, de `0.3.0-rc.1` à `0.3.0-rc.3` (du 2026-10-05 au 2026-10-06), pour la recette par les testeurs : le plugin EDMC a été retiré avant que cette version n'arrive chez les joueurs (ADR 0024).

### Modifié

- **La chasse à la prime devient le combat**, mesuré par site (décision de conception ADR 0013, dans le dépôt d'architecture du projet). Un **segment** est un séjour sur un site de combat (zone de conflit, site d'extraction de ressources, balise de navigation), de l'arrivée au départ ; il s'ouvre à la première récompense et compte la recherche depuis l'arrivée. Le panneau affiche le site en cours et, pour chaque type de site, les victimes et crédits par heure, pondérés par le temps. Un site quitté sans aucune récompense ne compte pas.
- Le temps passé ailleurs en espace normal ne compte plus comme du combat : dans une vraie session, 52 minutes de minage après deux zones de conflit affichaient 1 h 44 min et 664 594 CR/h ; les zones seules font 49 min 19 s et 1 403 083 CR/h.
- Le panneau ne bascule sur le combat que lorsqu'il progresse (une récompense, un segment qui commence ou se termine, un délit) : quitter un anneau après le minage ne ramène plus une session de combat terminée depuis des heures.

### Ajouté

- **Réglages d'affichage** (préférences, *Affichage* ; décision de conception ADR 0013) : les activités que montre le panneau, et le mode, soit la **dernière activité active** (comme avant, par défaut), soit **toutes, empilées**, chacune avec son bouton *Réinitialiser*. Une activité masquée reste suivie, et elle est à jour quand on l'affiche de nouveau.
- Victimes **diverses** : une victime hors de tout site de combat (un pirate pendant le minage, près d'une station) compte dans les victimes, les crédits et les bons, mais dans aucun ratio. Le temps de minage n'est jamais du temps de combat, et le minage ne termine jamais une session de combat.
- **Amendes** et **primes sur vous** pendant une session de combat, jamais retirées de ce qui a été gagné.
- Types de sites de combat confirmés en jeu (4.4.1.1) : zones de conflit (faible, moyenne, forte), sites d'extraction de ressources (pauvre, normal, riche, dangereux), balise de navigation.
- Le script de nettoyage des enregistrements garde les arrivées sur site et les délits, retire la réputation des sauts et les victimes des délits, et remplace les porte-vaisseaux (nom, indicatif, identifiant).
- **Zones de conflit au sol** (Odyssey, décision de conception ADR 0015) : la navette de Frontline Solutions ouvre un segment, sa retraite le ferme, et le panneau affiche la colonie. Lors d'une vraie soirée à Redonesses, deux zones au sol ont donné 35 victimes, à 68,1 victimes/h et 1 309 320 CR/h.
- **Zones de conflit que le journal ne nomme pas** : une obligation de combat n'existe qu'en zone de conflit, donc une obligation hors de tout site ouvre un segment depuis l'arrivée, d'intensité inconnue en vaisseau. Ce même soir, 45 victimes sur 77 n'auraient sinon eu aucun ratio.
- Le script de nettoyage garde les déplacements à pied (colonies, navette, débarquement, embarquement) et retire les tueurs du commandant.
- **Identité de build** (décision de conception ADR 0016) : chaque zip dit quel build il est, par exemple `0.3.0-rc.3`, dans le log d'EDMC au démarrage, en bas de l'onglet des préférences et dans le nom des enregistrements du journal. Les builds de la CI sont `0.3.0-dev+<commit>`.

### Corrigé

- L'onglet des préférences ne s'affichait plus dans EDMC depuis la 0.3.0-rc.2 : les réglages d'affichage mélangeaient deux placements Tk dans un même cadre, ce que refusent les cadres d'EDMC.

## [0.2.2] - 2026-10-03

### Corrigé

- Rendement de la chasse : le temps actif est désormais le **temps sur site** (en espace normal hors des stations, depuis l'arrivée sur le site de la première récompense). La recherche de cibles compte ; les trajets et l'amarrage non. Une recherche de 20 minutes entre deux primes était écartée, ce qui affichait 36 M CR/h au lieu de 10 M CR/h sur une vraie session.
- Les primes sont maintenant vérifiées sur une vraie session (jeu 4.4.1.1) : victimes, récompenses payées par plusieurs factions et encaissement par faction correspondent au jeu.

## [0.2.1] - 2026-10-03

### Modifié

- Panneau de chasse : quand seules des obligations de combat sont gagnées, l'état affiche **Zone de conflit** et la ligne des primes, vide, est masquée.
- Vérifié sur une vraie session en zone de conflit (jeu 4.4.1.1) : obligations de combat, temps actif, encaissement et objectif communautaire correspondent au jeu. Les primes elles-mêmes restent à vérifier en jeu.

## [0.2.0] - 2026-10-03

### Ajouté

- **Chasse à la prime** (décision de conception ADR 0011, dans le dépôt d'architecture du projet) : une session de chasse commence à la première prime ou obligation de combat et se termine à la mort, à la sortie du jeu ou avec **Réinitialiser** ; l'amarrage et les sauts ne la terminent pas. Statistiques : temps actif (pauses de plus de 15 minutes exclues), victimes et victimes partagées, primes, obligations de combat, crédits par heure. Bons non encaissés, perdus en cas de mort. Objectifs communautaires : contribution, tranche de classement, palier atteint.
- Le panneau montre l'activité en cours, minage ou chasse à la prime ; **Réinitialiser** agit sur elle.

### Limites connues

- Les bons non encaissés ne sont connus qu'à partir du lancement d'EDMC : le journal du jeu ne redonne pas les plus anciens.
- Le compteur de chasse n'a pas encore été vérifié sur une vraie session de chasse : activez l'enregistreur du journal en chassant et signalez tout chiffre faux.

## [0.1.0] - 2026-10-03

Première version, pour le premier essai en jeu. Le plugin fonctionne seul, sans aucun serveur.

### Ajouté

- **Alertes du prospecteur** : un seuil par commodité, en pourcentage de l'astéroïde. Valeurs par défaut : platine et diamants basse température 20 %, painite, osmium, palladium et or 25 %. S'y ajoutent une teneur minimale, une réserve minimale facultative, une alerte sur les cores (filons-mères) et un son. Un astéroïde prospecté deux fois en moins de 60 secondes ne déclenche qu'une alerte.
- **Sessions de minage** : une session commence à la première activité de minage et se termine au passage en supercroisière, au saut, à l'amarrage, à la sortie du jeu ou avec le bouton **Réinitialiser**. Le temps actif exclut les pauses de plus de 10 minutes. Statistiques : tonnes par commodité, tonnes par heure, raffinages, astéroïdes prospectés, cores trouvés et fissurés, drones lancés, soute. Les ventes des tonnes minées après la session s'y ajoutent (tonnes et crédits).
- **Panneau** dans la fenêtre principale d'EDMC et **onglet de préférences** dans ses paramètres.
- **Français et anglais**, selon la langue d'EDMC, sans redémarrage.
- **Enregistreur du journal** (désactivé par défaut) : garde une copie des événements du journal dans des fichiers JSONL, pour constituer des données de test et signaler des bogues.
- EDMC lancé alors que le jeu tourne déjà : l'anneau courant est connu.

### Limites connues

- Pas encore de liaison avec les services d'EDRockMaster (connexion, envois) : prévue pour la version suivante.
- Pas de valeur estimée de la soute : elle demande les prix du serveur.
- Pas encore vérifiés : le thème sombre d'EDMC, le son d'alerte sous Windows.

[0.4.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.4.0
[0.2.2]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2
[0.2.1]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.1
[0.2.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.1.0
