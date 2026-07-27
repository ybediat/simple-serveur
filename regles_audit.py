"""regles_audit.py — contenu du module « Audit & bonnes pratiques » (brique 32).

Même philosophie que `diagnostics.py` (31), `postgres_fiches.py` (21) et
`parcours/*.py` : ce fichier ne contient aucune interface. Il porte les règles,
leur explication, et la fonction qui calcule leur verdict — contribuable sans
toucher à la page.

**Dépannage et Audit ne répondent pas à la même question.** Le Dépannage traite
un serveur **en panne** : symptôme → pistes. L'Audit examine un serveur **qui
marche** et cherche ce qui le fera tomber plus tard. C'est pour cela que le
vocabulaire diffère (`conforme` / `à améliorer` / `problème` / `non
applicable`), tout en retombant sur les **trois couleurs** de la brique 24 —
pas de quatrième palette.

Deux règles de rédaction, vérifiées par `tests/test_audit.py` :

1. **Toute commande est en lecture seule.** Un audit complet doit pouvoir se
   lancer sans réfléchir sur un serveur en production. Les corrections vivent
   exclusivement dans les `Geste`, tous derrière `confirm_action`.
2. **Chaque `pourquoi` dépasse 200 caractères et dit ce qui arrive si on ne
   fait rien.** Une règle qu'on ne comprend pas est une règle qu'on désactive.

Ce qui est délibérément ABSENT : toute note sur 100. Pondérer treize règles
hétérogènes serait arbitraire, et un serveur « à 100 % » n'existe pas. On
compte, on ne note pas.
"""
from __future__ import annotations

import posixpath
import shlex
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from core import diagnostic
from diagnostics import Geste   # même forme de geste que la 31, pas un jumeau

# Domaines d'affichage, dans l'ordre de la page.
DOMAINE_REDEMARRAGE = "Résistance aux redémarrages"
DOMAINE_DISQUE = "Hygiène du disque"
DOMAINE_EXPOSITION = "Certificats et exposition"
DOMAINE_SAUVEGARDES = "Sauvegardes et mises à jour"

DOMAINES = (DOMAINE_REDEMARRAGE, DOMAINE_DISQUE, DOMAINE_EXPOSITION,
            DOMAINE_SAUVEGARDES)

# Jetons substitués par `core.parcours.substituer_jetons` (comme la brique 31).
JETON_STACKS = "__STACKS_DIR__"
JETON_BACKUP = "__BACKUP_DIR__"

# Au-delà, un test de restauration date trop : une sauvegarde jamais testée
# n'est qu'une intention.
RESTAURATION_MOIS = 6
RESTAURATION_JOURS = RESTAURATION_MOIS * 30

# Ligne à ajouter au compose pour corriger `restart_policy`. L'appli l'AFFICHE
# et ne l'écrit jamais : modifier un `compose.yaml` à la place de l'utilisateur
# serait une écriture silencieuse dans un fichier qu'il maintient (Dockge est
# là pour ça).
LIGNE_COMPOSE_RESTART = "    restart: unless-stopped"

# Ligne à ajouter à `/etc/systemd/journald.conf` pour corriger `journal_systemd`.
# Même principe que ci-dessus : AFFICHÉE, jamais écrite — journald.conf n'a pas
# la garde d'écriture atomique dont bénéficie `daemon.json` (core/fail2ban.py),
# donc l'appli ne se risque pas à y toucher elle-même.
LIGNE_JOURNALD_MAXUSE = "SystemMaxUse=500M"


# ============================================================================
#                                 STRUCTURES
# ============================================================================
@dataclass(frozen=True)
class Sortie:
    """Résultat d'une commande de règle (ce que la page transmet au juge)."""

    commande: str
    stdout: str = ""
    code: int = 0

    @property
    def abouti(self) -> bool:
        return self.code == 0


@dataclass(frozen=True)
class ResultatRegle:
    """Verdict d'une règle, sa ligne de résumé et son détail dépliable."""

    verdict: str = diagnostic.NON_APPLICABLE
    resume: str = ""
    detail: str = ""
    correction: str = ""      # texte à afficher (jamais exécuté) — cf. restart_policy

    @property
    def niveau(self) -> str:
        """Niveau brique 24 (`info` / `reussite` / `probleme`)."""
        return diagnostic.niveau_audit(self.verdict)

    @property
    def libelle(self) -> str:
        return diagnostic.LIBELLES_AUDIT.get(self.verdict, self.verdict)


@dataclass(frozen=True)
class Regle:
    """Un réglage vérifié, expliqué, et corrigé quand c'est sûr."""

    regle_id: str
    domaine: str
    libelle: str
    pourquoi: str                              # > 200 caractères, avec le POURQUOI
    commandes: Callable[[dict], list[str]]     # contexte → commandes lecture seule
    juge: Callable[[list, dict], ResultatRegle]
    geste_id: str = ""

    def construire(self, contexte: dict) -> list[str]:
        """Commandes à exécuter. Liste vide = règle purement locale."""
        try:
            return list(self.commandes(contexte or {}) or [])
        except Exception:  # noqa: BLE001 — une règle ne fait jamais tomber la page
            return []

    def evaluer(self, sorties: list[Sortie], contexte: dict) -> ResultatRegle:
        """Verdict de la règle. Un juge qui lève rend « non applicable »."""
        try:
            return self.juge(list(sorties or []), contexte or {})
        except Exception:  # noqa: BLE001
            return ResultatRegle(
                diagnostic.NON_APPLICABLE,
                "cette règle n'a pas pu être évaluée sur ce serveur",
            )


def _aucune(_contexte: dict) -> list[str]:
    """Règle locale : rien à demander au serveur."""
    return []


def _indetermine(motif: str) -> ResultatRegle:
    """Sortie manquante ou commande en échec : jamais « problème »."""
    return ResultatRegle(diagnostic.NON_APPLICABLE, motif)


def _premiere(sorties: list[Sortie]) -> Sortie | None:
    return sorties[0] if sorties else None


# ============================================================================
#                    DOMAINE 1 — RÉSISTANCE AUX REDÉMARRAGES
# ============================================================================
def _juger_restart_policy(sorties, _contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("la liste des conteneurs n'a pas pu être lue")
    politiques = diagnostic.parse_restart_policies(sortie.stdout)
    if not politiques:
        return _indetermine("aucun conteneur trouvé sur ce serveur")
    fragiles = [p for p in politiques if not p.sure]
    if not fragiles:
        return ResultatRegle(
            diagnostic.CONFORME,
            f"les {len(politiques)} conteneurs reviennent seuls après un redémarrage",
        )
    noms = ", ".join(f"{p.nom} ({p.politique})" for p in fragiles)
    return ResultatRegle(
        diagnostic.PROBLEME,
        f"{len(fragiles)} conteneur(s) sur {len(politiques)} ne reviendront pas seuls",
        f"Concernés : {noms}.\n\n"
        "Ajoutez la ligne ci-dessous au service correspondant dans son "
        "`compose.yaml` (depuis Dockge), puis recréez la stack. L'application "
        "ne modifie pas vos fichiers compose : ils sont à vous.",
        LIGNE_COMPOSE_RESTART,
    )


def _juger_docker_enabled(sorties, _contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None:
        return _indetermine("l'état du service Docker n'a pas pu être lu")
    # PIÈGE : `systemctl is-enabled` rend le code 1 pour « disabled ». Ce n'est
    # pas une erreur, c'est la réponse — juger sur le code retour ferait passer
    # le cas fautif pour un trou d'information, et la règle ne servirait à rien.
    mot = diagnostic.parse_systemctl(sortie.stdout)
    if not mot:
        return _indetermine("aucune réponse de systemctl")
    if mot == "enabled":
        return ResultatRegle(diagnostic.CONFORME,
                             "Docker démarre automatiquement au boot")
    if mot in ("disabled", "masked"):
        return ResultatRegle(
            diagnostic.PROBLEME,
            f"Docker ne démarre PAS au boot (« {mot} »)",
            "Après une coupure de courant, le serveur redémarrera sans aucun "
            "conteneur, et la politique de redémarrage des conteneurs n'y "
            "changera rien : c'est le moteur lui-même qui manquerait.",
        )
    return ResultatRegle(diagnostic.A_AMELIORER,
                         f"état inhabituel du service Docker : « {mot} »")


def _juger_stacks_au_boot(sorties, contexte) -> ResultatRegle:
    if len(sorties) < 2 or not all(s.abouti for s in sorties):
        return _indetermine("la comparaison des stacks n'a pas pu être faite")
    actifs = {p.nom for p in diagnostic.parse_compose_ls(sorties[0].stdout)}
    dossiers = []
    for ligne in (sorties[1].stdout or "").splitlines():
        chemin = ligne.strip()
        if not chemin:
            continue
        nom = posixpath.basename(posixpath.dirname(chemin))
        if nom and nom not in dossiers:
            dossiers.append(nom)
    if not dossiers:
        return _indetermine("aucun fichier compose trouvé")
    arretees = [nom for nom in dossiers if nom not in actifs]
    if not arretees:
        return ResultatRegle(diagnostic.CONFORME,
                             f"les {len(dossiers)} stacks déclarées sont lancées")
    return ResultatRegle(
        diagnostic.A_AMELIORER,
        f"{len(arretees)} stack(s) déclarée(s) mais pas lancée(s)",
        f"Concernées : {', '.join(arretees)}.\n\n"
        "Une stack arrêtée depuis un redémarrage passe inaperçue pendant des "
        "mois. Vérifiez d'abord si c'est volontaire — auquel cas il n'y a rien "
        "à faire.\n\n"
        "Sinon, deux façons de la relancer : depuis Dockge, ouvrez la stack et "
        "cliquez sur Démarrer — c'est l'outil déjà en place pour ça, et il "
        "connaît l'ordre de ses propres services. Si ses conteneurs ont "
        "seulement été arrêtés (pas supprimés), le Tableau de bord de cette "
        "appli peut aussi les redémarrer un par un. En ligne de commande, "
        "depuis le dossier de la stack : `docker compose up -d`.",
    )


# ============================================================================
#                       DOMAINE 2 — HYGIÈNE DU DISQUE
# ============================================================================
def _juger_log_rotation(sorties, _contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("`daemon.json` n'a pas pu être lu")
    etat = diagnostic.parse_daemon_json(sortie.stdout)
    if etat.rotation_active:
        return ResultatRegle(
            diagnostic.CONFORME,
            f"rotation active (max-size {etat.max_size}, max-file {etat.max_file or '?'})",
        )
    if etat.etat == "invalide":
        return ResultatRegle(
            diagnostic.PROBLEME,
            "`/etc/docker/daemon.json` existe mais n'est pas un JSON valide",
            "L'application ne propose AUCUNE correction dans ce cas : écraser un "
            "fichier qu'on n'a pas su lire serait la pire réponse possible. "
            "Ouvrez-le vous-même — un démon Docker qui redémarre sur un "
            "`daemon.json` invalide ne repart pas du tout.",
        )
    manque = {"absent": "le fichier n'existe pas",
              "vide": "le fichier est vide",
              "sans_log_opts": "le fichier existe mais ne borne pas les logs"}
    return ResultatRegle(
        diagnostic.PROBLEME,
        f"aucune rotation des logs Docker ({manque.get(etat.etat, etat.etat)})",
        "Sans `log-opts`, un conteneur bavard écrit un `-json.log` qui grossit "
        "SANS AUCUNE LIMITE : quelques mois suffisent à remplir un disque.\n\n"
        "Deux avertissements avant de corriger :\n"
        "• la rotation ne s'applique qu'aux conteneurs RECRÉÉS ensuite, pas aux "
        "conteneurs déjà en cours ;\n"
        "• redémarrer le démon coupe tous les conteneurs sans politique de "
        "redémarrage adéquate. Traitez donc la règle « politique de "
        "redémarrage » AVANT celle-ci : l'ordre des deux corrections n'est pas "
        "indifférent.",
    )


def _juger_logs_volumineux(sorties, _contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("la taille des fichiers de log n'a pas pu être lue")
    fichiers = diagnostic.parse_du_logs(sortie.stdout)
    if not fichiers:
        return ResultatRegle(diagnostic.CONFORME, "aucun fichier de log mesurable")
    gros = [f for f in fichiers if f.mega_octets > diagnostic.SEUIL_LOG_MO]
    if not gros:
        plus_gros = fichiers[0]
        return ResultatRegle(
            diagnostic.CONFORME,
            f"le plus gros fichier de log fait {plus_gros.taille_lisible}",
        )
    lignes = "\n".join(f"• {f.taille_lisible} — {f.chemin}" for f in gros)
    verdict = (diagnostic.PROBLEME if gros[0].mega_octets > 1024
               else diagnostic.A_AMELIORER)
    return ResultatRegle(
        verdict,
        f"{len(gros)} fichier(s) de log au-delà de {diagnostic.SEUIL_LOG_MO} Mo "
        f"(le plus gros : {gros[0].taille_lisible})",
        f"{lignes}\n\n"
        "Le geste vide le fichier sans le supprimer — Docker écrit dedans, une "
        "suppression casserait la sortie du conteneur. Mais vider ne règle rien "
        "de durable : sans rotation (règle ci-dessus), le fichier repousse à "
        "l'identique.",
    )


def _juger_croissance_disque(sorties, contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("l'occupation du disque n'a pas pu être lue")
    lignes = diagnostic.parse_df(sortie.stdout)
    pire = diagnostic.pire_occupation(lignes)
    if pire is None:
        return _indetermine("aucune ligne de `df` exploitable")
    precedente = (contexte.get("occupation_precedente") or {})
    date = contexte.get("date_occupation_lisible") or ""
    if not precedente:
        return ResultatRegle(
            diagnostic.NON_APPLICABLE,
            f"première mesure : {pire.target} occupé à {pire.pct} %",
            "L'occupation vient d'être mémorisée. Au prochain audit, cette "
            "règle affichera la TENDANCE — et une tendance vaut bien mieux "
            "qu'un pourcentage instantané pour anticiper un disque plein.",
        )
    ecarts = []
    pire_ecart = 0
    for ligne in lignes:
        avant = precedente.get(ligne.target)
        if avant is None:
            continue
        delta = ligne.pct - int(avant)
        signe = "+" if delta > 0 else ""
        ecarts.append(f"• {ligne.target} : {avant} % → {ligne.pct} % ({signe}{delta} pts)")
        pire_ecart = max(pire_ecart, delta)
    if not ecarts:
        return ResultatRegle(diagnostic.NON_APPLICABLE,
                             "aucun point de montage commun avec le précédent audit")
    detail = "\n".join(ecarts)
    depuis = f" depuis le {date}" if date else ""
    if pire_ecart >= 10:
        return ResultatRegle(
            diagnostic.A_AMELIORER,
            f"le disque s'est rempli de {pire_ecart} points{depuis}",
            detail + "\n\nÀ ce rythme, regardez ce qui grossit (logs de "
                     "conteneurs, sauvegardes, cache de build) avant que ce ne "
                     "soit une panne.",
        )
    return ResultatRegle(
        diagnostic.CONFORME,
        f"occupation stable{depuis} (plus forte hausse : {pire_ecart} points)",
        detail,
    )


def _juger_journal_systemd(sorties, _contexte) -> ResultatRegle:
    if len(sorties) < 2:
        return _indetermine("le journal systemd n'a pas pu être mesuré")
    usage, conf = sorties[0], sorties[1]
    if not usage.abouti:
        return _indetermine("`journalctl --disk-usage` n'a pas abouti")
    octets = diagnostic.parse_journal_usage(usage.stdout)
    if octets is None:
        return _indetermine("taille du journal illisible")
    lisible = diagnostic.taille_lisible(octets)
    borne = False
    for ligne in (conf.stdout or "").splitlines():
        nue = ligne.strip()
        if nue.startswith("#"):
            continue
        if nue.lower().startswith("systemmaxuse=") and nue.split("=", 1)[1].strip():
            borne = True
            break
    if borne:
        return ResultatRegle(diagnostic.CONFORME,
                             f"journal borné par `SystemMaxUse` ({lisible} occupés)")
    go = octets / (1024 ** 3)
    if go >= diagnostic.SEUIL_JOURNAL_GO:
        return ResultatRegle(
            diagnostic.A_AMELIORER,
            f"le journal systemd occupe {lisible} sans limite déclarée",
            "Même piège que les logs Docker, en moins connu : sans "
            "`SystemMaxUse=` dans `/etc/systemd/journald.conf`, le journal "
            "grandit jusqu'à ce que systemd décide lui-même (10 % du disque).\n\n"
            "Pour corriger, sur le serveur :\n"
            "1. `sudo nano /etc/systemd/journald.conf`\n"
            "2. dans la section `[Journal]`, ajoutez (ou décommentez et "
            "modifiez) la ligne ci-dessous ;\n"
            "3. enregistrez, puis appliquez avec "
            "`sudo systemctl restart systemd-journald`.\n\n"
            "Contrairement au redémarrage du démon Docker (règle de rotation "
            "des logs), celui-ci est sans risque : il ne touche qu'à la "
            "journalisation, aucun autre service n'est interrompu. Il ne "
            "supprime rien non plus — il fait juste le ménage au-delà de la "
            "limite désormais fixée, en gardant les entrées les plus récentes, "
            "qui sont aussi les seules qu'on relit en pratique.",
            LIGNE_JOURNALD_MAXUSE,
        )
    return ResultatRegle(diagnostic.CONFORME,
                         f"journal systemd raisonnable ({lisible})")


# ============================================================================
#                    DOMAINE 3 — CERTIFICATS ET EXPOSITION
# ============================================================================
def _commandes_certificats(contexte: dict) -> list[str]:
    return [diagnostic.build_enddate_cmd(d) for d in (contexte.get("domaines") or [])]


def _juger_certificats(sorties, contexte) -> ResultatRegle:
    domaines = list(contexte.get("domaines") or [])
    if not domaines:
        # Aucune découverte automatique : pas d'API NPM (hors périmètre, cf.
        # PLAN). Sans domaine déclaré, la règle ne s'applique pas — ce n'est
        # surtout pas une erreur.
        return ResultatRegle(
            diagnostic.NON_APPLICABLE,
            "aucun domaine déclaré",
            "Ajoutez les domaines à surveiller dans la colonne de gauche. Ils "
            "sont enregistrés localement, pour ce serveur uniquement.",
        )
    maintenant = contexte.get("maintenant")
    lignes, verdicts = [], []
    for domaine, sortie in zip(domaines, sorties):
        if not sortie.abouti:
            lignes.append(f"• {domaine} : injoignable en HTTPS")
            verdicts.append(diagnostic.NON_APPLICABLE)
            continue
        jours = diagnostic.jours_restants(
            diagnostic.parse_enddate(sortie.stdout), maintenant
        )
        verdict = diagnostic.verdict_certificat(jours)
        verdicts.append(verdict)
        if jours is None:
            lignes.append(f"• {domaine} : date d'expiration illisible")
        elif jours < 0:
            lignes.append(f"• {domaine} : EXPIRÉ depuis {abs(jours)} jour(s)")
        else:
            lignes.append(f"• {domaine} : {jours} jour(s) restants")
    detail = "\n".join(lignes)
    if diagnostic.PROBLEME in verdicts:
        pire = diagnostic.PROBLEME
        resume = "un certificat au moins expire dans moins de " \
                 f"{diagnostic.CERT_JOURS_PROBLEME} jours (ou est déjà expiré)"
        detail += (
            "\n\nCe que ça veut dire concrètement : le renouvellement "
            "automatique de NPM a déjà échoué au moins une fois. Ouvrez NPM, "
            "l'onglet SSL du Proxy Host concerné, et lancez « Renew now ». Si "
            "ça échoue à nouveau, vérifiez dans l'ordre : que le port 80 est "
            "bien accessible depuis Internet vers ce domaine (Let's Encrypt en "
            "a besoin pour valider), que le DNS pointe toujours vers votre IP, "
            "et que vous n'avez pas atteint le quota hebdomadaire de "
            "Let's Encrypt pour ce domaine."
        )
    elif diagnostic.A_AMELIORER in verdicts:
        pire = diagnostic.A_AMELIORER
        resume = f"un certificat expire dans moins de " \
                 f"{diagnostic.CERT_JOURS_AVERTISSEMENT} jours"
        detail += (
            "\n\nUn certificat se renouvelle normalement 30 jours avant son "
            "terme : en dessous de ce seuil, c'est encore probablement normal, "
            "mais si l'échéance approche vraiment, ouvrez NPM et vérifiez "
            "l'onglet SSL du Proxy Host concerné."
        )
    elif diagnostic.CONFORME in verdicts:
        pire = diagnostic.CONFORME
        resume = f"les {len(domaines)} certificats sont valides plus de " \
                 f"{diagnostic.CERT_JOURS_AVERTISSEMENT} jours"
    else:
        pire = diagnostic.NON_APPLICABLE
        resume = "aucun domaine n'a pu être interrogé"
    return ResultatRegle(pire, resume, detail)


def _juger_ports_exposes(sorties, _contexte) -> ResultatRegle:
    if len(sorties) < 2 or not all(s.abouti for s in sorties):
        return _indetermine("le croisement des ports n'a pas pu être fait")
    publies = diagnostic.parse_ports_publies(sorties[0].stdout)
    ouverts = diagnostic.parse_ufw_ports(sorties[1].stdout)
    orphelins = [p for p in ouverts if p not in publies]
    proxy_present = 80 in publies and 443 in publies
    directs = [p for p in publies if p not in (80, 81, 443)] if proxy_present else []
    lignes = []
    if orphelins:
        lignes.append(
            "Ports ouverts dans UFW sans conteneur derrière : "
            + ", ".join(str(p) for p in orphelins)
            + ".\nCe sont des règles oubliées après la suppression d'un service. "
              "Elles n'exposent rien aujourd'hui, mais elles exposeront le "
              "prochain service qui prendra ce port.\n"
              "Pour retirer une règle : `sudo ufw status numbered` pour "
              "repérer son numéro (celui qui correspond au port ci-dessus), "
              "puis `sudo ufw delete <numéro>`."
        )
    if directs:
        lignes.append(
            "Ports publiés sur toutes les interfaces alors qu'un reverse proxy "
            "est en place (80 et 443 publiés) : "
            + ", ".join(str(p) for p in directs)
            + ".\nCes services sont joignables en direct, sans passer par le "
              "proxy — donc sans HTTPS ni journalisation. Publier sur "
              "`127.0.0.1:` au lieu de `0.0.0.0:` les réserve au proxy.\n"
              "Dans le `compose.yaml` du service concerné (Dockge), changez "
              "par exemple `\"8080:8080\"` en `\"127.0.0.1:8080:8080\"`, puis "
              "recréez le conteneur — la page « Mises à jour » sait le faire."
        )
    if not lignes:
        return ResultatRegle(diagnostic.CONFORME,
                             "aucun port ouvert sans service, aucune exposition inutile")
    return ResultatRegle(
        diagnostic.A_AMELIORER,
        f"{len(orphelins)} règle(s) UFW orpheline(s), "
        f"{len(directs)} service(s) exposé(s) hors du proxy",
        "\n\n".join(lignes),
    )


def _juger_ssh_durci(sorties, _contexte) -> ResultatRegle:
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("la configuration SSH n'a pas pu être lue")
    reglages = diagnostic.parse_sshd_config(sortie.stdout)
    if not reglages:
        return _indetermine("aucune directive SSH lisible")
    ecarts, lignes = [], []
    root = reglages.get("permitrootlogin", "")
    mdp = reglages.get("passwordauthentication", "")
    port = reglages.get("port", "22")
    lignes.append(f"• PermitRootLogin : {root or 'non déclaré (défaut : prohibit-password)'}")
    lignes.append(f"• PasswordAuthentication : {mdp or 'non déclaré (défaut : yes)'}")
    lignes.append(f"• Port : {port}")
    if root == "yes":
        ecarts.append("la connexion root par mot de passe est autorisée")
    if mdp in ("", "yes"):
        ecarts.append("l'authentification par mot de passe est active")
    rappel = (
        "\n\nCette règle est en LECTURE SEULE et le restera : modifier "
        "`sshd_config` depuis l'application est le meilleur moyen de perdre "
        "l'accès au serveur. Le parcours « Base saine » (Installation & guides) "
        "le fait dans le bon ordre, avec ses gardes anti-verrouillage — clé "
        "testée par une vraie connexion AVANT de couper le mot de passe."
    )
    if not ecarts:
        return ResultatRegle(diagnostic.CONFORME,
                             "accès SSH durci (pas de root, pas de mot de passe)",
                             "\n".join(lignes) + rappel)
    return ResultatRegle(
        diagnostic.A_AMELIORER,
        "; ".join(ecarts),
        "\n".join(lignes) + rappel,
    )


# ============================================================================
#                   DOMAINE 4 — SAUVEGARDES ET MISES À JOUR
# ============================================================================
def _commandes_sauvegardes(contexte: dict) -> list[str]:
    dossier = contexte.get("backup_dir") or "/srv/backups"
    return [
        f"find {shlex.quote(dossier)} -maxdepth 2 -type f "
        f"-printf '%T@|%s|%p\\n' | sort -rn"
    ]


def _parse_listing(sortie: str) -> list[tuple[float, str]]:
    """`mtime|taille|chemin` → (mtime, chemin). Lignes illisibles ignorées.

    Écrit ici plutôt qu'importé de `modules/backups.py` : l'audit lit le travail
    des autres briques par les modules `core/`, jamais par une page — coupler
    deux pages pour six lignes de parsing serait un mauvais échange.
    """
    entrees = []
    for ligne in (sortie or "").splitlines():
        morceaux = ligne.strip().split("|", 2)
        if len(morceaux) != 3:
            continue
        try:
            entrees.append((float(morceaux[0]), morceaux[2].strip()))
        except ValueError:
            continue
    return entrees


def _juger_sauvegardes_recentes(sorties, contexte) -> ResultatRegle:
    sources = list(contexte.get("sources") or [])
    if not sources:
        return ResultatRegle(
            diagnostic.NON_APPLICABLE,
            "aucune source de sauvegarde déclarée",
            "Déclarez vos applications dans la page « Sauvegardes », section "
            "« Sources de sauvegarde » : c'est ce registre que cette règle "
            "relit pour savoir quoi vérifier.",
        )
    sortie = _premiere(sorties)
    if sortie is None or not sortie.abouti:
        return _indetermine("le dossier de sauvegardes n'a pas pu être listé")
    entrees = _parse_listing(sortie.stdout)
    maintenant = (contexte.get("maintenant") or datetime.now()).timestamp()
    seuil = int(contexte.get("backup_warn_days") or 7)
    lignes, verdicts = [], []
    for source in sources:
        cle = (getattr(source, "id", "") or "").lower()
        recents = [m for m, chemin in entrees if cle and cle.split("-")[0] in chemin.lower()]
        if not recents:
            lignes.append(f"• {getattr(source, 'libelle', cle) or cle} : AUCUNE archive trouvée")
            verdicts.append(diagnostic.PROBLEME)
            continue
        jours = int((maintenant - max(recents)) // 86400)
        libelle = getattr(source, "libelle", cle) or cle
        lignes.append(f"• {libelle} : dernière archive il y a {jours} jour(s)")
        if jours > seuil * 2:
            verdicts.append(diagnostic.PROBLEME)
        elif jours > seuil:
            verdicts.append(diagnostic.A_AMELIORER)
        else:
            verdicts.append(diagnostic.CONFORME)
    detail = ("\n".join(lignes) + "\n\nC'est toujours UNE source qui est "
              "oubliée, pas toutes : le chip global de la page « Santé serveur » "
              "ne le "
              "montre pas, ce détail par source si.")
    if diagnostic.PROBLEME in verdicts:
        manquantes = verdicts.count(diagnostic.PROBLEME)
        detail += (
            "\n\nPour une source sans aucune archive : ouvrez la page "
            "« Planificateur » et vérifiez que sa sauvegarde automatique est "
            "bien activée pour ce serveur — un script qui échoue en silence "
            "depuis des semaines est la cause la plus fréquente. Lancez "
            "ensuite une sauvegarde manuelle depuis la page « Sauvegardes » : "
            "si elle échoue aussi, l'erreur affichée dira pourquoi."
        )
        return ResultatRegle(diagnostic.PROBLEME,
                             f"{manquantes} source(s) sans sauvegarde récente", detail)
    if diagnostic.A_AMELIORER in verdicts:
        detail += (
            "\n\nSi l'écart se creuse au fil des audits, vérifiez d'abord la "
            "page « Planificateur » : une sauvegarde automatique désactivée ou "
            "en échec silencieux laisse l'ancienne archive en place, ce qui "
            "peut passer pour un simple retard."
        )
        return ResultatRegle(diagnostic.A_AMELIORER,
                             f"des sauvegardes dépassent {seuil} jours", detail)
    return ResultatRegle(diagnostic.CONFORME,
                         f"les {len(sources)} sources ont une archive de moins de "
                         f"{seuil} jours", detail)


def _juger_restauration_testee(_sorties, contexte) -> ResultatRegle:
    """Lit la date du dernier test dans l'HISTORIQUE (brique 24).

    C'était la seule inconnue du chantier : la brique 20 ne stocke nulle part la
    date de son dernier test de restauration. Elle écrit en revanche un
    événement d'historique à chaque test — c'est donc la source de vérité, et
    elle a le bon goût d'être déjà persistante et déjà par profil.
    """
    dernier = contexte.get("dernier_test_restauration")
    if dernier is None:
        return ResultatRegle(
            diagnostic.A_AMELIORER,
            "aucun test de restauration enregistré",
            "Une sauvegarde jamais testée n'est qu'une intention : rien ne "
            "prouve qu'elle se relit, ni qu'elle contient ce qu'on croit. La "
            "page Restauration sait le vérifier dans un environnement jetable, "
            "sans toucher au service en production.",
        )
    maintenant = contexte.get("maintenant") or datetime.now()
    jours = (maintenant.date() - dernier.date()).days
    date = dernier.strftime("%d/%m/%Y")
    if jours > RESTAURATION_JOURS:
        return ResultatRegle(
            diagnostic.A_AMELIORER,
            f"dernier test de restauration le {date}, il y a {jours} jours",
            f"Au-delà de {RESTAURATION_MOIS} mois, refaites-en un : le format "
            "des dumps, les versions d'images et le contenu des volumes ont "
            "changé entre-temps.",
        )
    return ResultatRegle(diagnostic.CONFORME,
                         f"restauration testée le {date} (il y a {jours} jours)")


def _juger_images_a_jour(_sorties, contexte) -> ResultatRegle:
    """Réutilise la détection de la brique 05, sans la refaire.

    Le décompte est calculé par la page avec `core/updates.py` (les mêmes
    commandes et le même `compare_digests` que la page Mises à jour) et déposé
    dans le contexte. Refaire ici une seconde détection, qui divergerait de la
    première au premier changement, aurait été le pire des deux mondes.
    """
    nombre = contexte.get("maj_disponibles")
    if nombre is None:
        return ResultatRegle(
            diagnostic.NON_APPLICABLE,
            "la détection des mises à jour n'a pas abouti",
            "Ouvrez la page « Mises à jour » : c'est elle qui porte la "
            "comparaison des empreintes d'images, et elle donne le détail par "
            "stack.",
        )
    if nombre == 0:
        return ResultatRegle(diagnostic.CONFORME,
                             "toutes les images sont à jour")
    return ResultatRegle(
        diagnostic.A_AMELIORER,
        f"{nombre} image(s) ont une mise à jour disponible",
        "Une image en retard n'est pas une panne, mais c'est là que vivent les "
        "correctifs de sécurité. Le détail par stack, et la mise à jour "
        "elle-même, sont sur la page « Mises à jour ».",
    )


# ============================================================================
#                                 LES RÈGLES
# ============================================================================
REGLES: tuple[Regle, ...] = (
    # ---------------------------------------- résistance aux redémarrages
    Regle(
        regle_id="restart_policy",
        domaine=DOMAINE_REDEMARRAGE,
        libelle="Chaque conteneur a une politique de redémarrage",
        pourquoi=(
            "Un conteneur créé sans `restart:` vaut « no » : après une coupure de "
            "courant ou un simple redémarrage du démon Docker, il ne revient PAS — "
            "et personne ne le découvre avant la panne, parce que tout allait bien "
            "tant que la machine ne s'était pas arrêtée. Les trois valeurs utiles : "
            "« no » ne relance jamais ; « always » relance toujours, y compris un "
            "conteneur que vous aviez arrêté volontairement ; « unless-stopped » "
            "relance après un redémarrage mais respecte un arrêt volontaire — c'est "
            "le bon défaut pour un serveur domestique. C'est LE réglage qui provoque "
            "les pannes du samedi soir."
        ),
        commandes=lambda _c: [diagnostic.build_restart_policies_cmd()],
        juge=_juger_restart_policy,
    ),
    Regle(
        regle_id="docker_enabled",
        domaine=DOMAINE_REDEMARRAGE,
        libelle="Le démon Docker démarre-t-il au boot ?",
        pourquoi=(
            "Une évidence… qui manque sur beaucoup de serveurs installés à la main, "
            "parce que le démon a été démarré une fois avec `systemctl start` et que "
            "personne n'a pensé au `enable` qui va avec. Tant que la machine ne "
            "redémarre pas, rien ne le signale. Le jour d'une coupure de courant, le "
            "serveur revient en ligne, répond au ping, accepte le SSH — et aucun "
            "service ne tourne. La politique de redémarrage des conteneurs n'y peut "
            "rien : c'est le moteur qui manque, pas les conteneurs."
        ),
        commandes=lambda _c: [diagnostic.build_is_enabled_cmd("docker")],
        juge=_juger_docker_enabled,
        geste_id="activer_docker_boot",
    ),
    Regle(
        regle_id="stacks_au_boot",
        domaine=DOMAINE_REDEMARRAGE,
        libelle="Les stacks déclarées sont-elles toutes lancées ?",
        pourquoi=(
            "Compare les dossiers de compose présents sur le disque aux projets que "
            "Docker considère comme actifs. L'écart entre les deux, ce sont les "
            "stacks qui existent mais ne tournent pas. Une stack tombée lors d'un "
            "redémarrage, ou jamais relancée après une mise à jour interrompue, "
            "passe inaperçue pendant des mois : rien ne la réclame, aucune alerte "
            "n'existe pour un service qu'on n'utilise qu'occasionnellement. On s'en "
            "aperçoit le jour où l'on en a besoin, ce qui est exactement le mauvais "
            "moment."
        ),
        commandes=lambda c: [
            diagnostic.build_compose_ls_cmd(),
            f"find {JETON_STACKS} -maxdepth 2 -name 'compose.y*ml'",
        ],
        juge=_juger_stacks_au_boot,
    ),
    # ------------------------------------------------ hygiène du disque
    Regle(
        regle_id="log_rotation",
        domaine=DOMAINE_DISQUE,
        libelle="Rotation des logs Docker",
        pourquoi=(
            "Sans `log-opts` dans `/etc/docker/daemon.json`, chaque conteneur écrit "
            "un fichier `-json.log` qui grossit sans AUCUNE limite. Un conteneur "
            "bavard — un reverse proxy qui journalise chaque requête, une "
            "application en mode debug oubliée — suffit à remplir un disque en "
            "quelques mois, sans que rien ne prévienne. C'est la cause numéro un du "
            "« / » qui se remplit tout seul sur un serveur où personne n'a rien "
            "changé. Trois lignes de configuration règlent le problème "
            "définitivement, pour tous les conteneurs à la fois."
        ),
        commandes=lambda _c: [diagnostic.build_daemon_json_cmd()],
        juge=_juger_log_rotation,
        geste_id="ecrire_daemon_json",
    ),
    Regle(
        regle_id="logs_volumineux",
        domaine=DOMAINE_DISQUE,
        libelle="Fichiers de log de conteneurs volumineux",
        pourquoi=(
            "Mesure ce que les `-json.log` occupent réellement, du plus gros au plus "
            "petit. C'est le constat immédiat qui accompagne la règle précédente : "
            "la rotation dit si le problème peut se reproduire, cette règle-ci dit "
            "s'il a déjà eu lieu. Le chemin de chaque fichier contient "
            "l'identifiant du conteneur, ce qui permet de savoir lequel est bavard. "
            "La correction se fait avec `truncate` et jamais avec `rm` : le fichier "
            "doit rester en place, Docker écrit dedans et ne le recréera pas."
        ),
        commandes=lambda _c: [diagnostic.build_du_logs_docker_cmd()],
        juge=_juger_logs_volumineux,
        geste_id="vider_log_conteneur",
    ),
    Regle(
        regle_id="croissance_disque",
        domaine=DOMAINE_DISQUE,
        libelle="Tendance d'occupation du disque",
        pourquoi=(
            "Compare l'occupation actuelle à celle relevée au précédent audit, "
            "mémorisée localement pour ce serveur. Un pourcentage instantané ne dit "
            "rien : 70 % peut être une situation stable depuis deux ans ou l'avant-"
            "veille d'une panne. Ce qui informe, c'est la pente — « +4 points depuis "
            "le 12/07 » permet d'agir des semaines avant que le disque ne soit "
            "plein, au moment où l'on a encore le choix de ce qu'on supprime. C'est "
            "la seule règle de cette page qui ne peut rien dire la première fois "
            "qu'on la lance."
        ),
        commandes=lambda _c: [diagnostic.build_df_cmd()],
        juge=_juger_croissance_disque,
    ),
    Regle(
        regle_id="journal_systemd",
        domaine=DOMAINE_DISQUE,
        libelle="Taille du journal systemd",
        pourquoi=(
            "Le même piège que les logs Docker, en beaucoup moins connu : le journal "
            "de systemd conserve tout ce que le système et les services écrivent, et "
            "en l'absence de `SystemMaxUse=` dans `/etc/systemd/journald.conf`, il "
            "s'autorise jusqu'à 10 % du système de fichiers. Sur un disque de 500 Go, "
            "cela fait 50 Go de journaux que personne ne lira jamais. Une seule ligne "
            "de configuration borne l'affaire définitivement, et les journaux "
            "récents — les seuls qui servent — restent accessibles."
        ),
        commandes=lambda _c: [
            diagnostic.build_journal_usage_cmd(),
            "cat /etc/systemd/journald.conf",
        ],
        juge=_juger_journal_systemd,
    ),
    # ------------------------------------------ certificats et exposition
    Regle(
        regle_id="certificats",
        domaine=DOMAINE_EXPOSITION,
        libelle="Expiration des certificats TLS",
        pourquoi=(
            "NGINX Proxy Manager (NPM) renouvelle les certificats Let's Encrypt tout "
            "seul, et cela marche très bien — jusqu'au jour où le renouvellement "
            "échoue silencieusement. Pour délivrer un certificat, Let's Encrypt doit "
            "d'abord vérifier que vous possédez bien le domaine : il contacte votre "
            "serveur sur le port 80 au moment du renouvellement. Si ce port a été "
            "refermé entre-temps (un changement de règle pare-feu), si le DNS du "
            "domaine ne pointe plus vers votre IP, ou si le quota hebdomadaire de "
            "renouvellements est atteint, l'opération échoue — et rien ne prévient. "
            "On l'apprend par un navigateur qui affiche un avertissement de sécurité "
            "en pleine page, et par des applications mobiles qui refusent de se "
            "connecter sans rien expliquer. Un certificat se renouvelle 30 jours "
            "avant son terme : en deçà de trois semaines, quelque chose a déjà "
            "échoué au moins une fois."
        ),
        commandes=_commandes_certificats,
        juge=_juger_certificats,
    ),
    Regle(
        regle_id="ports_exposes",
        domaine=DOMAINE_EXPOSITION,
        libelle="Ports ouverts et services derrière",
        pourquoi=(
            "Deux vérifications distinctes, l'une sur le pare-feu, l'autre sur "
            "Docker.\n\n"
            "La première regarde les portes ouvertes qui ne servent plus. Vous "
            "installez une application, vous ouvrez son port dans le pare-feu "
            "(UFW) pour qu'elle soit joignable. Plus tard, vous la supprimez ou "
            "la déplacez — la règle UFW, elle, reste. Rien ne l'utilise "
            "aujourd'hui, donc rien ne se voit. Le jour où une nouvelle "
            "application prend ce même port, elle hérite d'une porte déjà "
            "grande ouverte, sans que vous vous en souveniez.\n\n"
            "La seconde regarde COMMENT un service publie son port. Dans un "
            "`compose.yaml`, deux écritures très proches ont un effet très "
            "différent : `\"8080:8080\"` rend le service joignable depuis "
            "n'importe où — Internet compris, si le pare-feu laisse passer ce "
            "port. C'est ce que Docker appelle publier sur `0.0.0.0`, "
            "c'est-à-dire sur toutes les interfaces réseau de la machine. "
            "`\"127.0.0.1:8080:8080\"` réserve le service à la machine "
            "elle-même : seul un logiciel qui tourne dessus peut l'atteindre. "
            "C'est justement le rôle de NGINX Proxy Manager (NPM) : il reçoit "
            "les visiteurs en HTTPS sur le port 443, puis les redirige en "
            "interne vers l'application. Si l'application est AUSSI publiée en "
            "`0.0.0.0`, n'importe qui peut la joindre directement en "
            "contournant NPM — donc sans le chiffrement HTTPS qu'il assure, et "
            "sans que ses journaux d'accès n'en gardent la moindre trace."
        ),
        commandes=lambda _c: [
            "docker ps --format '{{.Ports}}'",
            "sudo ufw status numbered",
        ],
        juge=_juger_ports_exposes,
    ),
    Regle(
        regle_id="ssh_durci",
        domaine=DOMAINE_EXPOSITION,
        libelle="Points clés de la configuration SSH",
        pourquoi=(
            "Relit deux réglages qui comptent vraiment, et un troisième affiché "
            "pour information. `PermitRootLogin` et `PasswordAuthentication` "
            "d'abord : un serveur qui accepte une connexion par mot de passe se "
            "fait essayer des milliers de combinaisons par jour par des robots ; "
            "avec `PermitRootLogin yes`, l'une de ces tentatives finit "
            "statistiquement par aboutir, et elle donne alors tous les droits. "
            "`Port` est montré à titre indicatif seulement — changer le port SSH "
            "ne bloque personne de déterminé, ça réduit juste le bruit des robots "
            "qui scannent le port 22 par défaut, donc la règle ne le juge pas. "
            "Cette règle est en LECTURE SEULE et n'a aucun geste, volontairement : "
            "modifier `sshd_config` depuis l'application est le meilleur moyen de "
            "perdre l'accès au serveur. Le parcours « Base saine » le fait dans le "
            "bon ordre, avec ses gardes anti-verrouillage."
        ),
        commandes=lambda _c: [
            "grep -E -h -i "
            "'^[[:space:]]*(PermitRootLogin|PasswordAuthentication|Port)[[:space:]]' "
            "/etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf"
        ],
        juge=_juger_ssh_durci,
    ),
    # ---------------------------------------- sauvegardes et mises à jour
    Regle(
        regle_id="sauvegardes_recentes",
        domaine=DOMAINE_SAUVEGARDES,
        libelle="Chaque source a-t-elle une sauvegarde récente ?",
        pourquoi=(
            "Reprend les sources déclarées dans la page « Sauvegardes » et cherche, "
            "pour chacune, l'archive la plus récente présente sur le serveur. La page "
            "Santé affiche déjà l'ancienneté GLOBALE des sauvegardes — mais un chip "
            "vert ne dit rien de la source qui, elle, n'est plus sauvegardée depuis "
            "trois mois parce que son conteneur a été renommé et que le script échoue en "
            "silence. C'est toujours UNE source qui est oubliée, jamais toutes : "
            "seul le détail par source le montre, et c'est exactement celle qu'on "
            "voudra restaurer."
        ),
        commandes=_commandes_sauvegardes,
        juge=_juger_sauvegardes_recentes,
    ),
    Regle(
        regle_id="restauration_testee",
        domaine=DOMAINE_SAUVEGARDES,
        libelle="Date du dernier test de restauration",
        pourquoi=(
            "Une sauvegarde jamais testée n'est qu'une intention. Rien ne prouve "
            "qu'elle se relit, qu'elle contient ce qu'on croit, ni que la procédure "
            "de restauration fonctionne encore — les versions d'images changent, les "
            "formats de dump évoluent, un volume oublié dans le périmètre ne se "
            "remarque qu'au moment où il manque. La page Restauration sait faire ce "
            "test dans un environnement jetable, sans toucher au service en "
            "production. Au-delà de six mois, la question se repose."
        ),
        commandes=_aucune,
        juge=_juger_restauration_testee,
    ),
    Regle(
        regle_id="images_a_jour",
        domaine=DOMAINE_SAUVEGARDES,
        libelle="Images avec une mise à jour disponible",
        pourquoi=(
            "Compte les images dont l'empreinte publiée sur le registre diffère de "
            "celle installée localement, en réutilisant exactement la détection de "
            "la page « Mises à jour » plutôt qu'une seconde implémentation qui "
            "divergerait au premier changement. Une image en retard n'est pas une "
            "panne et ne demande aucune urgence — mais c'est là que vivent les "
            "correctifs de sécurité, et un serveur exposé sur Internet qui n'a pas "
            "été mis à jour depuis un an accumule des failles connues et "
            "publiquement documentées."
        ),
        commandes=_aucune,
        juge=_juger_images_a_jour,
    ),
)


# ============================================================================
#                                  GESTES
# ============================================================================
# Trois seulement, et c'est voulu : les autres règles se corrigent dans un
# fichier que l'utilisateur maintient (compose, sshd_config), et les écrire à
# sa place serait une écriture silencieuse. L'application AFFICHE alors la
# ligne exacte à ajouter.
#
# `ecrire_daemon_json` reprend le motif d'écriture distante sûre de
# `core/fail2ban.py` — sauvegarde `.bak`, écriture d'un `.tmp`, validation par
# `python3 -m json.tool`, `mv` atomique, restauration de la sauvegarde si le
# fichier produit est invalide. Ne pas en inventer un autre.
#
# ÉCRIRE DANS /etc/docker DEMANDE LES DROITS ROOT, donc `sudo`, et cela dicte
# toute la forme du script :
#
#   * la commande commence par `sudo` pour que `ui.helpers.preparer_sudo` la
#     reconnaisse et fabrique le couple `sudo -S -p '' …` + mot de passe sur
#     l'entrée standard (CLAUDE.md : un seul endroit sait faire ça) ;
#   * l'entrée standard est donc PRISE par le mot de passe : le programme
#     python ne peut plus arriver par un heredoc, il passe en argument de
#     `python3 -c`. Une version antérieure utilisait `python3 - <<EOF`, ce qui
#     rendait sudo impossible — et échouait par `PermissionError` dès que
#     l'utilisateur SSH n'était pas root ;
#   * un seul `sudo` dans toute la commande : `preparer_sudo` ne réécrit que le
#     premier, et les suivants réclameraient un terminal qui n'existe pas. D'où
#     le `sudo sh -c '<script entier>'` plutôt qu'un `sudo` par ligne.
_PROGRAMME_DAEMON_JSON = """import json, os, sys
source, cible = sys.argv[1], sys.argv[2]
donnees = {}
if os.path.exists(source):
    with open(source, encoding="utf-8") as fh:
        contenu = fh.read().strip()
    if contenu:
        try:
            donnees = json.loads(contenu)
        except ValueError as erreur:
            raise SystemExit(
                "ERREUR|Le fichier daemon.json actuel n'est pas du JSON valide "
                "(%s). Rien n'a ete modifie : corrigez-le d'abord." % erreur
            )
if not isinstance(donnees, dict):
    raise SystemExit(
        "ERREUR|daemon.json ne contient pas un objet JSON. Rien n'a ete modifie."
    )
options = donnees.get("log-opts")
if not isinstance(options, dict):
    options = {}
options.setdefault("max-size", "10m")
options.setdefault("max-file", "3")
donnees["log-opts"] = options
donnees.setdefault("log-driver", "json-file")
try:
    with open(cible, "w", encoding="utf-8") as fh:
        json.dump(donnees, fh, indent=2)
        fh.write("\\n")
except OSError as erreur:
    raise SystemExit(
        "ERREUR|Ecriture impossible dans /etc/docker (%s). Il faut les droits "
        "root : verifiez que votre compte peut utiliser sudo." % erreur
    )
"""

_CORPS_DAEMON_JSON = (
    "set -e\n"
    "F=/etc/docker/daemon.json\n"
    'B="$F.bak-$(date +%Y%m%d-%H%M%S)"\n'
    'T="$F.tmp-$$"\n'
    'if test -f "$F"; then cp -p "$F" "$B"; echo "SAUVEGARDE|$B";'
    ' else echo "ABSENT|$F"; fi\n'
    f"python3 -c {shlex.quote(_PROGRAMME_DAEMON_JSON)} \"$F\" \"$T\"\n"
    'python3 -m json.tool "$T" > /dev/null\n'
    'chmod 644 "$T"\n'
    'mv "$T" "$F"\n'
    'echo "ECRIT|$F"\n'
)

_SCRIPT_DAEMON_JSON = "sudo sh -c " + shlex.quote(_CORPS_DAEMON_JSON)

GESTES: tuple[Geste, ...] = (
    Geste(
        geste_id="activer_docker_boot",
        libelle="Activer Docker au démarrage",
        commande="sudo systemctl enable docker",
        explication=(
            "Demande à systemd de lancer le démon Docker à chaque démarrage de la "
            "machine. Le geste est immédiat et sans effet sur les conteneurs en "
            "cours : rien n'est arrêté, rien n'est redémarré. Ce que ça NE répare "
            "PAS : les conteneurs dont la politique de redémarrage vaut « no » ne "
            "reviendront toujours pas — Docker démarrera, eux non. Traitez aussi la "
            "règle « politique de redémarrage » pour que le serveur revienne "
            "vraiment complet après une coupure."
        ),
    ),
    Geste(
        geste_id="ecrire_daemon_json",
        libelle="Configurer la rotation des logs Docker",
        commande=_SCRIPT_DAEMON_JSON,
        explication=(
            "Écrit `log-opts` (max-size 10m, max-file 3) dans "
            "`/etc/docker/daemon.json` en CONSERVANT les clés déjà présentes : "
            "sauvegarde horodatée, fichier temporaire, validation JSON, puis "
            "déplacement atomique. Si le résultat est invalide, rien n'est "
            "remplacé.\n\n"
            "DEUX AVERTISSEMENTS, dans cet ordre. La rotation ne s'appliquera "
            "qu'aux conteneurs RECRÉÉS après coup — les fichiers actuels ne "
            "rétrécissent pas tout seuls (voir « fichiers de log volumineux »). Et "
            "la configuration ne prend effet qu'au redémarrage du démon Docker, qui "
            "COUPE tous les conteneurs : ceux dont la politique de redémarrage "
            "n'est pas « always » ou « unless-stopped » resteront à terre. Corrigez "
            "donc la règle « politique de redémarrage » AVANT de redémarrer le "
            "démon. Ce que ça NE répare PAS : la place déjà consommée."
        ),
    ),
    Geste(
        geste_id="vider_log_conteneur",
        libelle="Vider un fichier de log",
        # `sudo` : les `-json.log` vivent sous /var/lib/docker, lisible et
        # inscriptible par root seul. Appartenir au groupe docker ne suffit pas.
        commande="sudo truncate -s 0 __CHEMIN_LOG__",
        explication=(
            "Remet à zéro le fichier `-json.log` choisi sans le supprimer — Docker "
            "continue d'écrire dedans, ce qu'une suppression casserait. La place est "
            "libérée immédiatement, sans redémarrer le conteneur ni interrompre le "
            "service. Ce que ça NE répare PAS : le fichier repoussera exactement "
            "pareil tant que la rotation n'est pas configurée (règle « rotation des "
            "logs Docker »). Vous perdez l'historique des logs de ce conteneur — "
            "vérifiez d'abord que vous n'y cherchiez rien."
        ),
    ),
)

# Jeton du geste `vider_log_conteneur` : le chemin est choisi dans la liste des
# fichiers volumineux remontés par la règle, jamais saisi à la main.
JETON_CHEMIN_LOG = "__CHEMIN_LOG__"


# ============================================================================
#                                  ACCÈS
# ============================================================================
def regle(regle_id: str) -> Regle | None:
    """La règle d'identifiant donné, ou None."""
    for item in REGLES:
        if item.regle_id == regle_id:
            return item
    return None


def geste(geste_id: str) -> Geste | None:
    """Le geste d'identifiant donné, ou None."""
    for item in GESTES:
        if item.geste_id == geste_id:
            return item
    return None


def regles_du_domaine(domaine: str) -> list[Regle]:
    """Les règles d'un domaine, dans l'ordre de déclaration."""
    return [r for r in REGLES if r.domaine == domaine]


def domaines_presents() -> list[str]:
    """Domaines réellement portés par des règles, dans l'ordre d'affichage."""
    return [d for d in DOMAINES if regles_du_domaine(d)]


def contexte(config=None, *, domaines=None, sources=None, maintenant=None,
             occupation_precedente=None, date_occupation_lisible="",
             dernier_test_restauration=None, maj_disponibles=None) -> dict:
    """Table passée aux constructeurs de commandes et aux juges.

    Rassemble en un seul endroit tout ce que les règles lisent hors du serveur :
    données locales du profil (domaines, occupation précédente), registre des
    sources (brique 17), historique (brique 24) et détection des mises à jour
    (brique 05). Les règles n'accèdent jamais à un fichier elles-mêmes.
    """
    backup_dir = "/srv/backups"
    stacks_dir = "/opt/stacks"
    warn = 7
    if config is not None:
        lire = getattr(config, "get", None)
        if callable(lire):
            backup_dir = str(config.get("backup_dir") or backup_dir)
            stacks_dir = str(config.get("stacks_dir") or stacks_dir)
            try:
                warn = int(config.get("backup_warn_days") or warn)
            except (TypeError, ValueError):
                warn = 7
    return {
        "config": config,
        "backup_dir": backup_dir,
        "stacks_dir": stacks_dir,
        "backup_warn_days": warn,
        "domaines": list(domaines or []),
        "sources": list(sources or []),
        "maintenant": maintenant or datetime.now(),
        "occupation_precedente": dict(occupation_precedente or {}),
        "date_occupation_lisible": date_occupation_lisible,
        "dernier_test_restauration": dernier_test_restauration,
        "maj_disponibles": maj_disponibles,
    }


def jetons(contexte_: dict) -> dict[str, str]:
    """Substitution des jetons de chemin dans les commandes des règles."""
    return {
        JETON_STACKS: contexte_.get("stacks_dir") or "/opt/stacks",
        JETON_BACKUP: contexte_.get("backup_dir") or "/srv/backups",
    }
