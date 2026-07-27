"""main.py — point d'entrée de l'application Gestionnaire Serveur.

Options :
  --fake   : service SSH factice (fixtures) + connexion automatique. Permet de
             développer/démontrer l'appli sans serveur ni Docker.
  --smoke  : test de fumée — quitte tout seul après 3 s (code 0 si aucune
             exception n'a été levée au démarrage).
"""
from __future__ import annotations

import argparse
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit

from common_styles import get_complete_stylesheet
from core.config import Config
from core.fichiers_proteges import proteger_existants
from core.ssh import make_ssh_service
from core.vault import Vault
from ui.main_window import MainWindow

# Nombre d'essais de mot de passe maître avant fermeture (brique 08).
_UNLOCK_ATTEMPTS = 3


def _unlock_gate(vault) -> bool:
    """Portillon de déverrouillage au lancement. True si ouvert, False sinon."""
    for i in range(_UNLOCK_ATTEMPTS):
        restants = _UNLOCK_ATTEMPTS - i
        label = (
            "Mot de passe maître :"
            if i == 0
            else f"Mot de passe incorrect. Essais restants : {restants}."
        )
        pwd, ok = QInputDialog.getText(
            None, "Application verrouillée", label, QLineEdit.Password
        )
        if not ok:
            return False  # annulé → fermeture
        if vault.unlock(pwd):
            return True
    return False


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Gestionnaire de serveur Docker par SSH.")
    parser.add_argument("--fake", action="store_true",
                        help="Mode simulation : service SSH factice + connexion auto.")
    parser.add_argument("--smoke", action="store_true",
                        help="Test de fumée : quitte après 3 s (code 0 attendu).")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # Capture des erreurs vers le dock Journal (outil de dev). Installé tôt
    # pour attraper aussi les plantages du démarrage.
    from dev_hook import installer as _installer_hook_dev
    _installer_hook_dev()

    app = QApplication(sys.argv)
    app.setApplicationName("Gestionnaire Serveur")
    app.setStyleSheet(get_complete_stylesheet())

    config = Config()
    # Brique 18 : les fichiers locaux encore en clair (ancienne installation,
    # copie de migration, fichiers déposés depuis un autre PC) sont protégés dès
    # le lancement — silencieusement, la config est déjà chargée.
    proteger_existants()
    ssh = make_ssh_service(args.fake, config)
    vault = Vault(config)

    # Verrou maître : hors simulation, exiger le mot de passe AVANT la fenêtre.
    if vault.is_enabled() and not args.fake:
        if not _unlock_gate(vault):
            return 1  # 3 échecs ou annulation → l'appli se ferme

    window = MainWindow(ssh, config, fake=args.fake, vault=vault)
    window.show()

    if args.fake:
        # Connexion automatique en simulation (le service factice réussit toujours).
        ssh.connect_to(
            config.get("host"),
            config.get("port"),
            config.get("user"),
            config.get("key_path"),
        )

    # Messages sur les fichiers locaux (brique 18) puis, au premier lancement
    # (hôte non configuré), ouverture des Réglages. Les deux sont des modales :
    # ignorées en --smoke pour ne pas bloquer le test de fumée.
    if not args.smoke:
        QTimer.singleShot(0, window.verifier_fichiers_locaux)
        if not config.get("host"):
            QTimer.singleShot(0, window.open_first_run_settings)

    if args.smoke:
        QTimer.singleShot(3000, app.quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
