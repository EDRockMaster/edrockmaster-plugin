# Journal des modifications

*[English](CHANGELOG.md) · Français*

Les changements notables du plugin EDRockMaster. Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et les versions suivent le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Modifié

- Panneau de chasse : la ligne des primes est masquée quand seules des obligations de combat ont été gagnées (zones de conflit).

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

[0.2.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.2.0
[0.1.0]: https://github.com/EDRockMaster/edrockmaster-plugin/releases/tag/v0.1.0
