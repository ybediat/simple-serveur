"""postgres_fiches.py — le contenu de la page Postgres, en donnée.

À la racine, comme `parcours/*.py` : ce fichier est **contribuable sans toucher
au moteur**. Deux choses y vivent, et rien d'autre :

* les **fiches** — le pourquoi de chaque geste, en markdown, ton « débutant qui
  veut comprendre » ;
* le **catalogue de requêtes** — le seul SQL que l'appli sache exécuter.

Règle de la brique 21 : si l'appli permet un geste, son but premier est de
l'EXPLIQUER. Une requête d'écriture sans fiche est un bug, et c'est testé.

Le SQL d'ici n'est jamais concaténé avec une saisie utilisateur : les rares
trous (`{ident}`, `{pid}`) sont remplis par `core.postgres_admin`, qui valide
puis cite. Le SQL des trois écritures du volet « Créer » n'est pas ici : il est
fabriqué par `sql_creer_base` / `sql_creer_role` / `sql_donner_droits`, parce
qu'il porte des noms et un mot de passe à échapper.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Fiche:
    """Un texte d'explication, rattaché à un ou plusieurs gestes."""

    fiche_id: str
    titre: str
    texte: str  # markdown : le POURQUOI d'abord, puis quand/comment, puis les pièges


@dataclass(frozen=True)
class Requete:
    """Une entrée du catalogue : le seul SQL que la page sache lancer."""

    requete_id: str
    libelle: str  # texte du bouton
    sql: str  # gabarit ; les trous sont des {ident} / {pid} nommés
    colonnes: tuple[str, ...] = ()
    fiche_id: str = ""
    ecriture: bool = False  # → confirm_action obligatoire
    # True : la requête se lance AVEC `-d <base sélectionnée>` plutôt que sur
    # `postgres`. C'est le cas de tout ce qui regarde l'intérieur d'une base
    # (schémas, tables, extensions) — une base est un univers isolé, on ne peut
    # pas lire ses tables depuis une autre.
    sur_base_selectionnee: bool = False


# ============================================================================
#                                  FICHES
# ============================================================================

_FICHES: tuple[Fiche, ...] = (
    Fiche(
        "base_vs_schema",
        "Une base n'est pas un schéma",
        """
**Une base de données est un univers isolé.** On s'y connecte, et une fois
dedans on ne voit qu'elle : il n'existe pas de jointure entre deux bases du même
serveur. C'est pour ça que la règle est **une base par application** — si
Nextcloud et listmonk partagent une base, ils partagent aussi leurs ennuis, et
restaurer l'un oblige à restaurer l'autre.

**Un schéma est un tiroir DANS une base.** Toute base en a au moins un, nommé
`public`, où atterrissent les tables quand on ne précise rien. Les schémas
servent à deux choses : ranger (les tables de facturation d'un côté, celles du
catalogue de l'autre) et donner des droits par groupe de tables plutôt que table
par table.

En pratique : multiplier les **bases** sépare des applications, multiplier les
**schémas** organise une même application. Une appli auto-hébergée classique
n'a besoin que du schéma `public`.
""".strip(),
    ),
    Fiche(
        "roles_moindre_privilege",
        "Pourquoi un rôle qui ne peut pas tout faire",
        """
Le rôle `postgres` est **superutilisateur** : il peut lire, modifier et
supprimer n'importe quoi sur tout le serveur, y compris les bases des autres
applications. Une appli qui s'y connecte transforme la moindre faille — une
injection SQL, un script de migration mal écrit, une fausse manœuvre — en
incident qui déborde très au-delà d'elle.

**Un rôle propriétaire de sa seule base limite le rayon d'explosion.** Si
l'appli est compromise, ce qui est perdu est ce qu'elle gérait déjà. C'est aussi
ce qui rend les sauvegardes lisibles : on sait à qui appartient quoi, et une
restauration ne redistribue pas les droits au hasard.

Trois attributs à connaître :

- `LOGIN` — le rôle peut se connecter. Sans lui, c'est un simple groupe de droits.
- `CREATEDB` — il peut créer ses propres bases. Utile à un outil de migration,
  inutile à une appli en fonctionnement.
- `SUPERUSER` — tous les droits, partout, contrôles désactivés. **L'appli ne
  propose pas de le donner** : le besoin réel est rarissime, et il se fait alors
  en connaissance de cause depuis la Console.
""".strip(),
    ),
    Fiche(
        "vacuum",
        "VACUUM, ANALYZE, et les lignes mortes",
        """
PostgreSQL ne modifie jamais une ligne sur place. Un `UPDATE` écrit une nouvelle
version et laisse l'ancienne ; un `DELETE` marque la ligne comme partie sans
libérer sa place. C'est ce qui permet à plusieurs transactions de lire en même
temps sans se bloquer — et c'est ce qui laisse derrière lui des **lignes
mortes** (`n_dead_tup`).

- `VACUUM` recycle cette place pour les écritures suivantes. Il ne rend pas
  l'espace au disque, il le rend réutilisable par la table.
- `ANALYZE` met à jour les statistiques dont le planificateur se sert pour
  choisir ses plans. Des statistiques périmées donnent des requêtes lentes sans
  qu'aucune erreur n'apparaisse.

**L'autovacuum fait déjà ce travail en continu.** Un VACUUM manuel est un geste
de dépannage — après une purge massive, ou quand `n_dead_tup` explose sur une
table précise — pas une routine à programmer. Si vous en avez besoin
régulièrement, c'est l'autovacuum qu'il faut régler, pas le bouton qu'il faut
cliquer plus souvent.
""".strip(),
    ),
    Fiche(
        "vacuum_full",
        "Pourquoi VACUUM FULL n'est pas proposé ici",
        """
`VACUUM FULL` réécrit la table entière pour rendre l'espace au système de
fichiers. C'est le seul qui fasse vraiment maigrir le disque — et il coûte trois
choses :

- un verrou **ACCESS EXCLUSIVE** : plus personne ne lit ni n'écrit la table
  pendant l'opération. En clair, l'application est à l'arrêt ;
- **le double de l'espace disque** de la table le temps de la copie. Sur un
  disque déjà plein, c'est exactement le geste qui achève le serveur ;
- une durée imprévisible, proportionnelle à la taille.

Ce n'est pas un geste interdit, c'est un geste qui se décide : on choisit son
heure, on vérifie la place libre, on prévient les utilisateurs. Rien de tout ça
ne tient derrière un bouton. Il reste accessible depuis la page **Console**, où
l'on tape ce qu'on fait.
""".strip(),
    ),
    Fiche(
        "connexions",
        "Connexions, et la session qui ne se termine jamais",
        """
`max_connections` fixe le nombre de connexions simultanées que le serveur
accepte (souvent 100). Chacune coûte de la mémoire : monter ce chiffre n'est pas
la bonne réponse à « trop de connexions », un pooler comme PgBouncer l'est.

L'état d'une session se lit dans la colonne **état** :

- `active` — elle exécute quelque chose maintenant ;
- `idle` — connectée sans rien faire, c'est normal (les applis gardent un pool) ;
- **`idle in transaction`** — elle a ouvert une transaction et l'a laissée
  ouverte. C'est le symptôme n°1 d'un bug applicatif : un `BEGIN` sans `COMMIT`,
  ou un code qui plante entre les deux.

Pourquoi c'est grave : tant que cette transaction vit, elle garde ses verrous
**et** empêche le VACUUM de recycler les lignes mortes du serveur entier. Une
seule session oubliée peut faire grossir des tables qui n'ont rien à voir avec
elle. Au-delà de quelques minutes, la page la signale.
""".strip(),
    ),
    Fiche(
        "taille_bases",
        "Ce que mesure la taille d'une base",
        """
La taille affichée est **l'espace occupé sur le disque**, pas le volume de
données utiles. S'y ajoutent :

- les **index**, qui pèsent souvent autant que les tables ;
- les **lignes mortes** pas encore recyclées (voir la fiche VACUUM) ;
- l'espace réservé que PostgreSQL garde pour les écritures à venir.

Une base qui pèse 400 Mo pour 150 Mo de données n'a rien d'anormal. Ce qui est
intéressant, ce n'est pas le chiffre à un instant donné, c'est sa **tendance** :
une base qui double en un mois raconte quelque chose, une base qui pèse 400 Mo
ne raconte rien.

À noter : les journaux de transaction (WAL) ne sont comptés dans aucune base.
Ils vivent à part et peuvent occuper plusieurs gigaoctets à eux seuls.
""".strip(),
    ),
    Fiche(
        "cache_hit",
        "Le ratio de cache",
        """
PostgreSQL garde en mémoire les blocs de données lus récemment. Le ratio mesure
la part des lectures servies depuis cette mémoire plutôt que depuis le disque.

Un ratio **bas** (disons sous 90 %) sur un serveur qui travaille signifie
généralement que la mémoire allouée (`shared_buffers`) est trop petite pour le
volume manipulé : le serveur passe son temps à relire le disque.

Mais **99 % sur un serveur inactif ne prouve rien** : s'il n'y a eu que trois
requêtes depuis le démarrage, et qu'elles portaient sur la même petite table,
le ratio est parfait et ne dit rien de la charge réelle. C'est un indicateur à
lire sur un serveur qui tourne depuis longtemps et qui sert vraiment.
""".strip(),
    ),
    Fiche(
        "extensions",
        "Les extensions",
        """
Une extension ajoute des fonctions, des types ou des vues à PostgreSQL. Les plus
courantes sur un serveur domestique :

- `pg_stat_statements` — mémorise les requêtes exécutées et leur temps cumulé.
  C'est l'outil qui répond à « pourquoi c'est lent ? » ;
- `pgcrypto` — fonctions de chiffrement et de hachage, réclamée par certaines
  applications ;
- `unaccent`, `pg_trgm` — recherche textuelle tolérante aux accents et aux fautes.

Point qui surprend : **une extension s'installe base par base**. L'avoir activée
dans `metier` ne la rend pas disponible dans `nextcloud`. C'est cohérent avec
l'isolation des bases, mais ça explique bien des « pourtant je l'ai installée ».

Certaines demandent aussi d'être chargées au démarrage du serveur
(`shared_preload_libraries`), donc un redémarrage : c'est le cas de
`pg_stat_statements`.
""".strip(),
    ),
    Fiche(
        "entretien_duree",
        "Combien de temps ça prend, et ce que ça bloque",
        """
Les trois gestes d'entretien de cette page sont sûrs, mais pas gratuits :

- `ANALYZE` — rapide (quelques secondes), ne bloque rien. C'est le geste à faire
  après un import massif, quand les requêtes deviennent lentes sans raison.
- `VACUUM (ANALYZE)` — plus long, proportionnel au volume de lignes mortes. Ne
  bloque ni les lectures ni les écritures, mais consomme du disque et du
  processeur : à éviter en pleine heure de pointe.
- `REINDEX DATABASE` — reconstruit tous les index de la base. **Il verrouille
  chaque index le temps de le refaire** : l'application ralentit franchement, et
  certaines requêtes attendent. Il faut aussi de la place pour l'index en cours
  de reconstruction. À réserver aux cas où un index est corrompu ou très
  fragmenté.

Dans tous les cas, la durée réelle s'affiche à la fin — c'est la seule mesure
qui vaille pour décider si on recommencera un jour en pleine journée.
""".strip(),
    ),
    Fiche(
        "pourquoi_pas_ici",
        "Pour aller plus loin",
        """
Cette page couvre le quotidien : **regarder, comprendre, entretenir, créer le
strict nécessaire**. Elle s'arrête volontairement là, et n'a ni console SQL, ni
suppression, ni modification de données.

Pour de la vraie administration, il existe des outils faits pour ça :

- **pgAdmin** — interface web complète, l'outil de référence côté PostgreSQL ;
- **DBeaver** — client de bureau, multi-SGBD, très pratique pour explorer ;
- **psql** — la ligne de commande officielle, déjà accessible depuis la page
  **Console** de cette appli : c'est là qu'on tape du SQL libre ;
- **pg_stat_statements** et **pgHero** — pour chercher les requêtes lentes.

Un parcours d'installation dédié posera ces outils proprement, avec la même
logique que les autres parcours (étapes idempotentes, explication avant chaque
commande). Il n'existe pas encore : d'ici là, la Console fait le travail.
""".strip(),
    ),
)

FICHES: dict[str, Fiche] = {f.fiche_id: f for f in _FICHES}


def fiche(fiche_id: str) -> Fiche | None:
    """Retourne une fiche, ou None si l'identifiant est inconnu."""
    return FICHES.get(fiche_id)


def texte_fiche(fiche_id: str) -> str:
    """Markdown d'une fiche, chaîne vide si elle n'existe pas.

    Accès tolérant : une fiche manquante ne doit jamais empêcher un bouton de
    fonctionner, elle doit seulement laisser l'explication vide.
    """
    f = FICHES.get(fiche_id)
    return f.texte if f else ""


# ============================================================================
#                          CATALOGUE DE REQUÊTES
# ============================================================================
# Tout le SQL de lecture de la page est ici, en une ligne par requête pour que
# la commande affichée au journal reste lisible.
#
# Deux précautions systématiques, parce qu'un compte non superutilisateur est le
# cas nominal de la brique 11 :
#   * `has_database_privilege(..., 'CONNECT')` filtre les bases que le rôle ne
#     peut pas ouvrir — sans ce filtre, `pg_database_size` lève une erreur et,
#     avec ON_ERROR_STOP=1, c'est TOUTE la requête qui échoue ;
#   * `coalesce(...)` sur les colonnes qui peuvent être NULL (un processus
#     système n'a ni base ni requête), pour ne pas confondre « vide » et
#     « colonne absente » au découpage.

_SQL_APERCU = (
    "SELECT current_setting('server_version'), "
    "date_trunc('second', now() - pg_postmaster_start_time())::text, "
    "(SELECT pg_size_pretty(sum(pg_database_size(d.oid))) FROM pg_database d "
    "WHERE has_database_privilege(d.datname, 'CONNECT')), "
    "(SELECT count(*)::text FROM pg_stat_activity WHERE backend_type = 'client backend'), "
    "current_setting('max_connections'), "
    "(SELECT coalesce(round(100.0 * sum(blks_hit) / "
    "nullif(sum(blks_hit + blks_read), 0), 1)::text, '') FROM pg_stat_database)"
)

_SQL_BASES = (
    "SELECT d.datname, pg_get_userbyid(d.datdba), pg_encoding_to_char(d.encoding), "
    "pg_size_pretty(pg_database_size(d.oid)), "
    "(SELECT count(*) FROM pg_stat_activity a WHERE a.datid = d.oid)::text "
    "FROM pg_database d WHERE NOT d.datistemplate "
    "AND has_database_privilege(d.datname, 'CONNECT') "
    "ORDER BY pg_database_size(d.oid) DESC"
)

_SQL_SCHEMAS = (
    "SELECT n.nspname, pg_get_userbyid(n.nspowner), "
    "(SELECT count(*) FROM pg_class c WHERE c.relnamespace = n.oid "
    "AND c.relkind = 'r')::text "
    "FROM pg_namespace n WHERE n.nspname NOT LIKE 'pg\\_%' "
    "AND n.nspname <> 'information_schema' ORDER BY 1"
)

_SQL_TABLES = (
    "SELECT s.schemaname, s.relname, "
    "pg_size_pretty(pg_total_relation_size(s.relid)), "
    "s.n_live_tup::text, s.n_dead_tup::text "
    "FROM pg_stat_user_tables s "
    "ORDER BY pg_total_relation_size(s.relid) DESC LIMIT 15"
)

_SQL_EXTENSIONS = (
    "SELECT e.extname, e.extversion, n.nspname "
    "FROM pg_extension e JOIN pg_namespace n ON n.oid = e.extnamespace ORDER BY 1"
)

# `secondes` plutôt qu'une durée déjà mise en forme : le seuil des sessions
# `idle in transaction` se calcule côté appli, donc il se teste sans serveur.
_SQL_ACTIVITE = (
    "SELECT a.pid::text, coalesce(a.datname, ''), coalesce(a.usename, ''), "
    "coalesce(a.state, ''), "
    "coalesce(extract(epoch from (now() - a.state_change))::bigint, -1)::text, "
    "coalesce(a.backend_type, ''), "
    "left(regexp_replace(coalesce(a.query, ''), '\\s+', ' ', 'g'), 200) "
    # Tri sur l'expression de durée, PAS sur la colonne 5 : celle-ci est du
    # texte (tout sort en texte avec `-t -A`), et un tri lexical mettrait
    # « 96 » devant « 743 ». Les sessions sans `state_change` (processus
    # système) partent en fin de liste.
    "FROM pg_stat_activity a ORDER BY (now() - a.state_change) DESC NULLS LAST"
)

# Les rôles `pg_*` sont les rôles prédéfinis de PostgreSQL (pg_read_all_data…) :
# ce ne sont pas des comptes, les proposer comme propriétaire n'aurait aucun sens.
_SQL_ROLES = (
    "SELECT r.rolname, r.rolcanlogin::text, r.rolcreatedb::text, r.rolsuper::text "
    "FROM pg_roles r WHERE r.rolname NOT LIKE 'pg\\_%' ORDER BY 1"
)

_REQUETES: tuple[Requete, ...] = (
    Requete(
        "apercu",
        "Se connecter / actualiser",
        _SQL_APERCU,
        ("Version", "Démarré depuis", "Taille totale", "Connexions",
         "Maximum", "Ratio de cache"),
        fiche_id="cache_hit",
    ),
    Requete(
        "bases",
        "Lister les bases",
        _SQL_BASES,
        ("Base", "Propriétaire", "Encodage", "Taille", "Connexions"),
        fiche_id="taille_bases",
    ),
    Requete(
        "schemas",
        "Schémas",
        _SQL_SCHEMAS,
        ("Schéma", "Propriétaire", "Tables"),
        fiche_id="base_vs_schema",
        sur_base_selectionnee=True,
    ),
    Requete(
        "tables",
        "Plus grosses tables",
        _SQL_TABLES,
        ("Schéma", "Table", "Taille", "Lignes vivantes", "Lignes mortes"),
        fiche_id="vacuum",
        sur_base_selectionnee=True,
    ),
    Requete(
        "extensions",
        "Extensions installées",
        _SQL_EXTENSIONS,
        ("Extension", "Version", "Schéma"),
        fiche_id="extensions",
        sur_base_selectionnee=True,
    ),
    Requete(
        "roles",
        "Rôles",
        _SQL_ROLES,
        ("Rôle", "Peut se connecter", "Peut créer des bases", "Superutilisateur"),
        fiche_id="roles_moindre_privilege",
    ),
    Requete(
        "activite",
        "Activité",
        _SQL_ACTIVITE,
        ("PID", "Base", "Rôle", "État", "Secondes", "Type", "Requête"),
        fiche_id="connexions",
    ),
    Requete(
        "terminer_session",
        "Interrompre cette session",
        "SELECT pg_terminate_backend({pid})",
        ("Interrompue",),
        fiche_id="connexions",
        ecriture=True,
    ),
    Requete(
        "analyze",
        "ANALYZE",
        "ANALYZE",
        (),
        fiche_id="vacuum",
        ecriture=True,
        sur_base_selectionnee=True,
    ),
    Requete(
        "vacuum",
        "VACUUM (ANALYZE)",
        "VACUUM (ANALYZE)",
        (),
        fiche_id="vacuum",
        ecriture=True,
        sur_base_selectionnee=True,
    ),
    Requete(
        "reindex",
        "REINDEX DATABASE",
        "REINDEX DATABASE {ident}",
        (),
        fiche_id="entretien_duree",
        ecriture=True,
        sur_base_selectionnee=True,
    ),
)

REQUETES: dict[str, Requete] = {r.requete_id: r for r in _REQUETES}


def requete(requete_id: str) -> Requete | None:
    """Retourne une requête du catalogue, ou None si l'identifiant est inconnu."""
    return REQUETES.get(requete_id)


# Gestes volontairement absents, et la fiche qui explique chaque refus. Sert à
# l'encart « Ce que cette page ne fait pas » : un refus doit être visible et
# motivé, jamais une absence silencieuse.
REFUS: tuple[tuple[str, str, str], ...] = (
    ("DROP DATABASE / DROP ROLE",
     "L'appli ne supprime jamais de données — règle générale du projet.",
     ""),
    ("VACUUM FULL",
     "Verrou exclusif sur la table et le double de l'espace disque.",
     "vacuum_full"),
    ("SUPERUSER à la création d'un rôle",
     "Contraire au moindre privilège : le besoin est rare et se décide ailleurs.",
     "roles_moindre_privilege"),
    ("SQL libre",
     "Ce n'est pas le rôle de cette page : la Console est faite pour ça.",
     "pourquoi_pas_ici"),
    ("UPDATE / DELETE sur des données",
     "L'appli administre le contenant, jamais le contenu.",
     ""),
)
