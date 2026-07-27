"""
Module centralisé pour la gestion des styles de l'application GUSH Master-30000
Tous les modules (sauf Nouvel_an) utilisent ces couleurs et styles pour une apparence cohérente
"""

# ============================================================================
#                           PALETTE DE COULEURS
# ============================================================================

import os
import sys


COLORS = {
    # Couleurs de fond
    'bg': '#f8fafc',              # Fond gris très clair (Slate 50)
    'card_bg': '#ffffff',          # Fond des cartes/panneaux
    'table_bg': "#ffffff",           # Fond des tables


    # Couleurs principales
    'primary': '#02506e',          # Bleu GUSH original
    'primary_hover': '#013a5a',    # Survol
    'primary_pressed': '#002a4a',  # Clic
    'primary_canard': '#0e7c86',   # Bleu canard — 2e état des sélecteurs 2 états (SegmentedSwitch)

    # Couleurs d'accentuation
    'accent': '#ffa41d',           # Orange GUSH original
    'accent_alt': '#8064a2',     #accent alternatif (violet)
    'accent_alt_hover': '#800080', # Violet sombre pour le survol

    # Texte
    'text_primary': '#0f172a',     # Slate 900 (très sombre mais pas noir)
    'text_secondary': '#64748b',   # Slate 500
    'text_light': '#94a3b8',       # Slate 400

    # États
    'success': '#9bbb59',          # Vert pastel (Green 400)
    'success_log': "#006826",      # Vert franc pour texte de log (meilleur contraste)
    'danger': '#c0504d',           # Rouge pastel
    'warning': '#f59e0b',          # Ambre
    'info': '#3b82f6',             # Sky blue

    # Bordures et séparateurs
    'border': '#e2e8f0',           # Bordures très subtiles (Slate 200)
    'border_light': '#f1f5f9',     # Slate 100
    'border_focus': "#ffa41d",     # Focus orange

    # Backgrounds alternatifs
    'bg_alt': "#f1f5f9",
    'bg_hover': "#eff5fc",
    'bg_selected': "#fffbf4",

    # Nuances héritées — valeurs exactes conservées lors de la centralisation (refactor #7).
    # Hors palette teal/orange : surlignage indigo des cartouches + slates neutres des
    # dialogues. Regroupées ici pour un point de réglage unique (et un futur mode sombre).
    'card_selected_bg':   '#eef2ff',   # DemandHeaderCard : fond carte sélectionnée (indigo clair)
    'card_hover_bg':      '#f0f4ff',   # DemandHeaderCard : fond au survol
    'card_text':          '#374151',   # Texte cartouches + labels de dialogue (slate-700)
    'panel_border':       '#cbd5e1',   # ComGushDialog : bordure du panneau d'édition (slate-300)
    'dialog_title':       '#1e3a8a',   # ComGushDialog : titre d'édition (bleu navy)
    'sister_bg':          '#f9fafb',   # ComGushDialog : fond carte sœur
    'sister_border':      '#d1d5db',   # ComGushDialog : bordure carte sœur (slate-300)
    'sister_title':       '#1f2937',   # ComGushDialog : titre carte sœur (slate-800)
    'sister_body_border': '#e5e7eb',   # ComGushDialog : bordure du corps lecture seule (slate-200)

    # Autres
    'disabled_bg': '#f1f5f9',
    'disabled_text': '#94a3b8',
}

# ============================================================================
#                           COULEURS DES STATUTS GUSH
# ============================================================================
STATUS_COLORS = {
    "commission": COLORS['text_light'],        # Gris
    "refus commission": "#000000",  # Noir
    "admissible": COLORS['primary'], # Bleu GUSH (#02506e)
    "admis": COLORS['success'],             # Vert
    "refus usager": COLORS['danger'],      # Rouge
    "refus structure": COLORS['danger'],   # Rouge
}


# ============================================================================
#                           STYLES RÉUTILISABLES
# ============================================================================

def get_main_window_style():
    """Style pour la fenêtre principale"""
    return f"""
        QMainWindow {{
            background-color: {COLORS['bg']};
        }}
    """


def get_card_frame_style():
    """Style pour les cartes/panneaux conteneurs"""
    return f"""
        QFrame {{
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
    """


def get_button_style():
    """Style standard pour les boutons (couleur primaire #02506e)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['primary']};
            color: #ffffff;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            font-weight: 500;
            letter-spacing: 0.1px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['primary_hover']};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['primary_pressed']};
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_secondary_button_style():
    """Style ghost pour les boutons secondaires"""
    return f"""
        QPushButton {{
            background-color: transparent;
            color: {COLORS['primary']};
            border: 1.5px solid {COLORS['border']};
            border-radius: 5px;
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            padding: 5px 14px;
        }}
        QPushButton:hover {{
            background-color: {COLORS['bg_hover']};
            border-color: {COLORS['primary']};
        }}
        QPushButton:pressed {{
            background-color: {COLORS['bg_selected']};
        }}
        QPushButton:disabled {{
            background-color: transparent;
            color: {COLORS['disabled_text']};
            border-color: {COLORS['border']};
        }}
    """


def get_success_button_style():
    """Style pour les boutons de succès (vert)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['success']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-weight: 500;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QPushButton:hover {{
            background-color: #059669;
        }}
        QPushButton:pressed {{
            background-color: #047857;
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_danger_button_style():
    """Style pour les boutons de danger (rouge)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['danger']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-weight: 500;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QPushButton:hover {{
            background-color: #b91c1c;
        }}
        QPushButton:pressed {{
            background-color: #991b1b;
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_warning_button_style():
    """Style pour les boutons d'avertissement (ambre)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['warning']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-weight: 500;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QPushButton:hover {{
            background-color: #d97706;
        }}
        QPushButton:pressed {{
            background-color: #b45309;
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_reload_button_style():
    """Style pour les boutons de rechargement (ardoise)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['text_secondary']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-weight: 500;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QPushButton:hover {{
            background-color: #475569;
        }}
        QPushButton:pressed {{
            background-color: #334155;
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_accent_alt_button_style():
    """Style pour les boutons accent alternatif (violet)"""
    return f"""
        QPushButton {{
            background-color: {COLORS['accent_alt']};
            color: white;
            border: none;
            border-radius: 5px;
            padding: 5px 14px;
            font-weight: 500;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QPushButton:hover {{
            background-color: {COLORS['accent_alt_hover']};
        }}
        QPushButton:pressed {{
            background-color: #5b21b6;
        }}
        QPushButton:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border: none;
        }}
    """


def get_title_style():
    """Style pour les titres principaux (couleur accent #ffa41d)"""
    return f"""
        font-size: 16px;
        font-weight: 600;
        color: {COLORS['accent']};
        padding: 4px 2px;
        font-family: 'Segoe UI Variable Display', 'Segoe UI Variable', 'Segoe UI', sans-serif;
        letter-spacing: -0.3px;
    """


def get_subtitle_style():
    """Style pour les sous-titres (couleur primaire #02506e)"""
    return f"""
        font-size: 13px;
        font-weight: 600;
        color: {COLORS['primary']};
        padding: 4px 2px;
        font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
        letter-spacing: 0.1px;
    """


def get_section_title_style():
    """Style pour les titres de section — uppercase discret"""
    return f"""
        font-size: 10px;
        font-weight: 600;
        color: {COLORS['text_light']};
        padding-bottom: 4px;
        letter-spacing: 0.8px;
    """


def get_input_style():
    """Style pour les champs de saisie (QLineEdit, QComboBox, etc.)"""
    return f"""
        QLineEdit, QComboBox, QDateEdit {{
            border: 1.5px solid {COLORS['border']};
            border-radius: 5px;
            padding: 5px 9px;
            background-color: white;
            color: {COLORS['text_primary']};
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            selection-background-color: #ffe9a8;
            selection-color: {COLORS['primary']};
        }}
        QLineEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
            border-color: {COLORS['border']};
        }}
        QLineEdit:focus {{
            border: 1.5px solid {COLORS['border_focus']};
            background-color: #fffdf9;
        }}
        QLineEdit:hover, QComboBox:hover, QDateEdit:hover {{
            border-color: #cbd5e1;
        }}
        QComboBox:focus, QDateEdit:focus {{
            border: 1.5px solid {COLORS['border_focus']};
        }}
        QComboBox QLineEdit {{
            background-color: {COLORS['card_bg']};
            color: {COLORS['text_primary']};
            border: none;
            padding: 1px 2px;
        }}
        QComboBox QAbstractItemView {{
            background-color: #ffffff;
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            outline: none;
            padding: 3px;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 6px 10px;
            border-radius: 4px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {COLORS['bg_hover']};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {COLORS['primary']};
            color: white;
        }}
    """


def get_text_edit_style():
    """Style pour les zones de texte (QTextEdit)"""
    return f"""
        QTextEdit {{
            background-color: #f9f9f9;
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            padding: 4px;
        }}
        QTextEdit:disabled {{
            background-color: {COLORS['disabled_bg']};
            color: {COLORS['disabled_text']};
        }}
    """


def get_list_widget_style():
    """Style pour les listes (QListWidget et QListView)"""
    return f"""
        QListWidget, QListView {{
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            background-color: {COLORS['card_bg']};
            padding: 3px;
            outline: none;
        }}
        QListWidget::item, QListView::item {{
            padding: 5px 8px;
            border-radius: 4px;
            margin: 1px 2px;
        }}
        QListWidget::item:selected, QListView::item:selected {{
            background-color: {COLORS['bg_selected']};
            color: {COLORS['primary']};
            border-left: 2px solid {COLORS['accent']};
        }}
        QListWidget::item:hover:!selected, QListView::item:hover:!selected {{
            background-color: {COLORS['bg_hover']};
        }}
    """


def get_table_style():
    """Style pour les tableaux (QTableWidget, QTreeWidget)"""
    return f"""
        QTableWidget, QTableView, QTreeWidget {{
            border: none;
            border-radius: 0px;
            background-color: #ffffff;
            alternate-background-color: {COLORS['bg']};
            gridline-color: transparent;
            outline: none;
        }}
        QTableWidget::item, QTableView::item, QTreeWidget::item {{
            padding: 7px 8px;
            border-bottom: 1px solid {COLORS['border_light']};
            color: {COLORS['text_primary']};
        }}
        QTableWidget::item:selected, QTableView::item:selected, QTreeWidget::item:selected {{
            background-color: {COLORS['bg_selected']};
            color: {COLORS['primary']};
            border-top: 1px solid {COLORS['accent']};
            border-bottom: 1px solid {COLORS['accent']};
            font-weight: 600;
        }}
        QTableWidget::item:hover:!selected, QTableView::item:hover:!selected {{
            background-color: {COLORS['bg_hover']};
        }}
        QHeaderView::section {{
            background-color: #ffffff;
            padding: 8px 8px;
            border: none;
            border-bottom: 2px solid {COLORS['border']};
            font-size: 11px;
            font-weight: 600;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            color: {COLORS['text_secondary']};
            letter-spacing: 0.3px;
        }}
        QHeaderView::section:first {{
            border-left: none;
        }}
        QTableWidget QLineEdit, QTableView QLineEdit,
        QTableWidget QComboBox, QTableView QComboBox {{
            padding: 0px 6px;
            border: none;
            min-height: 0;
            margin: 0;
            background: white;
            font-size: 12px;
        }}
        QTableWidget QLineEdit {{
            padding-top: 0px;
            padding-bottom: 0px;
        }}

        /* Style pour les conteneurs en mode lecture seule */
        QFrame[readonly="true"] {{
            background-color: {COLORS['bg_alt']};
        }}
    """


def get_checkbox_style():
    """Style pour les cases à cocher (QCheckBox)"""
    return f"""
        QCheckBox {{
            spacing: 6px;
            color: {COLORS['text_primary']};
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1.5px solid {COLORS['border']};
            background-color: {COLORS['card_bg']};
        }}
        QCheckBox::indicator:hover {{
            border-color: {COLORS['primary']};
            background-color: {COLORS['bg_hover']};
        }}
        QCheckBox::indicator:checked {{
            background-color: {COLORS['primary']};
            border-color: {COLORS['primary']};
        }}
        QCheckBox::indicator:checked:hover {{
            background-color: {COLORS['primary_hover']};
        }}
    """


def get_splitter_style():
    """Style pour les séparateurs (QSplitter)"""
    return f"""
        QSplitter::handle {{
            background-color: {COLORS['border_light']};
        }}
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        QSplitter::handle:vertical {{
            height: 2px;
        }}
    """


def get_status_label_style(status_type='info'):
    """Style pour les labels de statut"""
    color = COLORS.get(status_type, COLORS['info'])
    return f"""
        color: {color};
        font-size: 12px;
    """


def get_scrollbar_style():
    """Style pour les barres de défilement"""
    return f"""
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #cbd5e1;
            min-height: 30px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #94a3b8;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 10px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: #cbd5e1;
            min-width: 30px;
            border-radius: 5px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: #94a3b8;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
    """

def get_filter_tab_button_style(active: bool) -> str:
    """Style pour les boutons onglet de filtre dispositif (actif / inactif)."""
    if active:
        return f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: 2px solid {COLORS['accent']};
                border-radius: 5px;
                padding: 4px 11px;
                font-size: 12px;
                font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """
    else:
        return f"""
            QPushButton {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 5px 12px;
                font-size: 12px;
                font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_hover']};
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
        """


def get_collapsible_section_toggle_style():
    """Style QToolButton pour les sections repliables (Big Brother et Dossier)."""
    return f"""
        QToolButton {{
            border: none;
            border-bottom: 2px solid {COLORS['primary']};
            background-color: #f8f9fa;
            padding: 6px 8px;
            font-weight: 600;
            font-size: 12px;
            color: {COLORS['primary']};
            text-align: left;
        }}
        QToolButton:hover {{
            background-color: {COLORS['bg_hover']};
        }}
    """


def get_menu_style():
    """Style pour les menus contextuels et menus de boutons (QMenu)"""
    return f"""
        QMenu {{
            background-color: #ffffff;
            border: 1px solid {COLORS['border']};
            border-radius: 7px;
            padding: 4px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
            font-size: 12px;
        }}
        QMenu::item {{
            padding: 5px 24px 5px 12px;
            border-radius: 4px;
            margin: 1px 2px;
            color: {COLORS['text_primary']};
        }}
        QMenu::item:selected {{
            background-color: {COLORS['bg_hover']};
            color: {COLORS['primary']};
        }}
        QMenu::item:disabled {{
            color: {COLORS['disabled_text']};
        }}
        QMenu::separator {{
            height: 1px;
            background: {COLORS['border_light']};
            margin: 3px 6px;
        }}
    """


def get_tooltip_style():
    """Style global des info-bulles (QToolTip) — remplace le jaune système.

    Fond bleu GUSH + texte blanc, bordure et coins arrondis discrets. Le contenu
    des tooltips riches (cellules de tableau) est mis en page via
    format_tooltip_html() ; ce style ne gère que l'apparence de la boîte.
    """
    return f"""
        QToolTip {{
            background-color: {COLORS['primary']};
            color: #ffffff;
            border: 1px solid {COLORS['primary_pressed']};
            border-radius: 5px;
            padding: 2px 2px;
            font-size: 12px;
            font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;
        }}
    """


# ============================================================================
#                    STYLESHEET COMPLET POUR APPLICATION
# ============================================================================

def get_complete_stylesheet():
    """
    Retourne un stylesheet complet combinant tous les styles
    Utilisable pour une application entière
    """
    return f"""
        {get_main_window_style()}

        {get_card_frame_style()}

        {get_button_style()}

        {get_input_style()}

        {get_text_edit_style()}

        {get_list_widget_style()}

        {get_table_style()}

        {get_checkbox_style()}

        {get_splitter_style()}

        {get_scrollbar_style()}

        {get_menu_style()}

        {get_tooltip_style()}
    """


# ============================================================================
#                           HELPER FUNCTIONS
# ============================================================================

def format_tooltip_html(text, max_width: int = 600) -> str:
    """Met en forme un texte d'info-bulle pour une lecture facile.

    Le contenu est plafonné à `max_width` px : les lignes plus longues sont
    renvoyées à la ligne automatiquement, et les retours à la ligne existants
    (historique de commentaires) sont préservés. Les tooltips courts gardent leur
    largeur naturelle pour éviter une grande boîte à moitié vide.

    Retourne du HTML compris par QToolTip / le mécanisme d'info-bulle de Qt.
    """
    import html as _html

    text = str(text)
    width = max_width
    # Largeur naturelle de la ligne la plus longue, selon la police du tooltip.
    # Encapsulé dans un try : QFontMetrics nécessite une QApplication active
    # (toujours le cas au moment de l'affichage d'un tooltip).
    try:
        from PySide6.QtGui import QFontMetrics
        from PySide6.QtWidgets import QToolTip
        fm = QFontMetrics(QToolTip.font())
        natural = max(
            (fm.horizontalAdvance(line) for line in text.split("\n")),
            default=0,
        )
        width = min(natural + 8, max_width)  # +petite marge interne
    except Exception:
        width = max_width

    escaped = _html.escape(text).replace("\n", "<br>")
    # La largeur fixe de la cellule force le retour à la ligne de Qt.
    return (
        f'<table cellpadding="0" cellspacing="0"><tr>'
        f'<td width="{width}">{escaped}</td></tr></table>'
    )


def apply_button_style_to_widget(button, button_type='primary'):
    """
    Applique un style spécifique à un bouton

    Args:
        button: Le widget QPushButton
        button_type: 'primary', 'secondary', 'success', 'danger', 'warning', 'reload', 'accent_alt'
    """
    styles = {
        'primary': get_button_style(),
        'secondary': get_secondary_button_style(),
        'success': get_success_button_style(),
        'danger': get_danger_button_style(),
        'warning': get_warning_button_style(),
        'reload': get_reload_button_style(),
        'accent_alt': get_accent_alt_button_style(),
    }

    style = styles.get(button_type, get_button_style())
    button.setStyleSheet(style)


def apply_title_style_to_label(label, title_type='main'):
    """
    Applique un style de titre à un QLabel

    Args:
        label: Le widget QLabel
        title_type: 'main', 'subtitle', 'section'
    """
    styles = {
        'main': get_title_style(),
        'subtitle': get_subtitle_style(),
        'section': get_section_title_style(),
    }

    style = styles.get(title_type, get_title_style())
    label.setStyleSheet(style)


def set_window_icon(window, icon_filename='icon.ico'):
    """
    Définit l'icône d'une fenêtre (favicon)

    Args:
        window: La fenêtre QMainWindow ou QWidget
        icon_filename: Nom du fichier d'icône (par défaut 'icon.ico')
    """
    from PySide6.QtGui import QIcon

    # Fonction robuste pour trouver le chemin des ressources, compatible PyInstaller
    def resource_path(relative_path):
        """ Obtenir le chemin absolu vers une ressource, fonctionne pour le dev et pour PyInstaller """
        # 1. Vérifier dans le bundle PyInstaller (_MEIPASS) si présent
        if hasattr(sys, '_MEIPASS'):
            path_in_bundle = os.path.join(sys._MEIPASS, relative_path)
            if os.path.exists(path_in_bundle):
                return path_in_bundle

        # 2. Vérifier à côté de l'exécutable (si frozen) ou du script (dev)
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.abspath(os.path.dirname(__file__))

        return os.path.join(base_path, relative_path)

    icon_path = resource_path(icon_filename)

    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
        return True
    
    print(f"Avertissement : Fichier d'icône introuvable à l'emplacement '{icon_path}'")
    return False
