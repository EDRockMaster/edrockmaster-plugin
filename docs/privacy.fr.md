# Politique de confidentialité — EDRockMaster Companion

*[English](privacy.md) · Français*

Dernière mise à jour : 9 octobre 2026. S'applique à l'application de bureau EDRockMaster Companion et au plugin EDRockMaster pour EDMarketConnector, publiés par Nexagone.

## En bref

EDRockMaster lit le journal qu'Elite Dangerous écrit sur votre ordinateur, calcule les statistiques de vos sessions **sur votre ordinateur**, et **n'envoie rien nulle part**. Ni compte, ni mesure d'audience, ni publicité, ni pistage.

## Ce que l'application lit

Elite Dangerous écrit un journal de votre partie dans votre dossier *Parties enregistrées* (Saved Games). EDRockMaster le lit, sans le modifier, pour afficher vos sessions de minage, de combat, de commerce et d'ingénierie. Ce journal contient notamment :

- le nom de votre commandant, votre vaisseau (type, nom et immatriculation que vous lui avez donnés), votre position (système, station) et votre mode de jeu (ouvert, solo, groupe privé et son nom) ;
- ce que vous avez fait : astéroïdes prospectés, marchandises raffinées, achats et ventes, victimes et primes, matériaux collectés, travaux des ingénieurs ;
- les noms **d'autres joueurs** dans certains événements : membres de votre escadrille, cibles de primes.

L'application ne fait rien d'autre sur votre ordinateur : elle ne lit aucun autre fichier, et n'utilise ni caméra, ni micro, ni localisation.

## Ce que l'application garde, et où

Tout reste sur votre ordinateur, dans `%LOCALAPPDATA%\EDRockMaster` :

- **vos réglages** (`settings.json`) ;
- **vos objectifs d'ingénierie** (`edrockmaster.sqlite3`) : les blueprints et effets que vous visez, et le nombre de passes ;
- **un journal technique** (`logs\`) : démarrage et arrêt de l'application, fichier de journal lu, erreurs ; il ne contient aucune statistique de votre partie ;
- **des enregistrements du journal** (`recordings\`), **seulement si vous les activez** (désactivés par défaut) : des copies d'entrées du journal, à joindre à un signalement de bogue si vous le souhaitez.

Les statistiques de vos sessions et votre situation (commandant, vaisseau, position, escadrille) ne sont **qu'en mémoire**, reconstruites depuis le journal à chaque démarrage de l'application, et jamais écrites nulle part.

## Ce que l'application envoie

**Rien.** L'application n'établit aucune connexion réseau : ni mesure d'audience, ni rapport de plantage, ni recherche de mise à jour (le Microsoft Store s'en charge).

Une version ultérieure proposera une liaison **facultative** avec les services en ligne d'EDRockMaster (historique de vos sessions, statistiques partagées). Elle sera désactivée sauf si vous l'activez, demandera d'abord votre consentement, et cette politique sera mise à jour avant la publication de cette version, pour dire exactement ce qui est envoyé, pourquoi, et combien de temps c'est conservé.

## Tiers

- **Microsoft Store** : installe et met à jour l'application, selon la [déclaration de confidentialité de Microsoft](https://privacy.microsoft.com/fr-fr/privacystatement). EDRockMaster n'en reçoit aucune donnée personnelle.
- **Microsoft Edge WebView2** : le composant de Windows qui dessine la fenêtre de l'application ; il fonctionne sur votre ordinateur.
- **Données du jeu** : la liste des matériaux, blueprints et ingénieurs vient de données communautaires (EDCD) livrées dans l'application ; rien n'est téléchargé.

## Vos choix

- **Voir ou effacer vos données** : tout est dans `%LOCALAPPDATA%\EDRockMaster` ; supprimez le dossier pour les effacer. La désinstallation de l'application le conserve, pour que vos objectifs survivent à une réinstallation ; supprimez-le à la main si vous le souhaitez.
- **Arrêter la lecture** : fermez l'application.

## Enfants

L'application s'adresse aux joueurs d'Elite Dangerous, classé PEGI 7 / ESRB Teen ; elle ne collecte rien auprès de personne.

## Contact

Questions sur cette politique : [contact@edrm.space](mailto:contact@edrm.space). Code source : [github.com/EDRockMaster/edrockmaster-plugin](https://github.com/EDRockMaster/edrockmaster-plugin).

## Modifications

Toute modification de cette politique est publiée ici, avec sa date, avant la version de l'application qu'elle concerne.

*Elite Dangerous est une marque de Frontier Developments plc. EDRockMaster n'est ni approuvé par Frontier Developments, ni affilié à elle.*
