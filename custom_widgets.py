"""custom_widgets.py — widgets génériques réutilisables (issus du projet GUSH).

Copie locale allégée pour le Gestionnaire Serveur : on ne garde que les widgets
d'interface génériques (switches, combos, champs de formulaire). La logique
métier propre à GUSH (cartouches « demande », éditeur de commentaires, dialogue
« Com Gush », menus contextuels « dossier », en-têtes de tableaux…) a été retirée.
"""

from PySide6.QtWidgets import (
    QComboBox, QLineEdit, QCompleter, QTextEdit, QHBoxLayout, QPushButton, QFrame,
    QListView, QWidget, QCheckBox, QApplication, QSizePolicy
)
from PySide6.QtGui import QStandardItemModel, QStandardItem, QColor, QFontMetrics, QKeySequence, QAction, QPainter
from PySide6.QtCore import Qt, QDate, QTimer, Signal, QEvent, QSize, QPropertyAnimation, QRect, QEasingCurve
from py_utils import is_empty
from common_styles import COLORS

__all__ = [
    "YesNoButtonGroup",
    "SegmentedSwitch",
    "ToggleSwitch",
    "SafeComboBox",
    "MultiSelectComboBox",
    "SmartDateEdit",
    "AutoResizingTextEdit",
    "apply_modern_effects",
]


class YesNoButtonGroup(QWidget):
    """Groupe de deux boutons radio Oui/Non."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_oui = QPushButton("Oui")
        self.btn_non = QPushButton("Non")
        self.btn_oui.setCheckable(True)
        self.btn_non.setCheckable(True)
        self.btn_oui.setFixedWidth(60)
        self.btn_non.setFixedWidth(60)

        self.btn_oui.clicked.connect(lambda: self._select(True))
        self.btn_non.clicked.connect(lambda: self._select(False))

        layout.addWidget(self.btn_oui)
        layout.addWidget(self.btn_non)
        layout.addStretch()
        self._update_styles()

    def _select(self, is_oui: bool):
        self.btn_oui.setChecked(is_oui)
        self.btn_non.setChecked(not is_oui)
        self._update_styles()
        self.changed.emit()

    def get_value(self) -> str:
        if self.btn_oui.isChecked():
            return "Oui"
        if self.btn_non.isChecked():
            return "Non"
        return ""

    def set_value(self, value):
        val = str(value).strip().lower() if not is_empty(value) else ""
        self.btn_oui.setChecked(val == "oui")
        self.btn_non.setChecked(val == "non")
        self._update_styles()

    def clear(self):
        self.btn_oui.setChecked(False)
        self.btn_non.setChecked(False)
        self._update_styles()

    def _update_styles(self):
        active = f"background-color: {COLORS['primary']}; color: white; border: none; border-radius: 4px; padding: 4px 8px; font-weight: 600;"
        inactive = f"background-color: {COLORS['bg']}; color: {COLORS['text_primary']}; border: 1px solid {COLORS['border_light']}; border-radius: 4px; padding: 4px 8px;"
        self.btn_oui.setStyleSheet(active if self.btn_oui.isChecked() else inactive)
        self.btn_non.setStyleSheet(active if self.btn_non.isChecked() else inactive)


class SegmentedSwitch(QWidget):
    """Sélecteur segmenté animé : un indicateur glisse vers le segment choisi,
    façon interrupteur (« ça switche »). Générique pour 2, 3 segments ou plus.

    Deux rendus via `style` :
      - "filled"    : pastille pleine colorée qui glisse sur une piste enfoncée.
                      L'aplat (et non un contour) fait lire l'ensemble comme UN
                      curseur unique, pas comme des boutons collés.
      - "underline" : barre fine qui glisse sous le libellé actif, façon onglets.

    `options` accepte des libellés simples OU des couples (libellé, couleur) pour
    une sémantique par état :
        SegmentedSwitch(["Oui", "Non"])
        SegmentedSwitch([("Commission",  COLORS['primary']),
                         ("Dossiers OK", COLORS['success']),
                         ("Incomplets",  COLORS['warning'])], style="filled")

    API alignée sur YesNoButtonGroup : signal `changed(index)` émis sur action
    UTILISATEUR uniquement ; `get_value`/`set_value` et `current_index`/`set_index`.
    Les changements programmatiques (set_value/set_index) ne ré-émettent pas —
    même convention que MultiSelectComboBox/SmartDateEdit — pour ne pas marquer
    un formulaire « modifié » au simple chargement des valeurs.
    """
    changed = Signal(int)

    _R = 8     # rayon des coins extérieurs (rendu "filled") — doit matcher la piste
    _BAR_H = 3 # épaisseur de la barre (rendu "underline")

    # Couleurs maison par nombre de segments (clés de COLORS), appliquées aux
    # segments sans couleur explicite — cf. parsing des options dans __init__.
    _DEFAULT_COLOR_SETS = {
        2: ('primary', 'primary_canard'),
        3: ('primary', 'success', 'warning'),
    }
    # Au-delà de 3 segments : on cycle sur ces 5 teintes (répétées pour un 6e,
    # 7e… segment) pour garder des changements de couleur lisibles et ne reboucler
    # que très rarement.
    _DEFAULT_COLOR_CYCLE = (
        'primary', 'primary_canard', 'success', 'warning', 'accent_alt')

    def __init__(self, options, style="filled", default_index=0, parent=None):
        super().__init__(parent)
        self._style = style if style in ("filled", "underline") else "filled"

        self._labels = []
        self._colors = []
        explicit = []   # couleur fournie par l'appelant (vs défaut) pour ce segment
        for opt in options:
            if isinstance(opt, (tuple, list)) and len(opt) > 1 and opt[1]:
                label, color, is_explicit = opt[0], opt[1], True
            else:
                label = opt[0] if isinstance(opt, (tuple, list)) else opt
                color, is_explicit = COLORS['primary'], False
            self._labels.append(str(label))
            self._colors.append(color)
            explicit.append(is_explicit)

        # Palettes maison appliquées aux segments dont la couleur n'est pas fournie
        # explicitement. Centralisé dans le widget pour un rendu toujours identique,
        # plutôt que de compter sur chaque appelant :
        #   2 états → bleu GUSH / bleu canard
        #   3 états → bleu GUSH / vert pastel / orange doré
        #   4+      → cycle des 5 teintes (répété au-delà)
        default_set = self._DEFAULT_COLOR_SETS.get(len(self._labels))
        cycle = self._DEFAULT_COLOR_CYCLE
        for i in range(len(self._labels)):
            if explicit[i]:
                continue
            key = default_set[i] if default_set else cycle[i % len(cycle)]
            self._colors[i] = COLORS[key]

        self._index = default_index if 0 <= default_index < len(self._labels) else 0
        self._buttons = []

        # La piste est dessinée par le widget lui-même (fond enfoncé ou ligne de
        # base), d'où WA_StyledBackground + un objectName ciblé par la QSS.
        self.setObjectName("segmentedSwitch")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(32)

        # Marges nulles : en "filled" la pastille remplit jusqu'aux bords et partage
        # les coins arrondis de la piste → lecture « bouton unique » (cf. _thumb_radii).
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Indicateur mobile (pastille ou barre) : enfant créé AVANT les boutons
        # pour rester sous eux dans l'ordre d'empilement, et hors layout pour
        # qu'on le positionne nous-mêmes via setGeometry/animation.
        self._thumb = QFrame(self)
        self._thumb.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        for i, label in enumerate(self._labels):
            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(lambda _=False, idx=i: self._on_clicked(idx))
            self._buttons.append(btn)
            layout.addWidget(btn)

        # Animation de l'indicateur : léger dépassement (OutBack) pour l'effet ressort.
        self._anim = QPropertyAnimation(self._thumb, b"geometry", self)
        self._anim.setDuration(220)
        # OutCubic (sans dépassement) : la pastille s'arrête pile au bord, sans
        # déborder du coin arrondi de la piste.
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        # À l'arrivée, la pastille « se cale » dans le coin (coins adaptatifs).
        self._anim.finished.connect(self._dock_thumb)

        self._apply_container_style()
        self._refresh_buttons()
        self._apply_thumb_style(self._thumb_radii())
        self._thumb.lower()
        # Géométrie initiale : après le 1er passage de layout (sizes connus).
        QTimer.singleShot(0, self, lambda: self._reposition(animate=False))

    # ----- Style -----

    def _apply_container_style(self):
        if self._style == "filled":
            qss = (f"#segmentedSwitch {{ background: {COLORS['bg_alt']}; "
                   f"border-radius: {self._R}px; }}")
        else:
            qss = (f"#segmentedSwitch {{ background: transparent; "
                   f"border-bottom: 1px solid {COLORS['border']}; }}")
        self.setStyleSheet(qss)

    def _thumb_radii(self):
        """Rayons (tl, tr, br, bl) de la pastille selon sa position : coins
        extérieurs arrondis aux extrémités, intérieurs carrés → l'ensemble se lit
        comme un seul bouton (et non des pavés séparés)."""
        if self._style != "filled":
            return (2, 2, 2, 2)
        i, n = self._index, len(self._buttons)
        left = self._R if i == 0 else 0
        right = self._R if i == n - 1 else 0
        return (left, right, right, left)

    def _apply_thumb_style(self, radii):
        color = self._colors[self._index] if self._buttons else COLORS['primary']
        tl, tr, br, bl = radii
        self._thumb.setStyleSheet(
            "QFrame { background: %s; border: none;"
            " border-top-left-radius: %dpx; border-top-right-radius: %dpx;"
            " border-bottom-right-radius: %dpx; border-bottom-left-radius: %dpx; }"
            % (color, tl, tr, br, bl)
        )

    def _dock_thumb(self):
        """Fin de glisse : applique les coins adaptatifs (extérieurs arrondis,
        intérieurs carrés). Pendant la glisse la pastille est tout-arrondie
        (flottante), puis elle se cale dans le coin à l'arrêt."""
        self._apply_thumb_style(self._thumb_radii())

    def _refresh_buttons(self):
        for i, btn in enumerate(self._buttons):
            active = (i == self._index)
            if self._style == "filled":
                # Texte blanc sur la pastille colorée, gris discret sinon.
                color = "#ffffff" if active else COLORS['text_secondary']
            else:
                # Le libellé actif prend sa couleur sémantique.
                color = self._colors[i] if active else COLORS['text_secondary']
            weight = "600" if active else "400"
            btn.setStyleSheet(
                "QPushButton {"
                "background: transparent; border: none; padding: 6px 10px;"
                f"font-size: 12px; color: {color}; font-weight: {weight};"
                "font-family: 'Segoe UI Variable', 'Segoe UI', system-ui, sans-serif;"
                "}"
            )

    # ----- Positionnement de l'indicateur -----

    def _thumb_rect_for(self, i):
        """Géométrie cible de l'indicateur pour le segment i."""
        b = self._buttons[i].geometry()
        if self._style == "filled":
            # Marges nulles : la pastille remplit pile le segment, bord à bord.
            return QRect(b)
        inset = 6
        return QRect(b.x() + inset, self.height() - self._BAR_H,
                     max(0, b.width() - 2 * inset), self._BAR_H)

    def _reposition(self, animate=True):
        if not self._buttons:
            return
        target = self._thumb_rect_for(self._index)
        if animate and self.isVisible():
            # Pendant la glisse : pastille tout-arrondie (flottante) ; elle se cale
            # dans le coin à l'arrivée via _dock_thumb (anim.finished).
            r = self._R if self._style == "filled" else 2
            self._apply_thumb_style((r, r, r, r))
            self._anim.stop()
            self._anim.setStartValue(self._thumb.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._apply_thumb_style(self._thumb_radii())
            self._thumb.setGeometry(target)
        self._thumb.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Un resize peut survenir PENDANT la glisse (ex. un voisin du layout qui
        # apparaît/disparaît) : la géométrie des boutons vient de changer, donc
        # l'endValue de l'animation est périmé. On réoriente l'animation en cours
        # vers la nouvelle cible plutôt que de la laisser finir décalée ; sinon on
        # recale directement la pastille.
        if self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.setEndValue(self._thumb_rect_for(self._index))
        else:
            self._reposition(animate=False)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition(animate=False)

    # ----- Interaction / API publique -----

    def _on_clicked(self, idx):
        if idx == self._index or not (0 <= idx < len(self._buttons)):
            return
        self._index = idx
        self._refresh_buttons()
        self._reposition(animate=True)
        self.changed.emit(self._index)

    def current_index(self) -> int:
        return self._index

    def set_index(self, idx, animate=False):
        """Sélection programmatique (n'émet pas `changed`)."""
        if not (0 <= idx < len(self._buttons)) or idx == self._index:
            return
        self._index = idx
        self._refresh_buttons()
        self._reposition(animate=animate)

    def get_value(self) -> str:
        return self._labels[self._index] if self._buttons else ""

    def set_value(self, label, animate=False):
        """Sélection programmatique par libellé (n'émet pas `changed`)."""
        target = str(label).strip().lower()
        for i, lab in enumerate(self._labels):
            if lab.strip().lower() == target:
                self.set_index(i, animate=animate)
                return

    def set_segment_text(self, idx, text):
        """Met à jour le libellé d'un segment (ex. compteurs dynamiques « Titre · N »).

        Ne change ni la sélection ni les couleurs. Attention si `set_value` est
        utilisé par ailleurs : il compare sur le libellé courant.
        """
        if not (0 <= idx < len(self._buttons)):
            return
        self._labels[idx] = str(text)
        self._buttons[idx].setText(str(text))
        # Les segments se partagent la largeur (Expanding) : elle ne bouge en
        # général pas, mais on recale l'indicateur après le passage de layout.
        QTimer.singleShot(0, self, lambda: self._reposition(animate=False))


class ToggleSwitch(QWidget):
    """Interrupteur On/Off animé façon iOS : une pastille ronde glisse dans une
    glissière qui change de couleur. Remplaçant « joli » d'une QCheckBox pour un
    booléen pur (activer/désactiver), quand un Oui/Non à deux libellés n'a pas de sens.

    API calquée sur QCheckBox (`isChecked` / `setChecked` / `toggle` + signal
    `toggled(bool)`) → remplacement direct sans toucher aux appelants existants.
    La glissière est peinte (paintEvent) et non stylée par QSS : un setStyleSheet
    externe ne casse donc pas le rendu.
    """
    toggled = Signal(bool)

    def __init__(self, checked=False, parent=None, on_color=None, off_color=None):
        super().__init__(parent)
        self._checked = bool(checked)
        self._on_color = on_color or COLORS['primary']
        self._off_color = off_color or COLORS['text_light']  # gris discret en OFF
        self._track_w, self._track_h, self._knob, self._margin = 44, 24, 18, 3

        self.setFixedSize(self._track_w, self._track_h)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Pastille blanche : enfant peint au-dessus de la glissière, déplacé par animation.
        self._handle = QFrame(self)
        self._handle.setFixedSize(self._knob, self._knob)
        self._handle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._handle.setStyleSheet(
            f"QFrame {{ background: #ffffff; border: none; border-radius: {self._knob // 2}px; }}"
        )

        self._anim = QPropertyAnimation(self._handle, b"geometry", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._place_handle(animate=False)

    def _handle_rect(self) -> QRect:
        x = (self._track_w - self._knob - self._margin) if self._checked else self._margin
        return QRect(x, self._margin, self._knob, self._knob)

    def _place_handle(self, animate=True):
        target = self._handle_rect()
        if animate and self.isVisible():
            self._anim.stop()
            self._anim.setStartValue(self._handle.geometry())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._handle.setGeometry(target)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(self._on_color if self._checked else self._off_color))
        r = self.rect()
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)

    def showEvent(self, event):
        super().showEvent(event)
        self._place_handle(animate=False)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.toggle()
            return
        super().keyPressEvent(event)

    # ----- API compatible QCheckBox -----

    def toggle(self):
        self.setChecked(not self._checked)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        """Comme QCheckBox : émet `toggled(bool)` si l'état change."""
        checked = bool(checked)
        if checked == self._checked:
            return
        self._checked = checked
        self._place_handle(animate=True)
        self.update()
        self.toggled.emit(self._checked)


class SafeComboBox(QComboBox):
    """
    QComboBox personnalisée qui ignore les événements de la molette de la souris
    sauf si le widget a le focus.

    Cela empêche les changements de valeur accidentels lors du défilement
    d'une page contenant des comboboxes (problème fréquent en PyQt).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._scroll_disabled = False

    def set_scroll_disabled(self, disabled: bool):
        """Active ou désactive totalement le défilement à la molette."""
        self._scroll_disabled = disabled


    def wheelEvent(self, event):
        if self._scroll_disabled:
            event.ignore()
            return

        if self.hasFocus():
            super().wheelEvent(event)
        else:
            # Ignorer l'événement pour qu'il soit propagé au parent (ex: ScrollArea)
            event.ignore()

    def set_filterable(self, filterable: bool = True):
        """
        Active le mode recherche : la combobox devient éditable et propose
        une autocomplétion basée sur le contenu (MatchContains).
        """
        if filterable:
            self.setEditable(True)
            self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

            # Créer un completer qui cherche n'importe où dans la chaîne
            completer = QCompleter(self.model(), self)
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(completer)

        else:
            self.setEditable(False)
            self.setCompleter(None)

class MultiSelectCompleter(QCompleter):
    """
    Completer personnalisé pour la sélection multiple.
    Permet de filtrer sur le dernier terme saisi (après le dernier point-virgule).
    """
    def splitPath(self, path):
        # On ne garde que la partie après le dernier point-virgule pour le filtrage
        return [path.split(';')[-1].strip()]

class MultiSelectComboBox(SafeComboBox):
    """
    ComboBox permettant la sélection multiple avec affichage des sélections.
    Générique : les items sont passés via add_items().
    """
    # Émis sur changement de sélection PILOTÉ PAR L'UTILISATEUR (case cochée,
    # autocomplétion). Les changements programmatiques (set_selected/_items) n'émettent
    # pas — même convention que SmartDateEdit.setDate — pour ne pas marquer un
    # formulaire « modifié » au simple chargement des valeurs.
    selection_changed = Signal(list)

    def __init__(self, parent=None, items=None, placeholder="Sélectionner..."):
        super().__init__(parent)
        self.selected_items = []
        self.setEditable(True)
        self.lineEdit().setReadOnly(False)  # Permettre la saisie
        self.lineEdit().setPlaceholderText(placeholder)

        # Utiliser une QListView pour afficher les checkboxes
        list_view = QListView(self)
        list_view.setStyleSheet(f"""
            QListView {{
                background-color: {COLORS['card_bg']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 3px;
                outline: none;
            }}
            QListView::item {{
                min-height: 24px;
                padding: 3px 8px;
                color: {COLORS['text_primary']};
            }}
            QListView::item:hover {{
                background-color: {COLORS['bg_hover']};
                color: {COLORS['text_primary']};
            }}
            QListView::item:selected {{
                background-color: {COLORS['bg_selected']};
                color: {COLORS['primary']};
            }}
        """)
        self.setView(list_view)
        self.view().setWordWrap(False)
        # Taille uniforme : évite les bugs de repaint au hover (chevauchement des items)
        list_view.setUniformItemSizes(True)
        self.view().viewport().installEventFilter(self)

        # Créer le modèle avec checkboxes
        self._item_model = QStandardItemModel()
        self.setModel(self._item_model)
        self._item_model.itemChanged.connect(self._on_item_changed)

        # Ajouter un completer pour la recherche
        self._multi_completer = MultiSelectCompleter(self)
        self._multi_completer.setModel(self._item_model)
        self._multi_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._multi_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._multi_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._multi_completer.activated.connect(self._on_completer_activated)
        self.setCompleter(self._multi_completer)

        if items:
            self.add_items(items)

    def add_items(self, items):
        """Ajoute une liste d'items avec cases à cocher (dédupliqué)."""
        # Taille fixe pour tous les items : évite les variations de hauteur
        # avant/après la première sélection (bug de recalcul du sizeHint par Qt)
        fixed_size = QSize(0, 26)
        existing = {self._item_model.item(i).text()
                    for i in range(self._item_model.rowCount())}
        for text in sorted(items):
            text_str = str(text)
            if text_str in existing:
                continue
            existing.add(text_str)
            item = QStandardItem(text_str)
            item.setCheckable(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setToolTip(text_str)
            item.setSizeHint(fixed_size)
            self._item_model.appendRow(item)
        # S'assurer que le lineEdit est vide pour afficher le placeholder
        self.lineEdit().clear()
        self.setCurrentIndex(-1)

    def clear_items(self):
        """Supprime tous les items de la liste."""
        self._item_model.setRowCount(0)
        self.selected_items = []
        self.lineEdit().clear()

    def showPopup(self):
        """Affiche le popup en ajustant sa largeur au contenu le plus long."""
        # Calcul de la largeur nécessaire pour le plus long item
        fm = QFontMetrics(self.view().font())
        max_text_width = 0
        for i in range(self._item_model.rowCount()):
            w = fm.horizontalAdvance(self._item_model.item(i).text())
            if w > max_text_width:
                max_text_width = w

        # + espace pour la checkbox (~24px), padding interne (~24px) et scrollbar (~16px)
        needed_width = max_text_width + 70
        # Ne jamais rétrécir en dessous de la largeur du combobox lui-même
        needed_width = max(needed_width, self.width())
        self.view().setMinimumWidth(needed_width)

        super().showPopup()

    def eventFilter(self, obj, event):
        """Intercepte les clics pour gérer la sélection multiple sans fermer le popup."""
        if obj == self.view().viewport() and event.type() == QEvent.Type.MouseButtonRelease:
            index = self.view().indexAt(event.pos())
            if index.isValid():
                item = self._item_model.itemFromIndex(index)
                item.setCheckState(Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked)
                return True
        return super().eventFilter(obj, event)

    def _recompute_selection(self):
        """Recalcule self.selected_items depuis les cases cochées et rafraîchit
        l'affichage du lineEdit. N'émet AUCUN signal : réutilisé par les chemins
        programmatiques (set_selected/_items) qui ne doivent pas notifier."""
        # Utiliser un set pour garantir l'unicité, puis trier pour un ordre cohérent
        selected = set()
        for i in range(self._item_model.rowCount()):
            if self._item_model.item(i).checkState() == Qt.CheckState.Checked:
                selected.add(self._item_model.item(i).text())
        
        # Mettre à jour la liste interne avec les items triés
        self.selected_items = sorted(list(selected))

        if self.selected_items:
            # Utiliser "; " pour une meilleure lisibilité
            self.lineEdit().setText("; ".join(self.selected_items))
        else:
            # Effacer le texte pour que le placeholder soit visible
            self.lineEdit().clear()

    def _on_item_changed(self, item=None):
        """Slot des changements PILOTÉS PAR L'UTILISATEUR (case cochée via itemChanged) :
        recalcule, affiche avec un « ; » final prêt pour la recherche suivante,
        puis notifie via selection_changed."""
        self._recompute_selection()
        self._show_with_trailing_separator()
        self.selection_changed.emit(list(self.selected_items))

    def _show_with_trailing_separator(self):
        """Affiche le récap des sélections suivi de « ; » (séparateur prêt) et place
        le curseur à la fin, pour enchaîner une recherche sans retaper le séparateur.
        Cosmétique : selected_items reste la valeur réelle ; focusOutEvent nettoie
        le « ; » final au départ du focus. Champ vide si aucune sélection."""
        line = self.lineEdit()
        text = ("; ".join(self.selected_items) + "; ") if self.selected_items else ""
        line.setText(text)
        line.setCursorPosition(len(text))

    def _on_completer_activated(self, text):
        """Gère la sélection d'un item via l'autocomplétion"""
        if not text: return
        index = self.findText(text)
        if index >= 0:
            item = self._item_model.item(index)
            item.setCheckState(Qt.CheckState.Checked)
            # Le completer écrase le lineEdit avec la complétion choisie : on reporte
            # la remise en forme après son traitement (singleShot 0). On en profite
            # pour ajouter un « ; » final + curseur en fin, afin d'enchaîner une
            # nouvelle recherche sans avoir à retaper le séparateur.
            # Le receveur (self) lie la durée de vie : si le widget est détruit
            # avant le tir, Qt annule l'appel — pas besoin de garde RuntimeError.
            QTimer.singleShot(0, self, self._prime_next_search_term)

    def _prime_next_search_term(self):
        """Après une sélection via l'autocomplétion, le completer a écrasé le lineEdit :
        on réaffiche après coup (récap + « ; » final + curseur en fin) et on notifie."""
        self._show_with_trailing_separator()
        self.selection_changed.emit(list(self.selected_items))

    def get_selected(self) -> str:
        """Retourne les items sélectionnés séparés par ';'"""
        return "; ".join(self.selected_items)

    def get_selected_items(self) -> list:
        """Retourne la liste des items sélectionnés"""
        return list(self.selected_items)

    def _apply_selection(self, selected_set):
        """Coche/décoche les cases selon selected_set (ensemble de textes), sans
        émettre de signal par item, puis rafraîchit l'affichage propre. Cœur partagé
        de set_selected / set_selected_items (set programmatique → pas d'émission)."""
        # Bloquer les signaux pour éviter un _on_item_changed par item
        self._item_model.blockSignals(True)
        for i in range(self._item_model.rowCount()):
            item = self._item_model.item(i)
            desired = Qt.CheckState.Checked if item.text() in selected_set else Qt.CheckState.Unchecked
            if item.checkState() != desired:
                item.setCheckState(desired)
        self._item_model.blockSignals(False)
        # Set programmatique : affichage propre, aucune émission de selection_changed
        self._recompute_selection()

    def set_selected(self, value: str):
        """Définit les items sélectionnés depuis une chaîne séparée par ';'."""
        if value and not is_empty(value):
            selected_set = {v.strip() for v in str(value).split(";") if v.strip()}
        else:
            selected_set = set()
        self._apply_selection(selected_set)

    def set_selected_items(self, items: list):
        """Définit les items sélectionnés depuis une liste."""
        selected_set = {str(x).strip() for x in items} if items else set()
        self._apply_selection(selected_set)

    def set_filterable(self, filterable: bool = True):
        """No-op : MultiSelectComboBox a déjà son propre completer multi-sélection.
        Override pour empêcher SafeComboBox.set_filterable d'écraser le
        MultiSelectCompleter et de casser la sélection multiple."""
        return

    def focusOutEvent(self, event):
        """Restaure le récapitulatif « a; b; c » si l'utilisateur a tapé un terme de
        recherche sans valider d'entrée : sans ça le lineEdit garderait le texte
        partiel et masquerait la sélection réelle jusqu'au prochain toggle."""
        super().focusOutEvent(event)
        expected = "; ".join(self.selected_items)
        if self.lineEdit().text().strip() != expected:
            self.lineEdit().setText(expected)

    def keyPressEvent(self, event):
        """Gère les événements de saisie pour la recherche"""
        if event.key() == Qt.Key.Key_Enter or event.key() == Qt.Key.Key_Return:
            # Empêcher la fermeture du popup lors de la saisie
            event.ignore()
        else:
            super().keyPressEvent(event)
           
class SmartDateEdit(QLineEdit):
    """
    Widget d'édition de date optimisé pour la saisie rapide (JJ/MM/AAAA).
    Utilise un masque de saisie pour insérer automatiquement les séparateurs '/'
    et permet de taper la date d'une traite.
    """
    # Signal émis quand la date change (compatibilité avec QDateEdit)
    dateChanged = Signal(QDate)

    # Règle CSS ré-appliquée à chaque setStyleSheet pour que l'état "invalid"
    # reste piloté par la propriété Qt, quel que soit le style externe.
    _INVALID_RULE = 'QLineEdit[invalid="true"] { background-color: #ffe6e6; }'

    def __init__(self, parent=None):
        super().__init__(parent)
        # Masque: 00/00/0000 (chiffres obligatoires)
        # ;_ signifie que le caractère vide est '_'
        self.setInputMask("00/00/0000;_")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._last_valid_date = None  # Pour détecter les changements de date
        self._user_style = ""

        # Limiter la largeur maximale pour qu'elle soit adaptée à une date (DD/MM/YYYY)
        self.setMaximumWidth(110)
        self.setToolTip("Ctrl+; ou clic droit → insérer la date du jour")

        # État de validité piloté par propriété Qt (cf. _set_invalid)
        self.setProperty("invalid", False)
        super().setStyleSheet(self._INVALID_RULE)

        # Connecter le signal textChanged pour validation en temps réel
        self.textChanged.connect(self._validate_and_style)

    def setStyleSheet(self, qss):
        """Capture le style externe et y ré-injecte la règle d'invalidité.
        Permet à un parent d'appliquer setStyleSheet() sans casser le marquage
        visuel des dates invalides."""
        self._user_style = qss or ""
        super().setStyleSheet(self._user_style + "\n" + self._INVALID_RULE)

    def _set_invalid(self, invalid: bool):
        """Active/désactive l'état visuel d'erreur via une propriété Qt."""
        if bool(self.property("invalid")) == invalid:
            return
        self.setProperty("invalid", invalid)
        self.style().unpolish(self)
        self.style().polish(self)

    def setDate(self, date: QDate):
        """Définit la date (compatibilité avec l'interface QDateEdit)"""
        # Bloquer les signaux pour éviter la validation pendant qu'on définit le texte
        self.blockSignals(True)

        try:
            if date is None:
                self.clear()
                self._last_valid_date = None
            elif isinstance(date, QDate):
                if date.isValid():
                    self.setText(date.toString("dd/MM/yyyy"))
                    self._last_valid_date = date
                else:
                    self.clear()
                    self._last_valid_date = None
            else:
                # Gérer datetime ou objet date-like
                try:
                    if hasattr(date, 'year') and hasattr(date, 'month') and hasattr(date, 'day'):
                        qdate = QDate(int(date.year), int(date.month), int(date.day))
                        self.setText(qdate.toString("dd/MM/yyyy"))
                        self._last_valid_date = qdate
                    else:
                        self.clear()
                        self._last_valid_date = None
                except (ValueError, AttributeError):
                    self.clear()
                    self._last_valid_date = None
        finally:
            # Toujours réactiver les signaux
            self.blockSignals(False)

        # Valider et appliquer le style après avoir défini la date
        self._validate_and_style()

    def date(self):
        """Retourne la date comme QDate ou None si vide/invalide (compatibilité avec QDateEdit)"""
        text = self.text().strip()
        # Si le texte contient des underscores (masque non rempli), c'est vide
        if not text or '_' in text:
            return None

        try:
            # Parser le format DD/MM/YYYY ou DD/MM/YY
            if '/' in text:
                parts = text.split('/')
                if len(parts) == 3:
                    day = int(parts[0])
                    month = int(parts[1])
                    year = int(parts[2])
                    # Le masque impose 4 chiffres ; on refuse explicitement
                    # toute année hors plage plutôt que de deviner le siècle.
                    if not (1900 <= year <= 2100):
                        return None

                    qdate = QDate(year, month, day)
                    if qdate.isValid():
                        return qdate

        except (ValueError, IndexError):
            pass
        return None

    def _maybe_emit_change(self):
        """Émet dateChanged si la date courante diffère de la dernière valide."""
        current_date = self.date()
        if current_date != self._last_valid_date:
            self.dateChanged.emit(current_date if current_date is not None else QDate())
            self._last_valid_date = current_date

    def _validate_and_style(self):
        """Valide la date et bascule la propriété 'invalid' en conséquence."""
        text = self.text().strip()

        # Champ vide (ou que des séparateurs/underscores) : neutre
        if not text or text.replace('_', '').replace('/', '') == '':
            self._set_invalid(False)
            return

        # Masque incomplet
        if '_' in text:
            self._set_invalid(True)
            return

        qdate = self.date()
        if qdate is None:
            self._set_invalid(True)
        else:
            self._set_invalid(False)
            self._maybe_emit_change()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # Sélectionner tout le texte lors de la prise de focus pour permettre
        # le remplacement immédiat de la date existante par la nouvelle saisie
        QTimer.singleShot(0, self, self.selectAll)

    def focusOutEvent(self, event):
        """Au focus out, garantit qu'un changement vers 'vide' est aussi émis
        (les dates valides étant déjà notifiées par _validate_and_style)."""
        super().focusOutEvent(event)
        self._validate_and_style()
        self._maybe_emit_change()

    @staticmethod
    def _parse_flexible(text):
        """Tente de lire une date depuis un texte collé en formats variés
        (ISO aaaa-mm-jj, séparateurs . - espace, ou 8 chiffres collés).
        Retourne un QDate valide, ou None si rien d'exploitable."""
        s = (text or "").strip()
        if not s:
            return None
        # Formats explicites les plus courants
        for fmt in ("dd/MM/yyyy", "d/M/yyyy", "yyyy-MM-dd", "yyyy/MM/dd"):
            d = QDate.fromString(s, fmt)
            if d.isValid():
                return d
        # Normaliser . - espace -> / puis relire en jour/mois/année
        norm = s.replace(".", "/").replace("-", "/").replace(" ", "/")
        d = QDate.fromString(norm, "d/M/yyyy")
        if d.isValid():
            return d
        # 8 chiffres collés : jjmmaaaa ou aaaammjj
        digits = "".join(ch for ch in s if ch.isdigit())
        if len(digits) == 8:
            for fmt in ("ddMMyyyy", "yyyyMMdd"):
                d = QDate.fromString(digits, fmt)
                if d.isValid():
                    return d
        return None

    def _insert_today(self):
        """Insère la date du jour. Passe par setText (et non setDate) pour que
        textChanged se déclenche → validation + détection 'modifié' du formulaire."""
        self.setText(QDate.currentDate().toString("dd/MM/yyyy"))

    def keyPressEvent(self, event):
        # Collage tolérant : ISO / séparateurs . - espace -> JJ/MM/AAAA
        if event.matches(QKeySequence.StandardKey.Paste):
            qdate = self._parse_flexible(QApplication.clipboard().text())
            if qdate is not None and qdate.isValid():
                self.setText(qdate.toString("dd/MM/yyyy"))
                return
            # Sinon : laisser le collage par défaut (le masque filtrera)
        # Raccourci « aujourd'hui » : Ctrl+; (convention Excel/Sheets)
        elif (event.modifiers() == Qt.KeyboardModifier.ControlModifier
              and event.key() == Qt.Key.Key_Semicolon):
            self._insert_today()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        """Ajoute « Aujourd'hui » en tête du menu contextuel standard."""
        menu = self.createStandardContextMenu()
        today_action = QAction("Aujourd'hui", menu)
        today_action.triggered.connect(self._insert_today)
        actions = menu.actions()
        if actions:
            menu.insertAction(actions[0], today_action)
            menu.insertSeparator(actions[0])
        else:
            menu.addAction(today_action)
        menu.exec(event.globalPos())

    def wheelEvent(self, event):
        # Désactiver la molette pour éviter les changements accidentels
        event.ignore()

class AutoResizingTextEdit(QTextEdit):
    """
    QTextEdit qui ajuste automatiquement sa hauteur en fonction de son contenu.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.document().setDocumentMargin(4)
        self.textChanged.connect(self.adjustHeight)
        self._min_height = 10
        self._max_height = 200
        self._adjusting = False

        QTimer.singleShot(0, self, self.adjustHeight)

    def adjustHeight(self):
        """Ajuste la hauteur du widget pour s'adapter au contenu.
        Garde anti-récursion : setFixedHeight déclenche resizeEvent qui
        rappellerait adjustHeight et pourrait osciller."""
        if self._adjusting:
            return
        self._adjusting = True
        try:
            doc = self.document()
            # Forcer le recalcul de la taille du document avec la largeur disponible
            doc.setTextWidth(self.viewport().width() if self.viewport().width() > 0 else -1)
            doc_height = doc.size().height()
            # Ajouter les marges du frame (bordures haut + bas) et content margins
            margins = self.contentsMargins()
            frame_extra = 2 * self.frameWidth()
            total = doc_height + margins.top() + margins.bottom() + frame_extra
            # Si le contenu dépasse le plafond, autoriser le scroll vertical : sinon
            # le bas du texte est rogné et devient inaccessible (scrollbar Always Off).
            self.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded if int(total) > self._max_height
                else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            new_height = max(self._min_height, min(int(total), self._max_height))
            if new_height != self.height():
                self.setFixedHeight(new_height)
        finally:
            self._adjusting = False

    def resizeEvent(self, event):
        """Recalculer la hauteur quand la largeur change (wrap du texte)."""
        super().resizeEvent(event)
        self.adjustHeight()

    def setMaxHeight(self, height):
        self._max_height = height

    def setMinHeight(self, height):
        self._min_height = height
        self.adjustHeight()


def apply_modern_effects(widget):
    """
    Applique les effets visuels modernes : transparence des angles et ombre portée.
    """
    # Frameless est crucial pour éviter les bordures noires de Windows sur les arrondis
    widget.setWindowFlags(widget.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    
