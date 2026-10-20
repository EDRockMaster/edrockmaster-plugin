# Politique de confidentialité — EDRockMaster Companion

*[English](privacy.md) · Français*

Dernière mise à jour : 20 octobre 2026. S'applique à l'application de bureau EDRockMaster Companion et au plugin EDRockMaster pour EDMarketConnector, publiés par DamScan, un projet personnel et non commercial.

## En bref

EDRockMaster lit le journal qu'Elite Dangerous écrit sur votre ordinateur, calcule les statistiques de vos sessions **sur votre ordinateur**, et **ne nous envoie rien** : EDRockMaster n'a pas de serveur. Ni compte, ni mesure d'audience, ni publicité, ni pistage. Seulement quand vous cherchez dans les onglets *Minage* ou *Commerce*, ou estimez votre soute, l'application demande à des outils communautaires sur internet ce que le journal ne dit pas (ci-dessous).

## Ce que l'application lit

Elite Dangerous écrit un journal de votre partie dans votre dossier *Parties enregistrées* (Saved Games). EDRockMaster le lit, sans le modifier, pour afficher vos sessions de minage, de combat, de commerce et d'ingénierie. Ce journal contient notamment :

- le nom de votre commandant, votre vaisseau (type, nom et immatriculation que vous lui avez donnés), votre position (système, station) et votre mode de jeu (ouvert, solo, groupe privé et son nom) ;
- ce que vous avez fait : astéroïdes prospectés, marchandises raffinées, achats et ventes, victimes et primes, matériaux collectés, travaux des ingénieurs ;
- les noms **d'autres joueurs** dans certains événements : membres de votre escadrille, cibles de primes.

L'application ne fait rien d'autre sur votre ordinateur : elle ne lit aucun autre fichier, et n'utilise ni caméra, ni micro, ni localisation.

## Ce que l'application garde, et où

Tout reste sur votre ordinateur, dans `%LOCALAPPDATA%\EDRockMaster` :

- **vos réglages** (`settings.json`), avec la clé du lien du QR code de *Téléphone et tablette* une fois activé ;
- **vos objectifs d'ingénierie** (`edrockmaster.sqlite3`) : les blueprints et effets que vous visez, et le nombre de passes ;
- **un journal technique** (`logs\`) : démarrage et arrêt de l'application, fichier de journal lu, erreurs ; il ne contient aucune statistique de votre partie ;
- **vos bons non encaissés** (dans `edrockmaster.sqlite3`) : les primes et obligations de combat que vous détenez, par faction et par commandant (par son identifiant Frontier), et les noms des fichiers de journal déjà lus pour cela, afin que chacun ne soit lu qu'une fois ;
- **les réponses des sources communautaires** (dans `edrockmaster.sqlite3`) : ce que Spansh et Ardent Insight ont publié en réponse à vos recherches (anneaux, marchés, prix), réutilisé un temps au lieu de redemander ; rien sur vous ;
- **des enregistrements du journal** (`recordings\`), **seulement si vous les activez** (désactivés par défaut) : des copies d'entrées du journal, à joindre à un signalement de bogue si vous le souhaitez.

Hormis vos bons non encaissés, les statistiques de vos sessions et votre situation (commandant, vaisseau, position, escadrille) ne sont **qu'en mémoire**, reconstruites depuis le journal à chaque démarrage de l'application, et jamais écrites nulle part.

## Ce que l'application envoie

**Rien à nous** : EDRockMaster n'a pas de serveur, ni mesure d'audience, ni rapport de plantage.

**Une recherche de mise à jour, vers GitHub.** Installée avec son installeur, l'application cherche une version plus récente au démarrage, puis une fois par jour, dans les releases publiques de son dépôt sur GitHub (`github.com`, `api.github.com`), et l'y télécharge. Les requêtes ne portent rien de vous : ni identifiant, ni statistiques ; GitHub voit l'adresse IP de votre ordinateur et l'heure, comme tout site web. Le canal *bêta* lit aussi les versions candidates. Désactivée dans *Réglages*, *Mises à jour* : l'application ne demande alors rien.

**Vers votre téléphone ou votre tablette, seulement si vous l'activez.** *Réglages*, *Téléphone et tablette* (désactivé par défaut) permet à un téléphone ou une tablette du réseau de la maison d'ouvrir l'application dans son navigateur, par son QR code. L'application écoute alors votre réseau local, sur un port (47800 par défaut), et sert aux appareils qui ont le lien tout ce que montre la fenêtre, et les laisse le changer ; rien ne passe par internet, et rien ne nous parvient. Le lien contient une clé aléatoire ; quiconque, sur votre réseau, l'a voit et change ce que fait la fenêtre. Il circule en clair sur votre réseau (pas de HTTPS pour une adresse locale) : laissez-le désactivé sur un réseau public. Désactivée, l'application n'écoute rien ; *Utiliser un nouveau lien* exclut les appareils déjà connectés.

**Vos recherches, à des outils communautaires, et seulement quand vous les faites.** Les onglets *Minage* et *Commerce* et le bouton *Estimer la soute* demandent à deux outils communautaires indépendants ce que le journal ne dit pas :

- **Spansh** (`spansh.co.uk`), pour les anneaux et leurs hotspots autour d'un système : il reçoit la marchandise, le nom du système et vos filtres ;
- **Ardent Insight** (`ardent-insight.com`), pour les marchés qui achètent ou vendent une marchandise : il reçoit la marchandise, le nom du système, la distance et la demande ou le stock minimum choisis (l'onglet *Commerce* le remplit avec la capacité de soute de votre vaisseau) ; pour une estimation, une requête par marchandise de votre soute de minage, autour de votre système actuel.

Rien d'autre n'est envoyé : ni le nom de votre commandant, ni vos statistiques. Comme tout site web, ils voient l'adresse IP de votre ordinateur et l'heure. Ce sont des projets bénévoles tenus par d'autres joueurs, sans politique de confidentialité de leur part à notre connaissance. Chacun se désactive dans *Réglages*, *Sources communautaires* ; désactivé, il n'est jamais interrogé, et ce qu'il avait répondu est oublié.

## Tiers

- **GitHub** : publie l'application et ses mises à jour, selon la [déclaration de confidentialité de GitHub](https://docs.github.com/fr/site-policy/privacy-policies/github-general-privacy-statement) ; interrogé par la recherche de mise à jour, comme dit plus haut.
- **Microsoft Edge WebView2** : le composant de Windows qui dessine la fenêtre de l'application ; il fonctionne sur votre ordinateur.
- **Données du jeu** : la liste des matériaux, blueprints, ingénieurs et marchandises vient de données communautaires (EDCD) livrées dans l'application ; rien n'est téléchargé.
- **Spansh** et **Ardent Insight** : interrogés seulement quand vous cherchez, comme dit plus haut ; désactivables dans *Réglages*.

## Vos choix

- **Voir ou effacer vos données** : tout est dans `%LOCALAPPDATA%\EDRockMaster` ; supprimez le dossier pour les effacer. La désinstallation de l'application le conserve, pour que vos objectifs survivent à une réinstallation ; supprimez-le à la main si vous le souhaitez.
- **Arrêter la lecture** : fermez l'application.
- **Ne chercher aucune mise à jour** : désactivez *Rechercher les mises à jour* dans *Réglages*, *Mises à jour*.
- **Fermer l'accès du téléphone et de la tablette** : désactivez-le dans *Réglages*, *Téléphone et tablette*, ou *Utilisez un nouveau lien*.
- **N'interroger aucun outil communautaire** : désactivez Spansh et Ardent Insight dans *Réglages*, *Sources communautaires*.

## Enfants

L'application s'adresse aux joueurs d'Elite Dangerous, classé PEGI 7 / ESRB Teen ; elle ne collecte rien auprès de personne.

## Contact

Questions sur cette politique : [contact@edrm.space](mailto:contact@edrm.space). Code source : [github.com/EDRockMaster/edrockmaster-plugin](https://github.com/EDRockMaster/edrockmaster-plugin).

## Modifications

Toute modification de cette politique est publiée ici, avec sa date, avant la version de l'application qu'elle concerne.

*Elite Dangerous est une marque de Frontier Developments plc. EDRockMaster n'est ni approuvé par Frontier Developments, ni affilié à elle.*
