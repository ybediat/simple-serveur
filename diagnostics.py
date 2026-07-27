"""diagnostics.py — contenu du module « Dépannage » (brique 31), en donnée.

Même philosophie que `postgres_fiches.py` (brique 21) et `parcours/*.py` : ce
fichier ne contient AUCUNE logique, seulement des symptômes, des vérifications
et des gestes. On peut en ajouter sans toucher au moteur
(`core/diagnostic.py`) ni à la page (`modules/depannage.py`).

Trois règles de rédaction, toutes vérifiées par `tests/test_diagnostics.py` :

1. **Toute `Verification.commande` est en LECTURE SEULE.** Aucune vérification
   ne modifie quoi que ce soit — pas de `restart`, pas de `stop`, pas de
   `truncate`, aucune redirection, aucun `sudo systemctl` autre que
   `is-active` / `is-enabled`. C'est ce qui permet au bouton « Tout vérifier »
   d'exister : on lance un bilan complet sans réfléchir, sur un serveur déjà
   en panne, sans risquer d'aggraver quoi que ce soit.
2. **Les modifications vivent exclusivement dans les `Geste`**, tous derrière
   `confirm_action`, tous accompagnés de ce qu'ils NE réparent PAS.
3. `explication` et `interpretation` font plus de 150 caractères. Ce n'est pas
   une coquetterie : une vérification qu'on ne sait pas lire ne sert à rien, et
   le but du module est d'apprendre à CHERCHER, pas de donner un oracle.

Interdits ici comme partout (CLAUDE.md) : `prune`, `rm -r`, `down -v`,
suppression de données. Un dépannage qui supprime, c'est un incident qui en
devient deux.
"""
from __future__ import annotations

from dataclasses import dataclass

from core import diagnostic

# Jetons substitués par `core.parcours.substituer_jetons` avant exécution.
# `__STACKS_DIR__` et `__BACKUP_DIR__` viennent de la configuration (brique 12) ;
# les autres sont saisis ou hérités du Tableau de bord (`set_params`).
JETON_STACKS = "__STACKS_DIR__"
JETON_BACKUP = "__BACKUP_DIR__"
JETON_CONTENEUR = "__CONTENEUR__"
JETON_STACK = "__STACK__"
JETON_DOMAINE = "__DOMAINE__"
JETON_IP = "__IP__"
JETON_PORT = "__PORT__"


@dataclass(frozen=True)
class Verification:
    """Une question posée au serveur, et comment lire sa réponse."""

    verif_id: str
    libelle: str              # « Le conteneur tourne-t-il ? »
    commande: str             # lecture seule, avec jetons
    explication: str          # ce qu'on regarde et pourquoi c'est cette question-là
    interpretation: str       # comment lire la sortie : quel motif = quel diagnostic
    motif_probleme: str = ""  # regex ; trouvée dans la sortie → piste CONFIRMEE
    motif_ok: str = ""        # regex ; trouvée → piste ECARTEE
    seuil: str = ""           # vérification numérique (« disque>90 »)
    geste_id: str = ""        # réparation proposée si la piste est confirmée
    besoin_conteneur: bool = False  # exige un conteneur sélectionné
    besoin_domaine: bool = False    # exige un domaine saisi


@dataclass(frozen=True)
class Geste:
    """Une réparation proposée. Jamais exécutée sans `confirm_action`."""

    geste_id: str
    libelle: str              # « Redémarrer le conteneur »
    commande: str
    explication: str          # ce que ça fait, ce que ça NE répare pas, ce que ça coupe
    sensible: bool = True     # par défaut oui : on répare un serveur en panne


@dataclass(frozen=True)
class Symptome:
    """Ce que l'utilisateur constate, dit dans ses mots."""

    symptome_id: str
    titre: str
    description: str
    verifications: tuple[str, ...] = ()   # ids, dans l'ordre du plus fréquent au plus rare
    manuel: bool = False                  # True = checklist locale (cas SSH)
    checklist: tuple[str, ...] = ()       # étapes de la checklist locale


# ============================================================================
#                             VÉRIFICATIONS
# ============================================================================
# Ordonnées par domaine et indexées par id : une même vérification sert à
# plusieurs symptômes (« le disque est-il plein ? » revient dans quatre d'entre
# eux, et c'est très bien — c'est la première question à se poser).
VERIFICATIONS: tuple[Verification, ...] = (
    # ------------------------------------------------------------ conteneur
    Verification(
        verif_id="conteneur_etat",
        libelle="Le conteneur existe-t-il, et tourne-t-il ?",
        commande=(
            f"docker ps -a --filter name=^{JETON_CONTENEUR}$ "
            "--format '{{.Names}}|{{.State}}|{{.Status}}'"
        ),
        explication=(
            "La toute première question, et celle qu'on saute le plus souvent parce "
            "qu'elle paraît idiote : le conteneur est-il seulement là ? On liste avec "
            "« -a », donc y compris les conteneurs arrêtés — un service qui ne répond "
            "plus est très rarement un service qui répond mal, c'est presque toujours "
            "un service qui n'est plus là. Une sortie vide veut dire que le conteneur "
            "n'existe pas du tout : nom mal orthographié, ou stack jamais relancée "
            "après un redémarrage du serveur."
        ),
        interpretation=(
            "« running » : le conteneur tourne, la panne est ailleurs (réseau, proxy, "
            "application elle-même) — passe aux vérifications suivantes. « exited » ou "
            "« dead » : c'est la cause directe, et le statut donne le code de sortie "
            "entre parenthèses (137 = tué par manque de mémoire, 1 = l'application "
            "s'est arrêtée d'elle-même). Aucune ligne du tout : le conteneur n'existe "
            "pas sous ce nom-là sur ce serveur."
        ),
        motif_probleme=r"\|(exited|dead|created|paused)\|",
        motif_ok=r"\|running\|",
        geste_id="redemarrer_conteneur",
        besoin_conteneur=True,
    ),
    Verification(
        verif_id="conteneur_redemarrages",
        libelle="Combien de fois le conteneur a-t-il redémarré ?",
        commande=f"docker inspect --format '{{{{.RestartCount}}}}' {JETON_CONTENEUR}",
        explication=(
            "Le compteur que Docker tient depuis la création du conteneur. C'est LA "
            "signature d'une boucle de redémarrage : le service démarre, plante en "
            "quelques secondes, la politique « always » ou « unless-stopped » le "
            "relance, et le cycle recommence. De l'extérieur, on voit un conteneur "
            "tantôt « up », tantôt « restarting », et un service qui répond une fois "
            "sur dix — le symptôme le plus déroutant qui soit, parce qu'il ressemble "
            "à un problème de réseau."
        ),
        interpretation=(
            "0 à 2 : normal, ce sont les redémarrages du serveur ou une mise à jour de "
            "stack. Au-delà de 3, et surtout si le nombre grimpe entre deux lectures, "
            "c'est une boucle : le conteneur n'arrive pas à démarrer. Redémarrer une "
            "fois de plus ne servira à rien — la réponse est dans les dernières lignes "
            "de log, vérification suivante. Un compteur à plusieurs dizaines veut dire "
            "que ça dure depuis des heures."
        ),
        seuil=f"redemarrages>{diagnostic.SEUIL_REDEMARRAGES}",
        geste_id="voir_logs_conteneur",
        besoin_conteneur=True,
    ),
    Verification(
        verif_id="conteneur_sortie",
        libelle="Comment le conteneur s'est-il arrêté ?",
        commande=(
            "docker inspect --format "
            "'{{.State.ExitCode}}|{{.State.OOMKilled}}|{{.State.Error}}' "
            f"{JETON_CONTENEUR}"
        ),
        explication=(
            "Trois informations que Docker garde après l'arrêt et qu'aucune autre "
            "commande ne donne aussi directement : le code de sortie du processus "
            "principal, un drapeau qui dit si c'est le noyau qui l'a tué par manque de "
            "mémoire, et le message d'erreur du démon s'il y en a un. C'est la "
            "différence entre « l'application a décidé de s'arrêter » et « quelque "
            "chose l'a tuée », et ces deux cas n'appellent absolument pas la même "
            "réparation."
        ),
        interpretation=(
            "0 : arrêt propre, quelqu'un a arrêté le conteneur — ce n'est pas une "
            "panne. 137 avec OOMKilled à « true » : le noyau a tué le conteneur parce "
            "que la machine manquait de mémoire — c'est le mécanisme du noyau qui tue "
            "un programme quand il ne reste plus rien, l'« OOM killer » ; enchaîne "
            "avec les vérifications « Reste-t-il de la mémoire vive ? » et « Le noyau "
            "a-t-il tué des processus par manque de mémoire ? ». 1 ou "
            "2 : l'application s'est arrêtée sur une erreur, la réponse est dans ses "
            "logs. 143 : arrêt demandé (SIGTERM), normal lors d'une mise à jour de "
            "stack."
        ),
        motif_probleme=r"^(137|139|1|2)\|",
        motif_ok=r"^(0|143)\|",
        besoin_conteneur=True,
    ),
    Verification(
        verif_id="conteneur_logs",
        libelle="Que disent les dernières lignes de log du conteneur ?",
        commande=f"docker logs --tail 50 {JETON_CONTENEUR}",
        explication=(
            "Les cinquante dernières lignes que l'application a écrites avant de "
            "s'arrêter. Dans la grande majorité des pannes, la réponse est écrite noir "
            "sur blanc dans ces lignes-là, et tout le reste du diagnostic ne sert qu'à "
            "savoir quel conteneur regarder. On se limite à cinquante lignes "
            "volontairement : au-delà on ne lit plus, on survole, et le message "
            "important passe inaperçu. La page Logs sert au suivi en direct, ici on "
            "veut juste la fin de l'histoire."
        ),
        interpretation=(
            "Cherche les mots « error », « fatal », « refused », « denied », « no "
            "space left ». « No space left on device » renvoie au disque ou aux "
            "inodes. « Connection refused » vers une base de données veut dire que le "
            "conteneur de base n'est pas (encore) là. « Permission denied » est presque "
            "toujours un volume monté avec les mauvais droits après une mise à jour. "
            "Aucune ligne : le conteneur n'a jamais démarré assez loin pour parler."
        ),
        motif_probleme=r"(no space left|fatal|panic|refused|denied|killed)",
        besoin_conteneur=True,
    ),
    Verification(
        verif_id="conteneur_ports",
        libelle="Le conteneur publie-t-il un port ?",
        commande=f"docker port {JETON_CONTENEUR}",
        explication=(
            "La correspondance entre les ports de l'hôte et ceux du conteneur. Un "
            "service accessible « directement » (sans passer par le proxy) a besoin "
            "d'un port publié ; un service placé derrière NGINX Proxy Manager n'en a "
            "pas besoin et n'en a souvent pas, ce qui est normal et même souhaitable. "
            "Cette vérification sert surtout à trancher entre « le service ne tourne "
            "pas » et « le service tourne mais personne ne sait comment l'atteindre »."
        ),
        interpretation=(
            "Une ligne comme « 80/tcp -> 0.0.0.0:8080 » se lit de droite à gauche : on "
            "atteint le service en demandant le port 8080 de la machine, et Docker "
            "l'amène sur le port 80 du conteneur. La partie « 0.0.0.0 » est l'adresse "
            "d'écoute côté machine et signifie « depuis n'importe quel réseau » — par "
            "opposition à « 127.0.0.1 », qui réserverait le service à la machine "
            "elle-même. Une ligne ou plusieurs, donc : le port est publié, le service "
            "est joignable depuis le réseau. Aucune "
            "ligne : le conteneur ne publie rien — soit c'est voulu (reverse proxy sur "
            "le même réseau Docker), soit la publication a disparu du compose et c'est "
            "la cause de la panne. Compare avec ce que dit le proxy avant de conclure."
        ),
        besoin_conteneur=True,
    ),
    Verification(
        verif_id="conteneur_sante",
        libelle="Que dit le contrôle de santé du conteneur ?",
        commande=(
            "docker inspect --format "
            "'{{if .State.Health}}{{.State.Health.Status}}{{else}}sans healthcheck"
            f"{{{{end}}}}' {JETON_CONTENEUR}"
        ),
        explication=(
            "Certaines images embarquent un « healthcheck » : une commande que Docker "
            "lance périodiquement dans le conteneur pour vérifier que l'application "
            "répond vraiment, et pas seulement que le processus existe. C'est la seule "
            "façon de détecter un service vivant mais bloqué — celui qui accepte les "
            "connexions et ne répond jamais. Toutes les images n'en ont pas, et leur "
            "absence n'est pas un défaut."
        ),
        interpretation=(
            "« healthy » : l'application répond, la panne est en amont (proxy, DNS, "
            "certificat) et pas dans le conteneur. « unhealthy » : le conteneur tourne "
            "mais son application ne répond plus — c'est précisément le cas où "
            "redémarrer aide vraiment. « starting » : le conteneur vient de démarrer, "
            "attends une minute avant de conclure. « sans healthcheck » : cette image "
            "n'en propose pas, cette piste ne dit donc rien."
        ),
        motif_probleme=r"unhealthy",
        motif_ok=r"^(healthy|sans healthcheck)",
        geste_id="redemarrer_conteneur",
        besoin_conteneur=True,
    ),
    # -------------------------------------------------------------- système
    Verification(
        verif_id="disque",
        libelle="Reste-t-il de la place sur les disques ?",
        commande=diagnostic.build_df_cmd(),
        explication=(
            "La cause numéro un des pannes sur un serveur domestique, et de très loin. "
            "Un disque plein ne provoque pas une erreur claire : il fait échouer des "
            "écritures au hasard, corrompt des bases, empêche les conteneurs de "
            "démarrer et rend les logs illisibles — le tout sans jamais dire « disque "
            "plein » nulle part. C'est donc la première chose à regarder, quel que "
            "soit le symptôme, avant même de savoir de quel service on parle."
        ),
        interpretation=(
            f"Au-delà de {diagnostic.SEUIL_DISQUE_PCT} % d'occupation sur n'importe "
            "quel point de montage, considère la piste comme confirmée et traite-la "
            "avant tout le reste : rien d'autre ne sera fiable tant que ce n'est pas "
            "réglé. Regarde surtout la ligne « / » (le système, où vivent les images "
            "et les logs Docker) et celle qui porte les sauvegardes. Entre 80 et 90 %, "
            "ce n'est pas encore la panne, mais c'est le moment d'agir."
        ),
        seuil=f"disque>{diagnostic.SEUIL_DISQUE_PCT}",
        geste_id="voir_logs_volumineux",
    ),
    Verification(
        verif_id="inodes",
        libelle="Reste-t-il des inodes (le disque « plein » avec de la place) ?",
        commande=diagnostic.build_df_inodes_cmd(),
        explication=(
            "Un système de fichiers a deux ressources séparées : l'espace, et le "
            "nombre de fichiers qu'il peut contenir (les inodes). On peut épuiser le "
            "second avec des centaines de milliers de tout petits fichiers alors que "
            "le premier reste à 60 %. Le serveur dit alors « No space left on device » "
            "et tous les `df -h` du monde disent que tout va bien — c'est la panne la "
            "plus incompréhensible qui soit tant qu'on ne connaît pas cette commande, "
            "et elle se règle en cinq minutes une fois identifiée."
        ),
        interpretation=(
            f"Au-delà de {diagnostic.SEUIL_INODES_PCT} % d'inodes utilisés, c'est la "
            "cause, même si l'espace disque paraît confortable. Les coupables "
            "habituels : un cache applicatif jamais purgé, une file d'attente de mails "
            "bloquée, un dossier de sessions PHP. Pour trouver le dossier fautif, "
            "compte les fichiers étage par étage depuis la Console : "
            "« sudo du --inodes -x -d1 /var | sort -n » donne le nombre de fichiers de "
            "chaque sous-dossier, et on redescend dans le plus gros jusqu'à tomber "
            "dessus. Ensuite seulement, vide-le par l'application qui l'a rempli "
            "(purge du cache, de la file de mails) — ne supprime rien au hasard : un "
            "dossier d'inodes plein est presque toujours un dossier de travail encore "
            "utilisé."
        ),
        seuil=f"inodes>{diagnostic.SEUIL_INODES_PCT}",
    ),
    Verification(
        verif_id="memoire",
        libelle="Reste-t-il de la mémoire vive ?",
        commande="free -m",
        explication=(
            "La mémoire disponible, en mégaoctets. Attention au piège classique de "
            "cette commande : sous Linux, la mémoire « utilisée » inclut le cache "
            "disque, qui est rendu instantanément dès qu'un programme en a besoin. La "
            "colonne qui compte est « available », et elle seule. Un serveur affichant "
            "90 % de mémoire « used » avec 3 Go « available » se porte parfaitement "
            "bien, et c'est ce malentendu qui envoie chercher des pannes qui n'existent "
            "pas."
        ),
        interpretation=(
            "Si « available » descend sous quelques centaines de mégaoctets, la machine "
            "est réellement à court : le noyau va commencer à tuer des processus pour "
            "se dégager de la place — c'est la vérification « Le noyau a-t-il tué des "
            "processus par manque de mémoire ? » qui le dira —, et tout devient lent "
            "avant de tomber. Regarde aussi "
            "la ligne « Swap » : un swap entièrement consommé sur une machine qui rame "
            "confirme le manque de mémoire. La réponse est alors de limiter un "
            "conteneur gourmand, pas de redémarrer : « docker stats --no-stream » "
            "désigne le coupable en une ligne, puis on ajoute une limite à son service "
            "dans le fichier `compose.yaml` de sa stack (« mem_limit: 512m », à la "
            "taille qui convient) avant de relancer la stack."
        ),
        motif_ok=r"^Mem:",
    ),
    Verification(
        verif_id="charge",
        libelle="Le serveur est-il surchargé ?",
        commande="uptime",
        explication=(
            "La charge moyenne sur 1, 5 et 15 minutes, et depuis combien de temps la "
            "machine tourne. La charge se lit en la comparant au nombre de cœurs : sur "
            "un serveur à 4 cœurs, une charge de 4 signifie « occupé mais à l'heure », "
            "et une charge de 12 signifie que tout attend. Les trois chiffres ensemble "
            "racontent une tendance — c'est plus utile qu'une valeur instantanée."
        ),
        interpretation=(
            "Le premier chiffre plus grand que le troisième : la charge monte, quelque "
            "chose vient de démarrer ou de s'emballer. L'inverse : la crise est passée. "
            "Un « up » de quelques minutes alors que personne n'a redémarré la machine "
            "est une information majeure : le serveur a redémarré tout seul (coupure de "
            "courant, plantage noyau), et c'est peut-être toute l'explication de la "
            "panne que tu cherches."
        ),
        motif_ok=r"load average",
    ),
    Verification(
        verif_id="oom",
        libelle="Le noyau a-t-il tué des processus par manque de mémoire ?",
        commande=diagnostic.build_dmesg_oom_cmd(),
        explication=(
            "Quand la mémoire vient à manquer, le noyau Linux choisit un processus et "
            "le tue sans prévenir. Le conteneur disparaît, les logs de l'application "
            "s'arrêtent net au milieu d'une phrase, et rien nulle part ne dit pourquoi "
            "— sauf ici, dans le journal du noyau. C'est l'explication de l'immense "
            "majorité des « il s'est arrêté tout seul cette nuit », et personne ne la "
            "trouve tant qu'on ne sait pas où regarder."
        ),
        interpretation=(
            "Chaque ligne « Killed process 1234 (nom) » est une victime, avec la date. "
            "Si le nom correspond à ton service, tu as ta réponse : la machine manque "
            "de mémoire, et redémarrer le conteneur ne fera que repousser le problème "
            "de quelques heures. La vraie réparation est de plafonner la mémoire du "
            "conteneur gourmand : « mem_limit: 512m » sous son service dans le fichier "
            "`compose.yaml` de sa stack, puis relance de la stack — ainsi c'est lui "
            "qui est arrêté quand il déborde, au lieu d'un voisin choisi par le noyau. "
            "Ajouter du swap est l'autre voie, plus lente mais moins brutale. Aucune "
            "ligne : la piste est écartée."
        ),
        seuil="oom>0",
    ),
    Verification(
        verif_id="heure",
        libelle="L'horloge du serveur est-elle juste et synchronisée ?",
        commande="timedatectl",
        explication=(
            "Une horloge décalée casse des choses qui n'ont apparemment rien à voir "
            "avec l'heure : les certificats TLS deviennent « pas encore valides » ou "
            "« expirés », les jetons d'authentification sont refusés, les sauvegardes "
            "se datent n'importe comment et les logs deviennent impossibles à recouper "
            "entre deux machines. C'est une cause rare mais spectaculaire, et elle "
            "coûte une seconde à écarter."
        ),
        interpretation=(
            "« System clock synchronized: yes » et « NTP service: active » : tout va "
            "bien, écarte la piste. « no » aux deux : l'horloge dérive, et si l'écart "
            "dépasse quelques minutes il faut le corriger avant de chercher ailleurs : "
            "depuis la Console, « sudo timedatectl set-ntp true » rebranche la "
            "synchronisation automatique, et l'heure se remet d'aplomb en quelques "
            "secondes. Vérifie aussi que le fuseau affiché est bien Europe/Paris "
            "(« sudo timedatectl set-timezone Europe/Paris » sinon), sinon les "
            "heures de tous les logs seront décalées et tu chercheras un événement à "
            "la mauvaise heure."
        ),
        motif_probleme=r"synchronized:\s*no",
        motif_ok=r"synchronized:\s*yes",
    ),
    # --------------------------------------------------------------- docker
    Verification(
        verif_id="docker_actif",
        libelle="Le démon Docker tourne-t-il ?",
        commande=diagnostic.build_is_active_cmd("docker"),
        explication=(
            "Avant de chercher pourquoi un conteneur ne répond pas, il faut savoir si "
            "Docker lui-même est vivant. Le démon peut s'arrêter après une mise à jour "
            "de paquet qui a mal fini, un disque plein au démarrage, ou une "
            "modification du fichier de réglages du démon — celui où l'on configure "
            "par exemple la rotation des logs, et qui s'appelle "
            "`/etc/docker/daemon.json` — qui l'empêche de repartir. Dans ce cas, "
            "AUCUN conteneur ne tourne, et chercher la panne service par service fait "
            "perdre un temps considérable."
        ),
        interpretation=(
            "« active » : le démon tourne, la panne concerne un conteneur en "
            "particulier. « inactive » ou « failed » : c'est Docker entier qui est à "
            "terre, plus rien ne tourne sur ce serveur. Regarde alors le journal de "
            "l'unité (vérification « journal de Docker ») : la raison y est presque "
            "toujours écrite, souvent une erreur de syntaxe dans un fichier de "
            "configuration modifié la veille."
        ),
        motif_probleme=r"^(inactive|failed|unknown)",
        motif_ok=r"^active",
        geste_id="relancer_docker",
    ),
    Verification(
        verif_id="logs_docker_espace",
        libelle="Quelle place prennent les logs des conteneurs ?",
        commande=diagnostic.build_du_logs_docker_cmd(),
        explication=(
            "Chaque conteneur écrit sa sortie dans un fichier `-json.log`, et sans "
            "configuration de rotation ce fichier grossit sans aucune limite. Un "
            "conteneur bavard peut à lui seul remplir un disque en quelques mois, sans "
            "que rien ne prévienne. C'est la cause la plus fréquente d'un « / » qui se "
            "remplit tout seul sur un serveur qui n'a pourtant rien changé — et le "
            "réglage définitif est l'affaire de la page Audit."
        ),
        interpretation=(
            f"Un fichier au-delà de {diagnostic.SEUIL_LOG_MO} Mo est déjà anormal ; "
            "au-delà du gigaoctet, c'est probablement ton problème de disque à lui "
            "tout seul. Le chemin contient l'identifiant du conteneur, ce qui permet de "
            "savoir lequel est bavard. Le vider ne règle rien de durable : c'est la "
            "rotation des logs qu'il faut configurer, sinon le fichier repousse à "
            "l'identique."
        ),
        seuil=f"taille_log_mo>{diagnostic.SEUIL_LOG_MO}",
        geste_id="purger_log_conteneur",
    ),
    Verification(
        verif_id="images_orphelines",
        libelle="Des images Docker orphelines occupent-elles le disque ?",
        commande="docker image ls -f dangling=true --format '{{.ID}} {{.Size}}'",
        explication=(
            "Chaque mise à jour d'une stack laisse derrière elle l'ancienne image, qui "
            "n'est plus référencée par rien mais occupe toujours sa place. Sur un "
            "serveur mis à jour régulièrement, ces images « pendantes » finissent par "
            "représenter plusieurs gigaoctets. Ce n'est jamais la cause d'une panne en "
            "soi, mais c'est de la place immédiatement récupérable quand le disque "
            "serre, et sans le moindre risque."
        ),
        interpretation=(
            "Chaque ligne est une image sans nom, avec sa taille. Leur suppression est "
            "sûre : par définition, aucune image pendante ne sert à un conteneur "
            "existant. Le ménage se fait depuis la page Santé serveur, qui montre "
            "d'abord ce "
            "qui sera supprimé. Aucune ligne : rien à récupérer de ce côté, cherche la "
            "place ailleurs (logs de conteneurs, sauvegardes, cache de build)."
        ),
    ),
    # ------------------------------------------------------- journal systemd
    Verification(
        verif_id="journal_ssh",
        libelle="Que dit le journal du service SSH ?",
        commande="sudo journalctl -u ssh -n 50 --no-pager",
        explication=(
            "La page Logs de l'application ne lit que `docker logs` : tout ce qui se "
            "passe hors conteneur lui échappe. Le journal systemd est le complément "
            "manquant, et c'est ici sa place naturelle. Pour SSH, il montre les "
            "tentatives de connexion refusées, les bannissements, les rechargements de "
            "configuration — et donc pourquoi un accès qui marchait hier ne marche "
            "plus aujourd'hui."
        ),
        interpretation=(
            "« Accepted publickey » : les connexions par clé fonctionnent. Une rafale "
            "de « Failed password » depuis la même adresse est une attaque banale, sans "
            "gravité tant que fail2ban fait son travail. « Invalid user » suivi de ton "
            "propre nom d'utilisateur est en revanche à regarder. Si le service a "
            "redémarré récemment sans que tu l'aies demandé, note l'heure et compare "
            "avec le reste du diagnostic."
        ),
        motif_probleme=r"(failed to start|fatal|error)",
        motif_ok=r"(Server listening|Accepted)",
    ),
    Verification(
        verif_id="journal_docker",
        libelle="Que dit le journal du démon Docker ?",
        commande="sudo journalctl -u docker -n 50 --no-pager",
        explication=(
            "Ce que Docker lui-même raconte, par opposition à ce que racontent les "
            "conteneurs. C'est là qu'apparaissent les refus de démarrage, les erreurs "
            "de réseau, les problèmes d'écriture sur le disque et les échecs de "
            "contrôle de santé. Quand un conteneur disparaît sans explication et que "
            "ses propres logs sont muets, la réponse est presque toujours dans ce "
            "journal-là."
        ),
        interpretation=(
            "« no space left on device » confirme sans ambiguïté la piste du disque. "
            "« failed to start » avec un nom de conteneur donne le coupable "
            "immédiatement. Des lignes de niveau « error » répétées à intervalle "
            "régulier accompagnent en général une boucle de redémarrage. Un journal "
            "calme depuis des jours écarte Docker de l'enquête : le problème est dans "
            "l'application, pas dans le moteur."
        ),
        motif_probleme=r"(level=error|no space left|failed to start)",
    ),
    Verification(
        verif_id="fail2ban",
        libelle="fail2ban a-t-il banni des adresses ?",
        commande="sudo fail2ban-client status sshd",
        explication=(
            "fail2ban surveille les échecs d'authentification et bloque les adresses "
            "qui insistent. C'est une excellente protection, avec un effet de bord "
            "connu : après quelques tentatives ratées, il bannit très bien VOTRE propre "
            "adresse, et l'accès devient impossible depuis chez soi alors que le "
            "serveur va parfaitement bien. C'est la deuxième cause de « je n'arrive "
            "plus à me connecter », juste derrière l'adresse IP qui a changé."
        ),
        interpretation=(
            "« Currently banned » donne le nombre d'adresses bloquées en ce moment, et "
            "« Banned IP list » les énumère. Si ton adresse publique y figure, tu as "
            "ton explication — et la page Santé serveur sait la débannir et la mettre "
            "en liste "
            "verte pour que ça ne recommence pas. Si la commande ne répond pas, "
            "fail2ban n'est pas installé sur ce serveur, ce qui écarte simplement cette "
            "piste."
        ),
        motif_probleme=r"Currently banned:\s*[1-9]",
        motif_ok=r"Currently banned:\s*0",
        geste_id="debannir_ip",
    ),
    # -------------------------------------------------------- réseau / HTTPS
    Verification(
        verif_id="ports_ecoute",
        libelle="Quels ports sont en écoute sur le serveur ?",
        commande="sudo ss -lntp",
        explication=(
            "La liste de ce qui accepte réellement des connexions, avec le programme "
            "derrière chaque port. C'est la vérité de terrain, celle qui tranche entre "
            "« le service est censé écouter » et « le service écoute ». Un port absent "
            "de cette liste n'est joignable par personne, quelles que soient les règles "
            "de pare-feu et la configuration du proxy — inutile d'aller chercher plus "
            "loin tant que ce n'est pas réglé."
        ),
        interpretation=(
            "Les ports 80 et 443 doivent apparaître si un reverse proxy tourne, et le "
            "port 22 si SSH fonctionne (ce qui est forcément le cas puisque cette "
            "commande a répondu). Une adresse « 127.0.0.1 » signifie que le service "
            "n'écoute que localement : parfait pour une base de données, fatal pour un "
            "service qu'on veut atteindre de l'extérieur. « 0.0.0.0 » signifie "
            "« depuis partout »."
        ),
        motif_ok=r"LISTEN",
    ),
    Verification(
        verif_id="dns",
        libelle="Le domaine pointe-t-il bien vers ce serveur ?",
        commande=f"getent hosts {JETON_DOMAINE}",
        explication=(
            "Résout le nom de domaine et affiche l'adresse IP obtenue. Sur une "
            "connexion domestique sans adresse fixe, cette adresse change à chaque "
            "renouvellement du bail, et si le service de DNS dynamique n'a pas suivi, "
            "le domaine pointe vers une machine qui n'est plus la vôtre. Tout le reste "
            "fonctionne parfaitement, et pourtant plus rien n'est joignable de "
            "l'extérieur."
        ),
        interpretation=(
            "Compare l'adresse obtenue à l'adresse publique réelle de ta connexion. "
            "Identiques : le DNS est bon, la panne est ailleurs. Différentes : c'est ta "
            "réponse — corrige l'enregistrement « A » du nom (celui qui contient "
            "l'adresse IP) dans l'interface DNS de ton fournisseur de domaine, et "
            "compte quelques minutes avant que le changement se propage ; si un client "
            "de DNS dynamique est censé le faire tout seul, c'est lui qu'il faut "
            "réparer, sinon l'adresse redeviendra fausse au prochain changement. "
            "Aucune réponse du tout : le domaine n'existe pas ou "
            "n'est plus délégué — vérifie qu'il n'a pas simplement expiré."
        ),
        besoin_domaine=True,
    ),
    Verification(
        verif_id="certificat",
        libelle="Le certificat HTTPS est-il encore valide ?",
        commande=diagnostic.build_enddate_cmd(JETON_DOMAINE),
        explication=(
            "Interroge le serveur en HTTPS et lit la date d'expiration du certificat "
            "qu'il présente. Le renouvellement automatique par Let's Encrypt fonctionne "
            "très bien… jusqu'au jour où il échoue silencieusement. Pour renouveler, "
            "Let's Encrypt vérifie d'abord que le domaine est bien à toi : il contacte "
            "ton serveur en HTTP ordinaire, c'est-à-dire sur le port 80 — celui du web "
            "non chiffré, à ne pas confondre avec le 443 qu'utilise HTTPS. Si ce "
            "port-là a été refermé entre-temps, ou si le domaine ne pointe plus vers "
            "ta connexion, l'opération échoue sans rien dire. On l'apprend alors par un "
            "navigateur qui affiche un avertissement en pleine page, et par des "
            "applications mobiles qui refusent de se connecter sans rien expliquer."
        ),
        interpretation=(
            f"Moins de {diagnostic.CERT_JOURS_PROBLEME} jours restants : traite-le "
            "immédiatement, le renouvellement automatique a déjà eu plusieurs occasions "
            "d'échouer. Une date déjà passée explique à elle seule toutes les erreurs "
            "de sécurité des navigateurs. Concrètement : ouvre NGINX Proxy Manager, "
            "rubrique « SSL Certificates », et redemande le renouvellement du "
            "certificat concerné ; s'il échoue encore, la cause est presque toujours "
            "le port 80 refermé (vérification « Que laisse passer le pare-feu ? ») ou "
            "le domaine qui ne pointe plus ici (vérification « Le domaine pointe-t-il "
            "bien vers ce serveur ? ») — répare cela d'abord, puis relance le "
            "renouvellement. La page Audit surveille ces dates en permanence, règle "
            "« Expiration des certificats TLS ». Plus de trois semaines : la piste est "
            "écartée. Si la commande ne répond rien, le service HTTPS ne répond pas du "
            "tout, ce qui est un autre problème — et un plus urgent."
        ),
        seuil=f"jours<{diagnostic.CERT_JOURS_PROBLEME}",
        besoin_domaine=True,
    ),
    Verification(
        verif_id="ufw",
        libelle="Que laisse passer le pare-feu ?",
        commande="sudo ufw status numbered",
        explication=(
            "Les règles du pare-feu, numérotées. Un port fermé par UFW donne exactement "
            "le même symptôme qu'un service arrêté vu de l'extérieur : la connexion "
            "n'aboutit pas. La différence se fait en comparant cette liste avec celle "
            "des ports réellement en écoute — c'est pour cela que les deux "
            "vérifications se suivent, et qu'aucune des deux ne suffit toute seule à "
            "conclure."
        ),
        interpretation=(
            "Vérifie que chaque service exposé a bien sa règle : OpenSSH, 80/tcp et "
            "443/tcp au minimum sur un serveur avec reverse proxy. Un port en écoute "
            "mais absent d'ici est bloqué par le pare-feu. « Status: inactive » signifie "
            "que le pare-feu est éteint : ce n'est pas la cause de ta panne, mais c'est "
            "un sujet en soi. Attention aux règles limitées à une adresse source "
            "précise, qui n'ouvrent le port que pour elle."
        ),
        motif_ok=r"Status:\s*active",
        geste_id="ouvrir_port_ufw",
    ),
)


# ============================================================================
#                                  GESTES
# ============================================================================
# Volontairement peu nombreux. Chaque explication dit ce que le geste NE répare
# PAS — c'est le plus important : un redémarrage qui « règle » un disque plein
# pendant cinq minutes fait perdre une heure à celui qui y croit.
GESTES: tuple[Geste, ...] = (
    Geste(
        geste_id="redemarrer_conteneur",
        libelle="Redémarrer le conteneur",
        commande=f"docker restart {JETON_CONTENEUR}",
        explication=(
            "Arrête puis relance le conteneur. Efficace contre une application bloquée "
            "ou « unhealthy », qui repart propre. Ce que ça NE répare PAS : un disque "
            "plein, un manque de mémoire, une base de données absente ou une erreur de "
            "configuration — dans ces cas-là le conteneur retombera en panne dans les "
            "minutes qui suivent, et tu auras seulement perdu les traces de l'incident. "
            "Coupe le service pendant quelques secondes."
        ),
    ),
    Geste(
        geste_id="redemarrer_stack",
        libelle="Redémarrer toute la stack",
        commande=(
            f"docker compose --project-directory {JETON_STACKS}/{JETON_STACK} restart"
        ),
        explication=(
            "Redémarre tous les conteneurs de la stack dans l'ordre du fichier "
            "compose. Utile quand plusieurs services d'une même application se sont "
            "désynchronisés — typiquement une application qui a démarré avant sa base "
            "de données. Ce que ça NE répare PAS : une modification du compose (il faut "
            "alors recréer, pas redémarrer), ni aucune cause système. Coupe toute "
            "l'application, pas seulement un service."
        ),
    ),
    Geste(
        geste_id="debannir_ip",
        libelle="Débannir une adresse dans fail2ban",
        commande=f"sudo fail2ban-client unban {JETON_IP}",
        explication=(
            "Retire l'adresse de toutes les jails de fail2ban, immédiatement. À "
            "utiliser quand c'est ta propre adresse qui a été bannie après quelques "
            "essais ratés. Ce que ça NE répare PAS : le bannissement recommencera à la "
            "prochaine série d'échecs — pour l'éviter durablement, ajoute l'adresse à "
            "la liste verte depuis la page Santé serveur, qui gère un fichier dédié "
            "sans "
            "toucher à ta configuration."
        ),
    ),
    Geste(
        geste_id="ouvrir_port_ufw",
        libelle="Ouvrir un port dans le pare-feu",
        commande=f"sudo ufw allow {JETON_PORT}/tcp",
        explication=(
            "Ajoute une règle autorisant le port en TCP depuis n'importe quelle "
            "adresse. Ce que ça NE répare PAS : si aucun service n'écoute derrière, le "
            "port restera inutile — et une règle ouverte sans rien derrière est "
            "exactement ce que la page Audit signale comme un oubli. Vérifie d'abord "
            "la liste des ports en écoute, et n'ouvre que ce dont tu as réellement "
            "besoin depuis l'extérieur."
        ),
    ),
    Geste(
        geste_id="purger_log_conteneur",
        libelle="Vider le fichier de log d'un conteneur",
        # `sudo` sur `truncate` seulement : le `$(docker inspect …)` s'évalue
        # avant, sous l'utilisateur SSH, à qui le groupe docker suffit. Un seul
        # `sudo` dans la commande, c'est ce qu'attend `preparer_sudo`.
        commande=(
            "sudo truncate -s 0 $(docker inspect --format '{{.LogPath}}' "
            f"{JETON_CONTENEUR})"
        ),
        explication=(
            "Remet à zéro le fichier `-json.log` du conteneur sans le supprimer — "
            "Docker continue d'écrire dedans, ce qu'une suppression casserait. Libère "
            "immédiatement la place occupée. Ce que ça NE répare PAS : le fichier "
            "repoussera exactement pareil tant que la rotation des logs n'est pas "
            "configurée (page Audit, règle « rotation des logs »). Tu perds l'historique "
            "des logs de ce conteneur."
        ),
    ),
    Geste(
        geste_id="relancer_docker",
        libelle="Relancer le démon Docker",
        commande="sudo systemctl restart docker",
        explication=(
            "TRÈS SENSIBLE. Redémarre le moteur Docker entier. Tous les conteneurs sont "
            "arrêtés, et seuls ceux dont la politique de redémarrage vaut « always » ou "
            "« unless-stopped » reviendront tout seuls : les autres resteront à terre "
            "jusqu'à ce que tu les relances à la main. Vérifie d'abord la règle "
            "« politique de redémarrage » de la page Audit — l'ordre des deux gestes "
            "n'est pas indifférent. Ce que ça NE répare PAS : une erreur de syntaxe "
            "dans le fichier de réglages du démon, `/etc/docker/daemon.json`, qui "
            "empêchera justement le démon de repartir — relis-le avant de relancer."
        ),
    ),
    Geste(
        geste_id="voir_logs_conteneur",
        libelle="Ouvrir les logs du conteneur (page Logs)",
        commande="# action locale : ouvre la page Logs, aucune commande envoyée au serveur",
        explication=(
            "Bascule vers la page Logs et lance le suivi en direct du conteneur. Ce "
            "n'est pas une réparation, c'est l'étape suivante de l'enquête : quand un "
            "conteneur redémarre en boucle, la réponse est dans les lignes qu'il écrit "
            "juste avant de mourir, et il faut les regarder défiler pour les attraper. "
            "Aucune commande n'est envoyée au serveur par ce geste, et rien n'est "
            "modifié nulle part."
        ),
        sensible=False,   # exception justifiée : navigation locale, zéro effet distant
    ),
    Geste(
        geste_id="voir_logs_volumineux",
        libelle="Voir ce qui occupe le disque (page Santé serveur)",
        commande=("# action locale : ouvre la page Santé serveur, aucune commande "
                  "envoyée au serveur"),
        explication=(
            "Bascule vers la page Santé serveur, qui détaille l'espace occupé par "
            "Docker et "
            "propose le ménage ciblé (conteneurs arrêtés, images orphelines, cache de "
            "build). Ce n'est pas une réparation en soi : c'est l'endroit où l'on voit "
            "d'abord ce qui sera supprimé avant de décider. Aucune commande n'est "
            "envoyée au serveur par ce geste, et rien n'est modifié nulle part."
        ),
        sensible=False,   # exception justifiée : navigation locale, zéro effet distant
    ),
)


# ============================================================================
#                                 SYMPTÔMES
# ============================================================================
# En langage d'utilisateur, jamais de technicien : on choisit ce qu'on CONSTATE,
# pas ce qu'on soupçonne. L'ordre des vérifications va du plus fréquent au plus
# rare — c'est tout l'intérêt d'un diagnostic guidé par rapport à une liste de
# commandes à taper.
CHECKLIST_SSH: tuple[str, ...] = (
    "Vérifie d'abord que CE PC a bien accès à Internet (ouvre n'importe quel site). "
    "Une box redémarrée coupe l'accès des deux côtés, et c'est la moitié des cas.",
    "Teste la joignabilité de la machine : dans PowerShell, "
    "« Test-NetConnection <adresse-du-serveur> -Port 22 ». "
    "« TcpTestSucceeded : True » veut dire que SSH répond et que le problème est "
    "ailleurs (clé, utilisateur, mot de passe).",
    "Cause n°1 — l'adresse du serveur a changé. Sur une box domestique, un "
    "redémarrage suffit à réattribuer une autre adresse locale. Regarde la liste des "
    "appareils dans l'interface de ta box, et donne-lui un bail statique — la "
    "réservation d'adresse, dans la rubrique DHCP de la box — pour que ça ne "
    "recommence pas.",
    "Cause n°2 — ton adresse a été bannie. Après quelques essais ratés, fail2ban "
    "bloque l'adresse depuis laquelle tu te connectes ; UFW peut aussi ne l'autoriser "
    "que depuis une liste précise. Essaie depuis une autre connexion (partage de "
    "connexion du téléphone) : si ça passe, c'est ça.",
    "Cause n°3 — le service SSH est arrêté sur le serveur. C'est la plus rare, et "
    "c'est aussi la seule qui demande d'aller sur place.",
    "Recours final : branche un écran et un clavier sur la machine, connecte-toi "
    "localement, puis « sudo systemctl status ssh » pour l'état du service et "
    "« sudo fail2ban-client unban <ton-adresse> » pour te débannir. "
    "Rien de tout cela ne peut se faire à distance : c'est précisément l'accès "
    "distant qui est cassé.",
)

SYMPTOMES: tuple[Symptome, ...] = (
    Symptome(
        symptome_id="service_muet",
        titre="Un service ne répond plus",
        description=(
            "Une page qui ne s'affiche plus, une application mobile qui n'arrive plus à "
            "se synchroniser. On part du conteneur, puis on remonte vers le système et "
            "le réseau."
        ),
        verifications=(
            "conteneur_etat",
            "conteneur_sante",
            "conteneur_logs",
            "conteneur_ports",
            "disque",
            "docker_actif",
            "ports_ecoute",
            # Les deux dernières regardent le CHEMIN D'ACCÈS plutôt que le
            # service : un service « qui ne répond plus » depuis chez soi mais
            # qui va très bien est presque toujours une adresse bannie par
            # fail2ban (ses jails couvrent aussi le proxy, pas seulement SSH),
            # et le journal systemd date le dernier redémarrage du serveur —
            # ce qui explique souvent tout le reste. C'est aussi le seul
            # rattachement de ces deux vérifications : le symptôme SSH, leur
            # domicile naturel, est manuel et n'exécute rien.
            "fail2ban",
            "journal_ssh",
        ),
    ),
    Symptome(
        symptome_id="conteneur_boucle",
        titre="Un conteneur redémarre en boucle",
        description=(
            "Le service marche par intermittence, ou le tableau de bord montre un "
            "conteneur qui passe son temps à repartir. On commence par confirmer la "
            "boucle, puis on cherche pourquoi il n'arrive pas à démarrer."
        ),
        verifications=(
            "conteneur_redemarrages",
            "conteneur_sortie",
            "conteneur_logs",
            "oom",
            "disque",
            "journal_docker",
        ),
    ),
    Symptome(
        symptome_id="disque_plein",
        titre="Il n'y a plus de place sur le disque",
        description=(
            "Des écritures qui échouent, des « No space left on device » dans les logs. "
            "Les deux premières vérifications se lisent ensemble : l'espace ET les "
            "inodes, car un disque peut être plein des deux façons."
        ),
        verifications=(
            "disque",
            "inodes",
            "logs_docker_espace",
            "images_orphelines",
            "journal_docker",
        ),
    ),
    Symptome(
        symptome_id="serveur_lent",
        titre="Le serveur est lent",
        description=(
            "Tout répond, mais avec des secondes d'attente. On regarde d'abord les trois "
            "ressources qui se partagent la machine — mémoire, charge, disque — avant de "
            "soupçonner une application en particulier."
        ),
        verifications=("memoire", "charge", "oom", "disque", "inodes", "docker_actif"),
    ),
    Symptome(
        symptome_id="certificat_https",
        titre="Un site en HTTPS affiche une erreur de certificat",
        description=(
            "Le navigateur affiche un avertissement de sécurité en pleine page. Saisis "
            "le domaine concerné avant de lancer le diagnostic : ces vérifications "
            "interrogent ce domaine précis."
        ),
        verifications=("certificat", "dns", "heure", "ports_ecoute", "ufw"),
    ),
    Symptome(
        symptome_id="ssh_injoignable",
        titre="Je n'arrive plus à me connecter en SSH",
        description=(
            "Une application qui a besoin de SSH ne peut pas diagnostiquer une panne de "
            "SSH : si elle pouvait exécuter la moindre commande, il n'y aurait pas de "
            "panne. Ce symptôme est donc une checklist à faire depuis CE PC, sans "
            "aucune commande envoyée au serveur. Le dire franchement vaut mieux que "
            "d'afficher un bouton qui ne peut pas marcher."
        ),
        manuel=True,
        checklist=CHECKLIST_SSH,
    ),
)


# ============================================================================
#                                  ACCÈS
# ============================================================================
def verification(verif_id: str) -> Verification | None:
    """La vérification d'identifiant donné, ou None."""
    for verif in VERIFICATIONS:
        if verif.verif_id == verif_id:
            return verif
    return None


def geste(geste_id: str) -> Geste | None:
    """Le geste d'identifiant donné, ou None."""
    for item in GESTES:
        if item.geste_id == geste_id:
            return item
    return None


def symptome(symptome_id: str) -> Symptome | None:
    """Le symptôme d'identifiant donné, ou None."""
    for item in SYMPTOMES:
        if item.symptome_id == symptome_id:
            return item
    return None


def verifications_de(symptome_id: str) -> list[Verification]:
    """Les vérifications d'un symptôme, dans l'ordre, ids inconnus ignorés."""
    cible = symptome(symptome_id)
    if cible is None:
        return []
    resultat = []
    for verif_id in cible.verifications:
        trouvee = verification(verif_id)
        if trouvee is not None:
            resultat.append(trouvee)
    return resultat


def toutes_verifications_automatiques() -> list[Verification]:
    """Les vérifications du bouton « Tout vérifier », sans doublon.

    Union des vérifications de tous les symptômes NON manuels, dans l'ordre de
    première apparition. Celles qui exigent un domaine sont incluses : la page
    les écarte elle-même si aucun domaine n'est saisi — décider ici reviendrait
    à mettre de la logique d'interface dans un fichier de données.
    """
    vues: list[Verification] = []
    ids: set[str] = set()
    for item in SYMPTOMES:
        if item.manuel:
            continue
        for verif_id in item.verifications:
            if verif_id in ids:
                continue
            trouvee = verification(verif_id)
            if trouvee is not None:
                ids.add(verif_id)
                vues.append(trouvee)
    return vues


def jetons(config=None, conteneur: str = "", stack: str = "", domaine: str = "",
           ip: str = "", port: str = "") -> dict[str, str]:
    """Table de substitution passée à `core.parcours.substituer_jetons`.

    Les valeurs vides sont conservées : une commande dont le jeton n'est pas
    résolu doit rester visiblement incomplète à l'écran plutôt que de partir sur
    le serveur avec un trou au milieu. La page vérifie `besoin_conteneur` /
    `besoin_domaine` avant de lancer quoi que ce soit.
    """
    stacks_dir = "/opt/stacks"
    backup_dir = "/srv/backups"
    if config is not None:
        stacks_dir = str(config.get("stacks_dir") or stacks_dir)
        backup_dir = str(config.get("backup_dir") or backup_dir)
    return {
        JETON_STACKS: stacks_dir,
        JETON_BACKUP: backup_dir,
        JETON_CONTENEUR: conteneur,
        JETON_STACK: stack,
        JETON_DOMAINE: domaine,
        JETON_IP: ip,
        JETON_PORT: port,
    }
