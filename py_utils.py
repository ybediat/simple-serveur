"""py_utils.py — stub local minimal.

Fournit uniquement `is_empty`, la seule fonction de l'utilitaire GUSH dont
`custom_widgets.py` a besoin. On garde la même sémantique que le projet d'origine
pour que les widgets réutilisés se comportent à l'identique.
"""
from __future__ import annotations

import math


def is_empty(value) -> bool:
    """True si la valeur est « vide » au sens large.

    Couvre : None, chaîne vide ou uniquement blanche, chaînes sentinelles
    ``'nan'`` / ``'none'`` (insensibles à la casse), float NaN, et toute
    collection (list/tuple/set/dict) sans élément.
    """
    if value is None:
        return True

    # Float NaN : NaN != NaN, et math.isnan lève sur les non-float.
    if isinstance(value, float):
        return math.isnan(value)

    if isinstance(value, str):
        cleaned = value.strip().lower()
        return cleaned in ("", "nan", "none")

    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0

    return False
