# Journal des modifications

*[English](CHANGELOG.md) · Français*

Les changements notables du plugin EDRockMaster. Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et les versions suivent le [versionnage sémantique](https://semver.org/lang/fr/).

## [0.3.0] - 2026-10-06

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

[0.3.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.3.0
[0.2.2]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.2
[0.2.1]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.1
[0.2.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.1.0
