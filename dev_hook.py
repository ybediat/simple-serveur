"""dev_hook.py — capture des erreurs de l'appli vers le journal de bord.

Intercepte les exceptions non gérées (thread principal + threads worker),
les exceptions « non retraçables » et les messages Qt critiques, puis les
pousse dans `core/journal.py` (dock « Journal ») en plus de stderr.

Outil de développement uniquement : appeler `installer()` une fois au
démarrage (voir `main.py`). Ne pas contourner le journal (voir CLAUDE.md).
"""
from __future__ import annotations

import sys
import traceback
import threading
from datetime import datetime
from typing import Optional

MODE_DEV = True


def _pousser(texte: str, *, erreur: bool = False) -> None:
    """Envoie une ligne au dock Journal (erreur → 'err', sinon 'info').

    L'émission passe par un signal Qt : sûre depuis n'importe quel thread.
    Silencieux si le bus n'est pas encore importable (démarrage très précoce).
    """
    try:
        from core.journal import journal
        (journal.err if erreur else journal.info)(texte)
    except Exception:
        pass


def log_erreur(
    erreur,
    contexte: Optional[str] = None,
    traceback_str: Optional[str] = None,
) -> None:
    """Trace une erreur (ligne résumé + traceback détaillé) dans le journal."""
    if not MODE_DEV:
        return

    horodatage = datetime.now().strftime("%H:%M:%S")

    if traceback_str:
        tb = traceback_str
    elif isinstance(erreur, BaseException):
        try:
            tb = "".join(
                traceback.format_exception(type(erreur), erreur, erreur.__traceback__)
            )
        except Exception:
            tb = "(traceback indisponible)\n"
    else:
        tb = "(aucun traceback)\n"

    resume = f"{contexte or 'Erreur'} : {type(erreur).__name__}: {erreur}"
    _pousser(f"[{horodatage}] ❌ {resume}", erreur=True)

    # Détail complet, une ligne par ligne (indenté, en 'info').
    for ligne in tb.splitlines():
        if ligne.strip():
            _pousser(f"    {ligne}")


def log_dev(message: str) -> None:
    """Message de développement libre dans le journal."""
    if not MODE_DEV:
        return
    _pousser(message)


def installer() -> None:
    """Installe les gestionnaires d'exceptions globaux + le handler Qt."""
    if not MODE_DEV:
        return

    def hook_exceptions(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        # Toujours écrire sur stderr d'abord : l'UI peut ne pas exister encore.
        print(f"[FATAL] {exc_type.__name__}: {exc_value}\n{tb}",
              file=sys.stderr, flush=True)
        log_erreur(exc_value, contexte="Exception non gérée", traceback_str=tb)

    sys.excepthook = hook_exceptions

    def hook_thread(args):
        if issubclass(args.exc_type, SystemExit):
            return
        tb = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
        print(f"[FATAL thread {args.thread.name}] {args.exc_type.__name__}: "
              f"{args.exc_value}\n{tb}", file=sys.stderr, flush=True)
        log_erreur(args.exc_value, contexte=f"Thread : {args.thread.name}",
                   traceback_str=tb)

    threading.excepthook = hook_thread

    def hook_non_retracable(unraisable):
        err = unraisable.exc_value or RuntimeError("Exception non retraçable")
        nom = getattr(unraisable.object, "__name__", repr(unraisable.object))
        tb = ""
        if unraisable.exc_traceback:
            tb = "".join(traceback.format_exception(
                unraisable.exc_type, unraisable.exc_value, unraisable.exc_traceback))
        log_erreur(err, contexte=f"Non retraçable : {nom}", traceback_str=tb)

    if hasattr(sys, "unraisablehook"):
        sys.unraisablehook = hook_non_retracable

    # Messages internes de Qt (warnings de layout, objets détruits, etc.).
    try:
        from PySide6.QtCore import qInstallMessageHandler

        def hook_qt(mode, contexte, message):
            val = mode.value if hasattr(mode, "value") else int(mode)
            libelles = {0: "DEBUG", 1: "WARNING", 2: "CRITICAL", 3: "FATAL", 4: "INFO"}
            libelle = libelles.get(val, "?")
            if val >= 2:  # CRITICAL / FATAL
                _pousser(f"[Qt-{libelle}] {message}", erreur=True)
            elif val == 1:  # WARNING
                _pousser(f"[Qt-{libelle}] {message}")
            # DEBUG/INFO ignorés pour ne pas noyer le journal.

        qInstallMessageHandler(hook_qt)
    except ImportError:
        pass
