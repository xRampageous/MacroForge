"""Main layout construction for MacroForge main window."""

from PyQt6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QMenu,
    QWidgetAction,
    QSlider,
    QSpinBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from version import VERSION
from ui.icons import icon
from ui.status_dot import StatusDot
from ui.theme import COLORS
from ui.timeline import TimelineView


def build_main_layout(window):
    self = window
    C = COLORS

    central = QWidget()
    central.setObjectName("root")
    central.setStyleSheet(
        f"QWidget#root {{ background-color: {C['bg']}; }}"
    )
    self.setCentralWidget(central)

    main_lo = QHBoxLayout(central)
    main_lo.setContentsMargins(0, 0, 0, 0)
    main_lo.setSpacing(0)

    def panel_frame(name, accent=None):
        frame = QFrame()
        frame.setObjectName(name)
        border = accent or C["border"]
        frame.setStyleSheet(
            f"QFrame#{name} {{ "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 {C['bg_card']}, stop:1 #00050B); "
            f"border: 1px solid {border}; border-radius: 10px; }}"
        )
        return frame

    def _caret_button(size=20):
        caret = QPushButton("^")
        caret.setObjectName("panel_caret_btn")
        caret.setFixedSize(size, size)
        caret.setCursor(Qt.CursorShape.PointingHandCursor)
        caret.setProperty("collapsed", False)
        caret.setToolTip("Collapse panel")
        caret.setStyleSheet(
            f"QPushButton#panel_caret_btn {{ color: {C['text_dim']}; background: transparent; "
            f"border: 1px solid transparent; border-radius: 6px; padding: 0; "
            "font-size: 12px; font-weight: 900; }}"
            f"QPushButton#panel_caret_btn:hover {{ color: {C['text']}; "
            f"background-color: {C['bg_hover']}; border-color: {C['border']}; }}"
        )
        return caret

    self._panel_collapse_controls = {}
    self._collapse_animations = {}

    def _toggle_collapsible_body(body_widget, caret):
        collapsed = not bool(caret.property("collapsed"))
        caret.setProperty("collapsed", collapsed)
        caret.setText("v" if collapsed else "^")
        caret.setToolTip("Expand down" if collapsed else "Collapse up")

        body_name = body_widget.objectName() or ""
        image_inspector_bodies = {
            "inspector_group_image_body",
            "inspector_group_matching_body",
            "inspector_group_retry_body",
            "inspector_group_on_fail_body",
            "inspector_group_fail_target_body",
        }
        is_image_inspector_body = body_name in image_inspector_bodies

        parent = body_widget.parentWidget()
        parent_name = parent.objectName() if parent is not None else ""
        anim_key = body_name or str(id(body_widget))
        previous_anim = self._collapse_animations.get(anim_key)
        if previous_anim is not None:
            try:
                previous_anim.stop()
            except Exception:
                pass

        def _refresh_inspector_size(delay_ms=0):
            if not hasattr(self, "_autosize_inspector_panel"):
                return
            try:
                if delay_ms > 0:
                    QTimer.singleShot(delay_ms, self._autosize_inspector_panel)
                else:
                    self._autosize_inspector_panel()
            except Exception:
                pass

        def _queue_side_panel_rebalance(reason="collapse", delays=(0, 24, 55, 95)):
            """Let the side-panel stack settle into space freed by a collapse/expand.

            The rebalancer is intentionally passive: it does not add resize
            thresholds or change lock state.  It only invalidates/activates the
            side-panel layout and refreshes stale height clamps so the spacer
            and Inspector can absorb freed height smoothly while a body animates.
            """
            rebalance = getattr(self, "_rebalance_side_panel_space", None)
            if not callable(rebalance):
                return
            for delay in delays:
                try:
                    if delay <= 0:
                        rebalance(reason=reason)
                    else:
                        QTimer.singleShot(delay, lambda r=reason: rebalance(reason=r))
                except Exception:
                    pass

        def _collapsible_body_height_hint(widget):
            """Return the natural height of the whole collapsible body.

            Qt can report a stale/partial ``sizeHint`` while a body has just
            been collapsed or is still constrained by a previous animation.
            Measure from the body layout first so the IMAGE sub-panel uses the
            full section body container, not just the visible preview/template
            child that happened to have the last painted height.
            """
            if widget is None:
                return 1

            def _item_height(item):
                if item is None:
                    return 0
                child = item.widget()
                if child is not None:
                    if not child.isVisible() and child is not widget:
                        return 0
                    try:
                        child.ensurePolished()
                    except Exception:
                        pass
                    vals = []
                    for getter in (child.sizeHint, child.minimumSizeHint):
                        try:
                            vals.append(int(getter().height()))
                        except Exception:
                            pass
                    try:
                        if int(child.maximumHeight()) != 0:
                            vals.append(int(child.height()))
                    except Exception:
                        pass
                    return max([0] + vals)
                child_layout = item.layout()
                if child_layout is not None:
                    return _layout_height(child_layout)
                spacer = item.spacerItem()
                if spacer is not None:
                    try:
                        return max(0, int(spacer.sizeHint().height()))
                    except Exception:
                        return 0
                return 0

            def _layout_height(layout):
                if layout is None:
                    return 0
                try:
                    layout.invalidate()
                    layout.activate()
                except Exception:
                    pass
                try:
                    margins = layout.contentsMargins()
                    total = int(margins.top()) + int(margins.bottom())
                except Exception:
                    total = 0
                visible_items = []
                try:
                    count = layout.count()
                except Exception:
                    count = 0
                for i in range(count):
                    item = layout.itemAt(i)
                    h = _item_height(item)
                    if h > 0:
                        visible_items.append(h)
                if visible_items:
                    try:
                        total += max(0, int(layout.spacing())) * max(0, len(visible_items) - 1)
                    except Exception:
                        pass
                    total += sum(visible_items)
                try:
                    total = max(total, int(layout.sizeHint().height()))
                except Exception:
                    pass
                return max(0, total)

            try:
                widget.ensurePolished()
            except Exception:
                pass
            try:
                widget.setMinimumHeight(0)
                widget.setMaximumHeight(16777215)
            except Exception:
                pass
            try:
                layout = widget.layout()
            except Exception:
                layout = None

            vals = []
            if layout is not None:
                vals.append(_layout_height(layout))
            for getter in (widget.sizeHint, widget.minimumSizeHint):
                try:
                    vals.append(int(getter().height()))
                except Exception:
                    pass
            return max(1, *vals)

        def _side_panel_animation_tick(_value=None):
            try:
                body_widget.updateGeometry()
                if parent is not None:
                    parent.updateGeometry()
                sidebar_frame = getattr(self, "sidebar_frame", None)
                if sidebar_frame is not None:
                    layout = sidebar_frame.layout()
                    if layout is not None:
                        layout.invalidate()
                        layout.activate()
                    hug = getattr(self, "_apply_side_panel_content_hug", None)
                    if callable(hug):
                        hug(reason=f"{body_name}.animation")
                    sidebar_frame.updateGeometry()
            except Exception:
                pass

        def _finish_parent():
            if parent is None:
                return
            if collapsed:
                parent.setMinimumHeight(0)
                parent.setMaximumHeight(max(28, parent.minimumSizeHint().height() + 2))
                parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            else:
                parent.setMinimumHeight(0)
                parent.setMaximumHeight(16777215)
                if parent_name == "inspector_card":
                    parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                else:
                    parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            parent.updateGeometry()
            if parent_name == "inspector_card" or is_image_inspector_body:
                _refresh_inspector_size()
                if is_image_inspector_body:
                    _refresh_inspector_size(0)
                    _refresh_inspector_size(80)

        try:
            body_widget.setMinimumHeight(0)
            if is_image_inspector_body:
                # Image Inspector sub-panels sit inside an Inspector card that is
                # height-clamped to its selected content. Release the parent/card
                # clamps before measuring, otherwise expand can calculate against
                # the old collapsed height and leave controls half-visible.
                body_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                if parent is not None:
                    parent.setMinimumHeight(0)
                    parent.setMaximumHeight(16777215)
                    parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                    parent.updateGeometry()
                inspector_card = getattr(self, "insp_card", None)
                if inspector_card is not None:
                    inspector_card.setMinimumHeight(0)
                    inspector_card.setMaximumHeight(16777215)
                    inspector_card.updateGeometry()

            # Measure once, then animate only the body container height.
            # Do not hide/show child controls mid-animation: doing so makes Qt
            # recalculate sizeHint() from an artificially empty body, which can
            # cause wrong target heights, overlap, and broken expand/collapse
            # states.  The body itself is hidden only after collapse finishes.
            if collapsed:
                body_widget.setVisible(True)
                start_h = max(0, int(body_widget.height()))
                if start_h <= 1:
                    try:
                        start_h = max(1, int(body_widget.sizeHint().height()))
                    except Exception:
                        start_h = 1
                end_h = 0
                body_widget.setMaximumHeight(start_h)
            else:
                body_widget.setVisible(True)
                start_h = max(0, int(body_widget.height()))
                if start_h <= 1:
                    start_h = 0
                body_widget.setMaximumHeight(16777215)
                body_widget.updateGeometry()
                if parent is not None:
                    parent.updateGeometry()
                end_h = _collapsible_body_height_hint(body_widget)
                body_widget.setMaximumHeight(start_h)

            try:
                body_widget.setAttribute(Qt.WidgetAttribute.WA_ClipsChildrenToShape, True)
            except Exception:
                pass

            anim = QPropertyAnimation(body_widget, b"maximumHeight", self)
            # Snappier side-panel motion: short enough to feel responsive,
            # but still long enough to avoid abrupt layout jumps while Qt
            # recalculates the nested Inspector stack.
            anim.setDuration(78 if is_image_inspector_body else 92)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.setStartValue(start_h)
            anim.setEndValue(end_h)

            def _finished():
                if collapsed:
                    body_widget.setMaximumHeight(0)
                    body_widget.setVisible(False)
                else:
                    body_widget.setVisible(True)
                    body_widget.setMaximumHeight(16777215)
                _finish_parent()
                body_widget.updateGeometry()
                self._collapse_animations.pop(anim_key, None)
                _queue_side_panel_rebalance(reason=f"{body_name}.finished", delays=(0, 24, 65))

            try:
                anim.valueChanged.connect(_side_panel_animation_tick)
            except Exception:
                pass
            anim.finished.connect(_finished)
            self._collapse_animations[anim_key] = anim
            _queue_side_panel_rebalance(reason=f"{body_name}.start", delays=(0, 18))
            anim.start()
        except Exception:
            if collapsed:
                body_widget.setMaximumHeight(0)
                body_widget.setVisible(False)
            else:
                body_widget.setVisible(True)
                body_widget.setMaximumHeight(16777215)
            _finish_parent()
            _queue_side_panel_rebalance(reason=f"{body_name}.fallback", delays=(0, 24, 65))
        body_widget.updateGeometry()
        _side_panel_animation_tick()

    def _set_collapsible_panel(body_name, collapsed, auto=False):
        body_widget, caret = self._panel_collapse_controls.get(body_name, (None, None))
        if body_widget is None or caret is None:
            return False
        collapsed = bool(collapsed)
        auto = bool(auto)
        user_collapsed = bool(body_widget.property("user_collapsed"))
        auto_collapsed = bool(body_widget.property("auto_collapsed"))
        current = bool(caret.property("collapsed"))

        if auto:
            # Auto-height recovery must not reopen a panel the user explicitly
            # collapsed, and auto-collapse should avoid fighting manual locks.
            if collapsed and user_collapsed:
                return False
            if not collapsed and (not auto_collapsed or user_collapsed):
                return False
            body_widget.setProperty("auto_collapsed", collapsed)
        else:
            body_widget.setProperty("user_collapsed", collapsed)
            body_widget.setProperty("auto_collapsed", False)

        if current != collapsed:
            _toggle_collapsible_body(body_widget, caret)
        return True

    self._set_collapsible_panel = _set_collapsible_panel

    def section_header(text, icon_name, color, body_widget=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        left_balance = QWidget()
        left_balance.setFixedSize(20, 20)
        row.addWidget(left_balance)

        title_wrap = QWidget()
        title_lo = QHBoxLayout(title_wrap)
        title_lo.setContentsMargins(0, 0, 0, 0)
        title_lo.setSpacing(7)
        title_lo.addStretch()

        ico = QLabel()
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setPixmap(icon(icon_name, 16, color).pixmap(16, 16))
        ico.setFixedSize(18, 18)
        title_lo.addWidget(ico)

        lbl = QLabel(text)
        lbl.setObjectName("section")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 12px; font-weight: 850; "
            "letter-spacing: 0.7px; background: transparent;"
        )
        title_lo.addWidget(lbl)
        title_lo.addStretch()
        row.addWidget(title_wrap, stretch=1)

        if body_widget is not None:
            caret = _caret_button(20)
            self._panel_collapse_controls[body_widget.objectName()] = (body_widget, caret)
            caret.clicked.connect(
                lambda checked=False, body=body_widget: self._set_collapsible_panel(
                    body.objectName(),
                    not bool(self._panel_collapse_controls[body.objectName()][1].property("collapsed")),
                    auto=False,
                )
            )
            row.addWidget(caret)
        else:
            caret = QLabel("^")
            caret.setAlignment(Qt.AlignmentFlag.AlignCenter)
            caret.setFixedSize(20, 20)
            caret.setStyleSheet(f"color: {C['text_dim']}; font-size: 12px; background: transparent;")
            row.addWidget(caret)
        return row

    def form_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C['text_dim']}; font-size: 10px; font-weight: 750; "
            "background: transparent;"
        )
        return lbl

    def form_input(placeholder="", text=""):
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        if text:
            inp.setText(text)
        inp.setFixedHeight(30)
        inp.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 9px; "
            "font-size: 11px; }}"
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        return inp

    def compact_combo(items=None):
        combo = QComboBox()
        if items:
            combo.addItems(items)
        combo.setFixedHeight(30)
        combo.setStyleSheet(
            f"QComboBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 8px; "
            "font-size: 11px; }}"
            "QComboBox::drop-down { border: none; width: 18px; }"
        )
        return combo

    def inspector_group(title, icon_name, color, show_info=False):
        card = QFrame()
        card.setObjectName(f"inspector_group_{title.lower().replace(' ', '_')}")
        card.setStyleSheet(
            f"QFrame#{card.objectName()} {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            f"stop:0 #04111D, stop:1 #00060E); border: 1px solid {C['border']}; "
            "border-radius: 8px; }}"
        )
        lo = QVBoxLayout(card)
        lo.setContentsMargins(8, 8, 8, 8)
        lo.setSpacing(7)
        body = QWidget(card)
        body.setObjectName(f"{card.objectName()}_body")
        body.setProperty("collapsible_title", title)
        body_lo = QVBoxLayout(body)
        body_lo.setContentsMargins(0, 0, 0, 0)
        body_lo.setSpacing(7)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(0)

        left_balance = QWidget()
        left_balance.setFixedSize(18, 18)
        head.addWidget(left_balance)

        title_wrap = QWidget()
        title_lo = QHBoxLayout(title_wrap)
        title_lo.setContentsMargins(0, 0, 0, 0)
        title_lo.setSpacing(6)
        title_lo.addStretch()

        ico = QLabel()
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setPixmap(icon(icon_name, 14, color).pixmap(14, 14))
        ico.setFixedSize(15, 15)
        title_lo.addWidget(ico)

        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {C['text']}; font-size: 11px; font-weight: 850; "
            "letter-spacing: 0.35px; background: transparent;"
        )
        title_lo.addWidget(lbl)

        title_lo.addStretch()
        head.addWidget(title_wrap, stretch=1)

        caret = _caret_button(18)
        caret.setStyleSheet(
            f"QPushButton#panel_caret_btn {{ color: {C['text_dim']}; background: transparent; "
            f"border: 1px solid transparent; border-radius: 5px; padding: 0; "
            "font-size: 11px; font-weight: 900; }}"
            f"QPushButton#panel_caret_btn:hover {{ color: {C['text']}; "
            f"background-color: {C['bg_hover']}; border-color: {C['border']}; }}"
        )
        self._panel_collapse_controls[body.objectName()] = (body, caret)
        caret.clicked.connect(
            lambda checked=False, body=body: self._set_collapsible_panel(
                body.objectName(),
                not bool(self._panel_collapse_controls[body.objectName()][1].property("collapsed")),
                auto=False,
            )
        )
        head.addWidget(caret)
        lo.addLayout(head)
        lo.addWidget(body)
        return card, body_lo

    def inspector_value(text="", width=58):
        inp = QLineEdit(text)
        inp.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inp.setFixedSize(width, 28)
        inp.setStyleSheet(
            f"QLineEdit {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
            f"border: 1px solid {C['border']}; border-radius: 7px; padding: 2px 6px; "
            "font-size: 11px; font-weight: 750; }}"
            f"QLineEdit:focus {{ border-color: {C['accent']}; }}"
        )
        return inp

    # Left command rail.
    sidebar = QFrame()
    sidebar.setObjectName("mf3_sidebar")
    sidebar.setFixedWidth(270)
    sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    sidebar.setStyleSheet(
        f"QFrame#mf3_sidebar {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #020A13, stop:1 #000309); border-right: 1px solid {C['border']}; }}"
    )
    sb_lo = QVBoxLayout(sidebar)
    sb_lo.setContentsMargins(10, 14, 10, 10)
    sb_lo.setSpacing(8)

    brand_row = QHBoxLayout()
    brand_row.setContentsMargins(0, 0, 0, 0)
    brand_row.setSpacing(6)

    brand_box = QFrame()
    brand_box.setObjectName("macroforge_brand_box")
    brand_box.setFixedHeight(36)
    brand_box.setStyleSheet(
        f"QFrame#macroforge_brand_box {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #07172A, stop:0.55 #03101E, stop:1 #01070E); "
        f"border: 1px solid {C['border']}; border-radius: 10px; }}"
    )
    brand_box_lo = QHBoxLayout(brand_box)
    brand_box_lo.setContentsMargins(10, 0, 6, 0)
    brand_box_lo.setSpacing(6)

    brand = QLabel("MACROFORGE")
    brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
    brand.setStyleSheet(
        f"color: {C['text']}; font-size: 18px; font-weight: 950; "
        "letter-spacing: 0.4px; background: transparent;"
    )
    brand_box_lo.addWidget(brand, stretch=1)

    ver = QLabel(f"v{VERSION}")
    ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ver.setFixedSize(58, 23)
    ver.setStyleSheet(
        f"color: {C['accent']}; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {C['bg_tertiary']}, stop:1 #010913); "
        f"border: 1px solid {C['accent_glow']}; border-radius: 8px; "
        "font-size: 11px; font-weight: 900;"
    )
    brand_box_lo.addWidget(ver)

    brand_row.addWidget(brand_box, stretch=1)
    self.side_panel_lock_btn = _caret_button(22)
    self.side_panel_lock_btn.setText("🔓")
    self.side_panel_lock_btn.setToolTip("Lock side panel width")
    self.side_panel_lock_btn.clicked.connect(self._toggle_side_panel_lock)
    brand_row.addWidget(self.side_panel_lock_btn)

    self.sidebar_collapse_btn = _caret_button(22)
    self.sidebar_collapse_btn.setText("<")
    self.sidebar_collapse_btn.setToolTip("Collapse side panel")
    brand_row.addWidget(self.sidebar_collapse_btn)
    sb_lo.addLayout(brand_row)

    add_card = panel_frame("add_action_card")
    add_lo = QVBoxLayout(add_card)
    add_lo.setContentsMargins(10, 9, 10, 10)
    add_lo.setSpacing(5)
    add_body = QWidget(add_card)
    add_body.setObjectName("add_action_body")
    add_body_lo = QVBoxLayout(add_body)
    add_body_lo.setContentsMargins(0, 0, 0, 0)
    add_body_lo.setSpacing(0)
    add_lo.addLayout(section_header("ADD ACTION", "bolt", C["accent"], add_body))
    add_grid = QGridLayout()
    add_grid.setContentsMargins(0, 0, 0, 0)
    add_grid.setHorizontalSpacing(6)
    add_grid.setVerticalSpacing(5)
    add_grid.setColumnMinimumWidth(0, 104)
    add_grid.setColumnMinimumWidth(1, 104)
    action_specs = [
        ("Key", self._open_key_dialog, C["key"], "key", 0, 0, 1, 1),
        ("Click", self._open_click_dialog, C["click"], "click", 0, 1, 1, 1),
        ("Delay", self._open_pause_dialog, C["pause"], "delay", 1, 0, 1, 1),
        ("Image", self._open_image_dialog, C["image"], "image", 1, 1, 1, 1),
        ("Condition", self._open_condition_dialog, C["condition"], "condition", 2, 0, 1, 1),
        ("Loop", self._open_loop_dialog, C["loop"], "loop", 2, 1, 1, 1),
        ("Group", self._open_group_dialog, C["group"], "group", 3, 0, 1, 2),
    ]
    for text, callback, color, icon_name, row, col, rowspan, colspan in action_specs:
        btn = self._add_btn(text, callback, color, None, icon_name)
        btn_w = 216 if colspan > 1 else 104
        # Hard-lock every Add Action button to 42px tall. Widths remain unchanged.
        btn_h = 42
        btn.setFixedSize(btn_w, btn_h)
        btn.setMinimumSize(btn_w, btn_h)
        btn.setMaximumSize(btn_w, btn_h)
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        add_grid.setRowMinimumHeight(row, btn_h)
        add_grid.addWidget(btn, row, col, rowspan, colspan, alignment=Qt.AlignmentFlag.AlignCenter)
    add_body_lo.addLayout(add_grid)
    add_lo.addWidget(add_body)
    sb_lo.addWidget(add_card)

    rec_card = panel_frame("recorder_card")
    rec_lo = QVBoxLayout(rec_card)
    rec_lo.setContentsMargins(12, 10, 12, 12)
    rec_lo.setSpacing(9)
    rec_body = QWidget(rec_card)
    rec_body.setObjectName("recorder_body")
    rec_body_lo = QVBoxLayout(rec_body)
    rec_body_lo.setContentsMargins(0, 0, 0, 0)
    rec_body_lo.setSpacing(9)
    rec_lo.addLayout(section_header("RECORDER", "record", C["accent"], rec_body))
    rec_state = QHBoxLayout()
    rec_state.setContentsMargins(0, 0, 0, 0)
    rec_state.setSpacing(7)
    self.rec_dot = StatusDot()
    self.rec_dot.set_color(C["success"])
    rec_state.addWidget(self.rec_dot)
    self.rec_status = QLabel("IDLE")
    self.rec_status.setStyleSheet(
        f"color: {C['text']}; font-size: 12px; font-weight: 900; background: transparent;"
    )
    rec_state.addWidget(self.rec_status)
    rec_state.addStretch()
    self.rec_time = QLabel("00:00:00")
    self.rec_time.setStyleSheet(f"color: {C['text_dim']}; font-size: 11px; font-weight: 800;")
    rec_state.addWidget(self.rec_time)
    self.rec_actions = QLabel("0")
    self.rec_actions.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.rec_actions.setFixedSize(28, 24)
    self.rec_actions.setStyleSheet(
        f"color: {C['text']}; background-color: {C['bg_secondary']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; font-size: 11px;"
    )
    rec_state.addWidget(self.rec_actions)
    rec_body_lo.addLayout(rec_state)
    rec_buttons = QHBoxLayout()
    rec_buttons.setSpacing(8)
    rec_buttons.setContentsMargins(0, 0, 0, 0)
    self.rec_btn = QPushButton()
    self.rec_btn.setObjectName("rec_round_btn")
    self.rec_btn.setIcon(icon("record", 16, C["error"]))
    self.rec_btn.setIconSize(QSize(16, 16))
    self.rec_btn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    # Keep the icon-only recorder button but make it the requested wide
    # recording-control size.  Colors remain controlled by the existing theme.
    self.rec_btn.setFixedSize(100, 45)
    self.rec_btn.setMinimumSize(100, 45)
    self.rec_btn.setMaximumSize(100, 45)
    self.rec_btn.setToolTip("Record (F7)")
    self.rec_btn.clicked.connect(self._toggle_record)
    self.rec_pause_btn = QPushButton("Pause")
    self.rec_pause_btn.setObjectName("rec_pause_btn")
    self.rec_pause_btn.setIcon(icon("pause", 16, C["text_dim"]))
    self.rec_pause_btn.setIconSize(QSize(16, 16))
    self.rec_pause_btn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    self.rec_pause_btn.setFixedSize(100, 45)
    self.rec_pause_btn.setMinimumSize(100, 45)
    self.rec_pause_btn.setMaximumSize(100, 45)
    self.rec_pause_btn.setToolTip("Pause")
    self.rec_pause_btn.setEnabled(False)
    self.rec_pause_btn.clicked.connect(self._toggle_record_pause)
    rec_buttons.addWidget(self.rec_btn)
    rec_buttons.addWidget(self.rec_pause_btn)
    rec_body_lo.addLayout(rec_buttons)
    rec_lo.addWidget(rec_body)
    sb_lo.addWidget(rec_card)

    self._recorder["btn"] = self.rec_btn
    self._recorder["pause_btn"] = self.rec_pause_btn
    self._recorder["status_dot"] = self.rec_dot
    self._recorder["status_lbl"] = self.rec_status
    self._recorder["time_lbl"] = self.rec_time
    self._recorder["actions_lbl"] = self.rec_actions

    insp_card = panel_frame("inspector_card")
    insp_card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    insp_lo = QVBoxLayout(insp_card)
    insp_lo.setContentsMargins(12, 10, 12, 12)
    insp_lo.setSpacing(8)
    insp_body = QWidget(insp_card)
    insp_body.setObjectName("inspector_body")
    insp_body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    self.insp_body = insp_body
    insp_body_lo = QVBoxLayout(insp_body)
    insp_body_lo.setContentsMargins(0, 0, 0, 0)
    insp_body_lo.setSpacing(8)
    insp_lo.addLayout(section_header("INSPECTOR", "search", C["accent"], insp_body))

    selector_row = QHBoxLayout()
    selector_row.setSpacing(6)
    self.inspector_selector = compact_combo(["Select an action"])
    self.inspector_selector.setEnabled(False)
    self.inspector_selector.setIconSize(QSize(15, 15))
    self.inspector_selector.setStyleSheet(
        f"QComboBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 8px; "
        "font-size: 11px; }}"
        "QComboBox::drop-down { border: none; width: 20px; }"
    )
    selector_row.addWidget(self.inspector_selector, stretch=1)

    self.inspector_label = form_input("timeline label")
    self.inspector_label.setObjectName("inspector_label")
    self.inspector_label.setToolTip("Timeline label/name for the selected action")
    self.inspector_label.setEnabled(False)
    self.inspector_label.setFixedWidth(86)
    selector_row.addWidget(self.inspector_label)

    self.inspector_type_btn = QPushButton("ACTION")
    self.inspector_type_btn.setObjectName("inspector_type_btn")
    self.inspector_type_btn.setEnabled(False)
    self.inspector_type_btn.setFixedSize(54, 30)
    self.inspector_type_btn.setToolTip("Open the selected action dialog")
    self.inspector_type_btn.clicked.connect(lambda checked=False: self._open_active_dialog())
    self.inspector_type_btn.setStyleSheet(
        f"QPushButton#inspector_type_btn {{ color: {C['text']}; background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {C['bg_tertiary']}, stop:1 #020A13); "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 0; "
        "font-size: 10px; font-weight: 900; text-align: center; }}"
        f"QPushButton#inspector_type_btn:hover {{ border-color: {C['accent']}; color: #FFFFFF; }}"
        f"QPushButton#inspector_type_btn:disabled {{ color: {C['text_dark']}; border-color: {C['border']}; }}"
    )
    selector_row.addWidget(self.inspector_type_btn)

    # Backwards-compatible alias for older update code paths.
    self.inspector_type_badge = self.inspector_type_btn

    more_btn = QPushButton()
    more_btn.setObjectName("icon_btn")
    more_btn.setFixedSize(24, 30)
    more_btn.setIcon(icon("menu", 14, C["text_dim"]))
    selector_row.addWidget(more_btn)
    insp_body_lo.addLayout(selector_row)

    self.insp_empty = QLabel("Select an action to inspect")
    self.insp_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.insp_empty.setStyleSheet(
        f"color: {C['text_dark']}; font-size: 10px; padding: 6px; background: transparent;"
    )
    insp_body_lo.addWidget(self.insp_empty)

    self._insp_lo = QVBoxLayout()
    self._insp_lo.setContentsMargins(0, 0, 0, 0)
    self._insp_lo.setSpacing(6)

    self.insp_key = QWidget()
    ik_outer = QVBoxLayout(self.insp_key)
    ik_outer.setContentsMargins(0, 0, 0, 0)
    ik_outer.setSpacing(6)
    key_card, ik_lo = inspector_group("KEY ACTION", "key", C["key"])
    self.ik_key = form_input("key")
    self.ik_dur = form_input("duration")
    self.ik_hold = QCheckBox("Hold mode")
    self.ik_repeat = form_input("repeat", "1")
    self.ik_label = form_input("label")
    for label, widget in [
        ("Key", self.ik_key),
        ("Duration", self.ik_dur),
        ("Repeat", self.ik_repeat),
    ]:
        ik_lo.addWidget(form_label(label))
        ik_lo.addWidget(widget)
    self.ik_label.setVisible(False)
    ik_lo.addWidget(self.ik_hold)
    ik_outer.addWidget(key_card)

    self.insp_pause = QWidget()
    ip_outer = QVBoxLayout(self.insp_pause)
    ip_outer.setContentsMargins(0, 0, 0, 0)
    ip_outer.setSpacing(6)
    pause_card, ip_lo = inspector_group("DELAY ACTION", "delay", C["pause"])
    self.ip_dur = form_input("duration")
    self.ip_label = form_input("label")
    ip_lo.addWidget(form_label("Duration"))
    ip_lo.addWidget(self.ip_dur)
    self.ip_label.setVisible(False)
    ip_outer.addWidget(pause_card)

    self.insp_click = QWidget()
    ic_outer = QVBoxLayout(self.insp_click)
    ic_outer.setContentsMargins(0, 0, 0, 0)
    ic_outer.setSpacing(6)
    click_card, ic_lo = inspector_group("CLICK ACTION", "click", C["click"])
    self.ic_x = form_input("x")
    self.ic_y = form_input("y")
    xy = QHBoxLayout()
    xy.setSpacing(5)
    xy.addWidget(self.ic_x)
    xy.addWidget(self.ic_y)
    self.ic_btn = compact_combo(["left", "right", "middle"])
    self.ic_rand = form_input("rand")
    self.ic_repeat = form_input("repeat", "1")
    self.ic_label = form_input("label")
    ic_lo.addWidget(form_label("X, Y"))
    ic_lo.addLayout(xy)
    for label, widget in [
        ("Button", self.ic_btn),
        ("Randomness", self.ic_rand),
        ("Repeat", self.ic_repeat),
    ]:
        ic_lo.addWidget(form_label(label))
        ic_lo.addWidget(widget)
    self.ic_label.setVisible(False)
    ic_outer.addWidget(click_card)

    self.insp_image = QWidget()
    ii_lo = QVBoxLayout(self.insp_image)
    ii_lo.setContentsMargins(0, 0, 0, 0)
    ii_lo.setSpacing(7)

    image_card, image_card_lo = inspector_group("IMAGE", "image", C["image"], show_info=False)
    self.ii_image_card = image_card

    preview = QFrame()
    preview.setObjectName("image_inspector_preview")
    preview.setFixedHeight(150)
    preview.setStyleSheet(
        f"QFrame#image_inspector_preview {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #07182A, stop:1 #020A13); border: 1px solid {C['border']}; "
        "border-radius: 8px; }}"
    )
    preview_lo = QVBoxLayout(preview)
    preview_lo.setContentsMargins(7, 7, 7, 7)
    preview_lo.setSpacing(5)
    art = QFrame()
    art.setObjectName("image_preview_art")
    art.setStyleSheet(
        f"QFrame#image_preview_art {{ background-color: #071525; "
        f"border: 1px solid {C['border']}; border-radius: 7px; }}"
    )
    art_lo = QVBoxLayout(art)
    art_lo.setContentsMargins(0, 0, 0, 0)
    art_lo.setSpacing(0)
    art_icon = QLabel()
    art_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    art_icon.setPixmap(icon("image", 62, C["image"]).pixmap(62, 62))
    art_icon.setProperty("has_template", False)
    self.image_preview_label = art_icon
    art_lo.addWidget(art_icon, stretch=1)
    preview_lo.addWidget(art, stretch=1)

    preview_actions = QHBoxLayout()
    preview_actions.setContentsMargins(0, 0, 0, 0)
    preview_actions.setSpacing(6)
    change_btn = QPushButton("Browse")
    change_btn.setIcon(icon("image", 13, C["text_dim"]))
    change_btn.setIconSize(QSize(13, 13))
    change_btn.setFixedHeight(28)
    change_btn.setStyleSheet(
        f"QPushButton {{ color: {C['text']}; background-color: {C['bg_tertiary']}; "
        f"border: 1px solid {C['border']}; border-radius: 6px; padding: 3px 8px; "
        "font-size: 10px; font-weight: 750; text-align: left; }}"
        f"QPushButton:hover {{ border-color: {C['accent']}; }}"
    )
    change_btn.clicked.connect(self._browse_active_image_file)
    preview_actions.addWidget(change_btn)
    preview_actions.addStretch()
    for attr, name, tip, slot in (
        ("ii_zoom_btn", "search", "Zoom image", self._zoom_image_preview),
        ("ii_fit_btn", "move", "Fit preview", self._fit_image_preview),
        ("ii_capture_btn", "target", "Capture search region", self._capture_active_image_region),
    ):
        btn = QPushButton()
        btn.setObjectName("icon_btn")
        btn.setIcon(icon(name, 13, C["text_dim"]))
        btn.setToolTip(tip)
        btn.setFixedSize(28, 28)
        btn.clicked.connect(slot)
        setattr(self, attr, btn)
        preview_actions.addWidget(btn)
    preview_lo.addLayout(preview_actions)
    image_card_lo.addWidget(preview)
    ii_lo.addWidget(image_card)

    matching, matching_lo = inspector_group("MATCHING", "target", C["accent"], show_info=False)
    self.ii_matching_card = matching
    sim_row = QHBoxLayout()
    sim_row.setContentsMargins(0, 0, 0, 0)
    sim_lbl = form_label("Similarity")
    sim_row.addWidget(sim_lbl)
    sim_row.addStretch()
    self.ii_sim = inspector_value("0.85", 54)
    sim_row.addWidget(self.ii_sim)
    matching_lo.addLayout(sim_row)
    self.ii_sim_slider = QSlider(Qt.Orientation.Horizontal)
    self.ii_sim_slider.setRange(0, 100)
    self.ii_sim_slider.setValue(85)
    self.ii_sim_slider.setFixedHeight(18)
    self.ii_sim_slider.setStyleSheet(
        f"QSlider::groove:horizontal {{ height: 3px; background: {C['lane']}; border-radius: 2px; }}"
        f"QSlider::sub-page:horizontal {{ background: {C['accent']}; border-radius: 2px; }}"
        f"QSlider::handle:horizontal {{ background: {C['accent']}; width: 10px; height: 10px; "
        "border-radius: 5px; margin: -4px 0; }}"
    )
    self.ii_sim_slider.valueChanged.connect(lambda v: self.ii_sim.setText(f"{v / 100:.2f}"))
    matching_lo.addWidget(self.ii_sim_slider)
    scale_row = QHBoxLayout()
    scale_row.setContentsMargins(0, 0, 0, 0)
    left_scale = QLabel("0.00")
    right_scale = QLabel("1.00")
    for lbl in (left_scale, right_scale):
        lbl.setStyleSheet(f"color: {C['text_dark']}; font-size: 10px; background: transparent;")
    scale_row.addWidget(left_scale)
    scale_row.addStretch()
    scale_row.addWidget(right_scale)
    matching_lo.addLayout(scale_row)
    wait_row = QHBoxLayout()
    wait_row.setContentsMargins(0, 0, 0, 0)
    wait_row.addWidget(form_label("Wait timeout"))
    wait_row.addStretch()
    self.ii_wait = inspector_value("1000", 58)
    wait_row.addWidget(self.ii_wait)
    wait_ms = QLabel("ms")
    wait_ms.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; background: transparent;")
    wait_row.addWidget(wait_ms)
    matching_lo.addLayout(wait_row)
    ii_lo.addWidget(matching)

    retry, retry_lo = inspector_group("RETRY", "update", C["accent"], show_info=False)
    self.ii_retry_card = retry
    self.ii_retry_count = QSpinBox()
    self.ii_retry_count.setRange(1, 99)
    self.ii_retry_count.setFixedSize(76, 28)
    self.ii_retry_count.setStyleSheet(
        f"QSpinBox {{ background-color: {C['bg_secondary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 2px 8px; font-size: 11px; }}"
    )
    self.ii_retry_delay = inspector_value("250", 76)
    retry_row = QHBoxLayout()
    retry_row.setContentsMargins(0, 0, 0, 0)
    retry_row.setSpacing(8)
    retry_row.addWidget(form_label("Retry attempts / delay"))
    retry_lo.addLayout(retry_row)
    retry_values = QHBoxLayout()
    retry_values.setContentsMargins(0, 0, 0, 0)
    retry_values.setSpacing(7)
    slash = QLabel("/")
    slash.setAlignment(Qt.AlignmentFlag.AlignCenter)
    slash.setStyleSheet(f"color: {C['text']}; font-size: 12px; background: transparent;")
    retry_values.addWidget(self.ii_retry_count)
    retry_values.addWidget(slash)
    retry_values.addWidget(self.ii_retry_delay)
    retry_values.addWidget(form_label("ms"))
    retry_values.addStretch()
    retry_lo.addLayout(retry_values)
    ii_lo.addWidget(retry)

    on_fail, on_fail_lo = inspector_group("ON FAIL", "condition", C["accent"], show_info=False)
    self.ii_on_fail_card = on_fail
    on_fail_row = QHBoxLayout()
    on_fail_row.setContentsMargins(0, 0, 0, 0)
    on_fail_row.addWidget(form_label("On fail"))
    on_fail_row.addStretch()
    self.ii_fail_mode = compact_combo(["Default", "Continue", "Stop", "Jump", "Recovery Group"])
    self.ii_fail_mode.setFixedWidth(118)
    on_fail_row.addWidget(self.ii_fail_mode)
    on_fail_lo.addLayout(on_fail_row)
    ii_lo.addWidget(on_fail)

    fail_target, fail_target_lo = inspector_group("FAIL TARGET", "target", C["accent"], show_info=False)
    self.ii_fail_target_card = fail_target
    target_row = QHBoxLayout()
    target_row.setContentsMargins(0, 0, 0, 0)
    target_row.addWidget(form_label("Fail target"))
    target_row.addStretch()
    self.ii_fail_target = compact_combo()
    self.ii_fail_target.setFixedWidth(118)
    target_row.addWidget(self.ii_fail_target)
    fail_target_lo.addLayout(target_row)
    ii_lo.addWidget(fail_target)

    self.insp_group = QWidget()
    ig_outer = QVBoxLayout(self.insp_group)
    ig_outer.setContentsMargins(0, 0, 0, 0)
    ig_outer.setSpacing(6)
    group_card, ig_lo = inspector_group("GROUP", "folder", C["group"])
    self.ig_name = form_input("group name")
    self.ig_collapsed = QCheckBox("Collapsed")
    self.ig_recovery = QCheckBox("Recovery group")
    self.ig_meta = QLabel("0 actions - ~0.0s")
    self.ig_meta.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
    ig_lo.addWidget(form_label("Group name"))
    ig_lo.addWidget(self.ig_name)
    ig_lo.addWidget(self.ig_collapsed)
    ig_lo.addWidget(self.ig_recovery)
    ig_lo.addWidget(self.ig_meta)
    ig_outer.addWidget(group_card)

    self.insp_loop = QWidget()
    il_outer = QVBoxLayout(self.insp_loop)
    il_outer.setContentsMargins(0, 0, 0, 0)
    il_outer.setSpacing(6)
    loop_card, il_lo = inspector_group("LOOP", "loop", C["loop"])
    self.il_label = form_input("loop label")
    self.il_count = QSpinBox()
    self.il_count.setRange(2, 9999)
    self.il_count.setFixedHeight(30)
    self.il_target = compact_combo()
    self.il_label.setVisible(False)
    il_lo.addWidget(form_label("Repeat count"))
    il_lo.addWidget(self.il_count)
    il_lo.addWidget(form_label("Target"))
    il_lo.addWidget(self.il_target)
    il_outer.addWidget(loop_card)

    self.insp_condition = QWidget()
    ico_outer = QVBoxLayout(self.insp_condition)
    ico_outer.setContentsMargins(0, 0, 0, 0)
    ico_outer.setSpacing(6)
    condition_card, ico_lo = inspector_group("CONDITION", "condition", C["condition"])
    self.ico_label = form_input("condition label")
    self.ico_type = compact_combo(["pixel_color", "variable", "none"])
    self.ico_true = compact_combo()
    self.ico_false = compact_combo()
    self.ico_retry_count = QSpinBox()
    self.ico_retry_count.setRange(1, 99)
    self.ico_retry_count.setFixedHeight(30)
    self.ico_retry_delay = form_input("delay", "0.25")
    self.ico_fail_mode = compact_combo(["default", "continue", "stop", "jump", "recovery_group"])
    self.ico_fail_target = compact_combo()
    self.ico_rule = QLabel("Edit for pixel/variable values")
    self.ico_rule.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px;")
    ico_retry = QHBoxLayout()
    ico_retry.setSpacing(5)
    ico_retry.addWidget(self.ico_retry_count)
    ico_retry.addWidget(self.ico_retry_delay)
    self.ico_label.setVisible(False)
    for label, widget in [
        ("Type", self.ico_type),
        ("True target", self.ico_true),
        ("False target", self.ico_false),
    ]:
        ico_lo.addWidget(form_label(label))
        ico_lo.addWidget(widget)
    ico_lo.addWidget(form_label("Retry attempts / delay"))
    ico_lo.addLayout(ico_retry)
    ico_lo.addWidget(form_label("On false/fail"))
    ico_lo.addWidget(self.ico_fail_mode)
    ico_lo.addWidget(form_label("Fail target"))
    ico_lo.addWidget(self.ico_fail_target)
    ico_lo.addWidget(self.ico_rule)
    ico_outer.addWidget(condition_card)

    for pane in (
        self.insp_key,
        self.insp_pause,
        self.insp_click,
        self.insp_image,
        self.insp_group,
        self.insp_loop,
        self.insp_condition,
    ):
        pane.setVisible(False)
        self._insp_lo.addWidget(pane)
    insp_body_lo.addLayout(self._insp_lo)
    insp_lo.addWidget(insp_body)
    sb_lo.addWidget(insp_card, stretch=0)
    self._side_panel_bottom_restore_margin = 32
    self._side_panel_bottom_spacer = QWidget()
    self._side_panel_bottom_spacer.setObjectName("side_panel_bottom_spacer")
    self._side_panel_bottom_spacer.setMinimumHeight(0)
    self._side_panel_bottom_spacer.setMaximumHeight(16777215)
    self._side_panel_bottom_spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
    sb_lo.addWidget(self._side_panel_bottom_spacer, stretch=1)


    self._side_panel_collapsed = False
    self._side_panel_auto_collapsed = False
    self._side_panel_user_collapsed = False
    self._side_panel_locked = False
    self._bottom_panel_locked = False
    self._side_panel_expanded_width = 270
    self._side_panel_collapsed_width = 22
    self._side_panel_expand_restore_window_width = 920
    self._side_panel_auto_collapse_width = 910
    self._side_panel_auto_expand_width = 1040
    self._height_auto_playback_collapse = 1100
    self._height_auto_playback_expand = 1170
    # Side-panel auto-hide order while unlocked and resizing height:
    # FAIL TARGET -> ON FAIL -> RETRY -> MATCHING -> IMAGE -> RECORDER ->
    # ADD ACTION -> INSPECTOR.  The expand path restores the same set in
    # reverse order so the main Inspector body comes back before the larger
    # top-level sections and Image groups.
    self._height_auto_add_collapse = 1060
    self._height_auto_add_expand = 1130
    self._height_auto_recorder_collapse = 1020
    self._height_auto_recorder_expand = 1090
    self._height_auto_image_table_collapse = 960
    self._height_auto_image_table_expand = 1030
    self._height_auto_image_matching_collapse = 900
    self._height_auto_image_matching_expand = 970
    self._height_auto_image_retry_collapse = 840
    self._height_auto_image_retry_expand = 910
    self._height_auto_image_on_fail_collapse = 780
    self._height_auto_image_on_fail_expand = 850
    self._height_auto_image_fail_target_collapse = 720
    self._height_auto_image_fail_target_expand = 790
    self._height_auto_inspector_collapse = 650
    self._height_auto_inspector_expand = 720
    self.sidebar_frame = sidebar
    self.add_action_body = add_body
    self.recorder_body = rec_body
    self.insp_card = insp_card

    def _apply_side_panel_content_hug(reason=""):
        """Compatibility shim for older rebalance calls.

        The previous content-hug approach capped the whole sidebar height and
        caused expanded Inspector content to clip too early.  Keep the sidebar
        in its normal full-height layout; the responsive height policy now
        collapses only when the visible stack reaches the actual app bottom.
        """
        try:
            sidebar.setMinimumHeight(0)
            sidebar.setMaximumHeight(16777215)
            sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            spacer = getattr(self, "_side_panel_bottom_spacer", None)
            if spacer is not None:
                spacer.setMinimumHeight(0)
                spacer.setMaximumHeight(16777215)
                spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
                spacer.updateGeometry()
            layout = sidebar.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            sidebar.updateGeometry()
        except Exception:
            pass

    self._apply_side_panel_content_hug = _apply_side_panel_content_hug

    def _rebalance_side_panel_space(reason="", final=False):
        """Re-settle the side-panel layout after a section collapse/expand.

        Collapsing Add Action, Recorder, or Image Inspector sub-sections frees
        vertical space.  This helper restores the normal full-height sidebar
        layout, refreshes stale height clamps, and leaves collapse timing to the
        actual application bottom instead of clamping the whole side-panel frame.  It is
        layout-only and does not change the user's manual collapsed state, lock
        state, or auto-collapse thresholds.
        """
        try:
            if bool(getattr(self, "_side_panel_collapsed", False)):
                return

            controls = getattr(self, "_panel_collapse_controls", {})
            active_anims = getattr(self, "_collapse_animations", {})
            body_names = (
                "add_action_body",
                "recorder_body",
                "inspector_body",
                "inspector_group_image_body",
                "inspector_group_matching_body",
                "inspector_group_retry_body",
                "inspector_group_on_fail_body",
                "inspector_group_fail_target_body",
            )

            for body_name in body_names:
                ctl = controls.get(body_name)
                if not ctl:
                    continue
                body, caret = ctl
                if body is None or caret is None:
                    continue

                anim_key = body.objectName() or str(id(body))
                is_animating = anim_key in active_anims
                is_collapsed = bool(caret.property("collapsed"))
                parent = body.parentWidget()

                body.setMinimumHeight(0)
                if is_animating:
                    # Let the active height animation own maximumHeight; just
                    # push geometry updates through the parent/sidebar layouts.
                    body.updateGeometry()
                    if parent is not None:
                        parent.updateGeometry()
                    continue

                if is_collapsed:
                    body.setMaximumHeight(0)
                    body.setVisible(False)
                    if parent is not None:
                        parent.setMinimumHeight(0)
                        parent.setMaximumHeight(max(28, parent.minimumSizeHint().height() + 2))
                        parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                        parent.updateGeometry()
                else:
                    body.setVisible(True)
                    body.setMaximumHeight(16777215)
                    body.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                    if parent is not None:
                        parent.setMinimumHeight(0)
                        parent.setMaximumHeight(16777215)
                        if parent.objectName() == "inspector_card":
                            parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
                        else:
                            parent.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                        parent.updateGeometry()
                    body.updateGeometry()

            spacer = getattr(self, "_side_panel_bottom_spacer", None)
            if spacer is not None:
                spacer.setMinimumHeight(0)
                spacer.setMaximumHeight(16777215)
                spacer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
                spacer.updateGeometry()


            if hasattr(self, "_autosize_inspector_panel"):
                # Inspector content may have just gained/returned height.  Run
                # this after releases above so it clamps to the current natural
                # selected pane, not a stale collapsed value.
                try:
                    self._autosize_inspector_panel()
                except Exception:
                    pass

            layout = sidebar.layout()
            if layout is not None:
                layout.invalidate()
                layout.activate()
            hug = getattr(self, "_apply_side_panel_content_hug", None)
            if callable(hug):
                hug(reason=reason)
            sidebar.updateGeometry()
            central_widget = self.centralWidget()
            if central_widget is not None and central_widget.layout() is not None:
                central_widget.layout().invalidate()
                central_widget.layout().activate()
            # If an auto-collapse animation finished and the visible stack is
            # still pressing into the application bottom, let the resize policy
            # continue to the next section in the requested collapse order.
            if str(reason).endswith(".finished"):
                responsive_height = getattr(self, "_update_responsive_height_panels", None)
                if callable(responsive_height):
                    QTimer.singleShot(0, responsive_height)
        except Exception:
            pass

    self._rebalance_side_panel_space = _rebalance_side_panel_space
    try:
        QTimer.singleShot(0, lambda: self._apply_side_panel_content_hug(reason="initial"))
        QTimer.singleShot(120, lambda: self._apply_side_panel_content_hug(reason="initial.settle"))
    except Exception:
        pass

    def _set_side_panel_collapsed(collapsed, auto=False):
        collapsed = bool(collapsed)
        auto = bool(auto)
        if auto:
            self._side_panel_auto_collapsed = collapsed
        else:
            self._side_panel_user_collapsed = collapsed
            self._side_panel_auto_collapsed = False
        self._side_panel_collapsed = collapsed
        target_width = self._side_panel_collapsed_width if collapsed else self._side_panel_expanded_width
        sidebar.setFixedWidth(target_width)
        sidebar.setMinimumWidth(target_width)
        sidebar.setMaximumWidth(target_width)
        if collapsed:
            sidebar.setMinimumHeight(0)
            sidebar.setMaximumHeight(16777215)
            sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            sidebar.setMinimumHeight(0)
            sidebar.setMaximumHeight(16777215)
            sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        margin = 0 if collapsed else 10
        sb_lo.setContentsMargins(margin, 14, margin, 10)
        brand_box.setVisible(not collapsed)
        self.side_panel_lock_btn.setVisible(not collapsed)
        add_card.setVisible(not collapsed)
        rec_card.setVisible(not collapsed)
        insp_card.setVisible(not collapsed)
        self.sidebar_collapse_btn.setText(">" if collapsed else "<")
        self.sidebar_collapse_btn.setToolTip("Expand side panel" if collapsed else "Collapse side panel")
        sb_lo.setSpacing(0 if collapsed else 8)
        if collapsed and not bool(getattr(self, "_side_panel_locked", False)) and not bool(getattr(self, "_bottom_panel_locked", False)):
            if hasattr(self, "_auto_grow_for_collapsed_side_panel"):
                self._auto_grow_for_collapsed_side_panel()
        elif not collapsed:
            try:
                restore_w = int(getattr(self, "_side_panel_expand_restore_window_width", 920))
                if int(self.width()) < restore_w:
                    # Expanding the side panel from the narrow rail should return
                    # the whole window to the compact usable width instead of
                    # stealing space from the center/top toolbar. This is a
                    # one-shot resize only; normal manual resizing remains free.
                    self.resize(restore_w, self.height())
            except Exception:
                pass
        if hasattr(self, "_apply_panel_size_locks"):
            self._apply_panel_size_locks()
        if hasattr(self, "_update_toolbar_containment"):
            try:
                QTimer.singleShot(0, self._update_toolbar_containment)
            except Exception:
                pass

    self._set_side_panel_collapsed = _set_side_panel_collapsed
    self.sidebar_collapse_btn.clicked.connect(
        lambda checked=False: _set_side_panel_collapsed(
            not bool(getattr(self, "_side_panel_collapsed", False)),
            auto=False,
        )
    )
    main_lo.addWidget(sidebar)

    # Main workspace.
    content = QFrame()
    content.setObjectName("mf3_content")
    content.setStyleSheet(f"QFrame#mf3_content {{ background-color: {C['bg']}; border: none; }}")
    content_lo = QVBoxLayout(content)
    content_lo.setContentsMargins(0, 0, 0, 0)
    content_lo.setSpacing(0)

    header_shell = QFrame()
    header_shell.setFixedHeight(62)
    header_shell.setObjectName("header_shell")
    header_shell.setStyleSheet(
        "QFrame#header_shell { background: transparent; border: none; }"
    )
    shell_lo = QVBoxLayout(header_shell)
    shell_lo.setContentsMargins(8, 6, 8, 4)
    shell_lo.setSpacing(0)

    header_dock = QFrame()
    self.header_dock = header_dock
    header_dock.setObjectName("header_dock")
    header_dock.setStyleSheet(
        f"QFrame#header_dock {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #020A13, stop:0.55 #03101E, stop:1 #000309); "
        f"border: 1px solid {C['border']}; border-radius: 12px; }}"
    )
    header_dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    header_dock.setMinimumWidth(0)
    dock_lo = QHBoxLayout(header_dock)
    dock_lo.setContentsMargins(7, 5, 9, 5)
    dock_lo.setSpacing(4)

    self.toolbar_separators = []

    def header_separator():
        sep = QFrame()
        sep.setObjectName("toolbar_separator")
        sep.setFixedSize(1, 28)
        sep.setStyleSheet(
            "QFrame#toolbar_separator { background-color: #0E2A40; "
            "border: none; border-radius: 1px; }"
        )
        self.toolbar_separators.append(sep)
        return sep

    def header_icon_button(obj, icon_name, color, tooltip, slot=None, width=38, grouped=False, height=38):
        btn = QPushButton()
        btn.setObjectName(obj)
        btn.setIcon(icon(icon_name, 18, color))
        btn.setIconSize(QSize(18, 18))
        btn.setToolTip(tooltip)
        btn.setFixedSize(width, height)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        radius = 9 if not grouped else 8
        border_color = "#15354D" if not grouped else "transparent"
        bg = "qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #07172A, stop:1 #020A13)" if not grouped else "transparent"
        btn.setStyleSheet(
            f"QPushButton#{obj} {{ background: {bg}; color: {color}; "
            f"border: 1px solid {border_color}; border-radius: {radius}px; padding: 0; }}"
            f"QPushButton#{obj}:hover {{ border-color: {color}; background: {C['bg_hover']}; }}"
            f"QPushButton#{obj}:pressed {{ border-color: {color}; background: {C['bg_pressed']}; }}"
            f"QPushButton#{obj}:checked {{ border-color: {color}; background: {C['accent_glow']}; }}"
            f"QPushButton#{obj}::menu-indicator {{ image: none; width: 0px; }}"
        )
        if slot is not None:
            btn.clicked.connect(slot)
        return btn

    tools = QFrame()
    self.toolbar_tools_group = tools
    tools.setObjectName("toolbar_group")
    tools.setFixedHeight(38)
    tools.setStyleSheet(
        f"QFrame#toolbar_group {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #07172A, stop:0.58 {C['bg_tertiary']}, stop:1 #020A13); "
        f"border: 1px solid {C['border']}; border-radius: 12px; }}"
    )
    tools_lo = QHBoxLayout(tools)
    tools_lo.setContentsMargins(2, 2, 2, 2)
    tools_lo.setSpacing(1)
    self.editor_mode_btn = header_icon_button("editor_mode_btn", "magic", C["accent"], "Open macro editor mode", self.open_macro_editor, width=35, height=34, grouped=True)
    self.preflight_btn = header_icon_button("preflight_btn", "check", C["success"], "Run macro health / pre-flight checker", self.open_preflight_report, width=35, height=34, grouped=True)
    self.runtime_log_btn = header_icon_button("runtime_log_btn", "eye", C["pause_cyan"], "Show / hide live runtime log", self.toggle_runtime_log_panel, width=35, height=34, grouped=True)
    self.runtime_log_btn.setCheckable(True)
    self.mode_filter_btn = header_icon_button("mode_filter_btn", "menu", C["accent"], "Mode filters: All actions", None, width=41, height=34, grouped=True)
    self.compact_view_btn = self.mode_filter_btn
    for btn in (self.editor_mode_btn, self.preflight_btn, self.runtime_log_btn, self.mode_filter_btn):
        tools_lo.addWidget(btn)
    dock_lo.addWidget(tools)

    dock_lo.addSpacing(4)
    dock_lo.addWidget(header_separator())
    dock_lo.addSpacing(4)

    self.profile_btn = QPushButton("Default Profile  ▾")
    self.profile_btn.setObjectName("profile_switcher")
    self.profile_btn.setIcon(icon("folder", 16, C["accent"]))
    self.profile_btn.setIconSize(QSize(16, 16))
    self.profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.profile_btn.setToolTip("Switch profile")
    self.profile_btn.setFixedSize(164, 38)
    self._toolbar_profile_full_width = 164
    self._toolbar_profile_compact_width = 132
    self._toolbar_profile_tiny_width = 116
    self.profile_btn.clicked.connect(self._show_profile_menu)
    self.profile_btn.setStyleSheet(
        f"QPushButton#profile_switcher {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 #07172A, stop:1 {C['bg_card']}); color: {C['text']}; "
        f"border: 1px solid #15354D; border-radius: 11px; padding: 0 12px; "
        "font-size: 12px; font-weight: 800; text-align: left; }}"
        f"QPushButton#profile_switcher:hover {{ border-color: {C['accent']}; background: {C['bg_hover']}; }}"
        f"QPushButton#profile_switcher:pressed {{ background: {C['bg_pressed']}; }}"
    )
    dock_lo.addWidget(self.profile_btn)

    dock_lo.addSpacing(4)
    dock_lo.addWidget(header_separator())
    dock_lo.addSpacing(4)

    self.search_top_btn = header_icon_button("search_top_btn", "search", C["text_dim"], "Search timeline actions", None, width=38)
    dock_lo.addWidget(self.search_top_btn)

    self.update_top_btn = header_icon_button("update_top_btn", "update", C["accent"], "Check for updates", self._check_update_manual, width=38)
    dock_lo.addWidget(self.update_top_btn)

    dock_lo.addStretch(1)

    status_pill = QFrame()
    status_pill.setObjectName("status_pill")
    status_pill.setMinimumWidth(260)
    # Top-panel containment pass: trim the large status pill by 40px
    # while keeping its existing minimum readable width.
    status_pill.setMaximumWidth(390)
    status_pill.setFixedHeight(38)
    status_pill.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    status_pill.setAutoFillBackground(False)
    status_pill.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    status_pill.setStyleSheet(
        f"QFrame#status_pill {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1, "
        f"stop:0 #07172A, stop:0.6 {C['bg_tertiary']}, stop:1 #020A13); "
        f"border: 1px solid {C['border']}; border-radius: 12px; }}"
        "QFrame#status_pill QLabel { background: transparent; border: none; }"
        "QFrame#status_pill QWidget { background: transparent; border: none; }"
    )
    self.status_pill = status_pill
    sp_lo = QHBoxLayout(status_pill)
    sp_lo.setContentsMargins(11, 0, 11, 0)
    sp_lo.setSpacing(7)
    self.status_dot = StatusDot()
    self.status_dot.set_color(C["success"])
    self.status_dot.setFixedSize(12, 12)
    self.status_dot.setAutoFillBackground(False)
    self.status_dot.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    sp_lo.addWidget(self.status_dot)
    self.status_icon = QLabel()
    self.status_icon.setPixmap(icon("check", 15, C["success"]).pixmap(15, 15))
    self.status_icon.setFixedSize(15, 15)
    self.status_icon.setScaledContents(True)
    self.status_icon.setAutoFillBackground(False)
    self.status_icon.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    self.status_icon.setStyleSheet("background: transparent; border: none;")
    self.status_icon.setVisible(False)
    sp_lo.addWidget(self.status_icon)
    self.status_text = QLabel("Ready")
    self.status_text.setObjectName("status_text")
    self.status_text.setAutoFillBackground(False)
    self.status_text.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    self.status_text.setStyleSheet(f"QLabel#status_text {{ background: transparent; border: none; color: {C['text']}; font-size: 11px; font-weight: 850; }}")
    self.status_text.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    self.status_text.setWordWrap(False)
    self.status_text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    sp_lo.addWidget(self.status_text, stretch=1)

    # Keep the autosave label object alive for existing save-session logic and
    # tests, but remove its visible chip from the redesigned top toolbar.
    self.autosave_label = QLabel("Saved")
    self.autosave_label.setObjectName("autosave_label")
    self.autosave_label.setStyleSheet(
        f"QLabel#autosave_label {{ color: {C['success']}; font-size: 10px; "
        f"background-color: {C['bg_card']}; border: 1px solid {C['border']}; "
        "border-radius: 7px; padding: 2px 6px; }}"
    )
    self.autosave_label.setToolTip("Profile autosave state")
    self.autosave_label.setVisible(False)
    dock_lo.addWidget(status_pill, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    try:
        QTimer.singleShot(0, self._update_toolbar_containment)
    except Exception:
        pass

    toolbar_menu_style = (
        f"QMenu {{ background-color: #020A13; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 10px; padding: 6px; }}"
        f"QMenu::item {{ padding: 7px 24px 7px 12px; border-radius: 7px; }}"
        f"QMenu::item:selected {{ background-color: {C['bg_hover']}; color: {C['accent']}; }}"
        f"QMenu::item:checked {{ background-color: {C['accent_glow']}; color: {C['accent_hover']}; }}"
        f"QMenu::separator {{ height: 1px; background: {C['border']}; margin: 5px 4px; }}"
    )

    self.mode_filter_menu = QMenu(self)
    self.mode_filter_menu.setObjectName("mode_filter_menu")
    self.mode_filter_menu.setStyleSheet(toolbar_menu_style)
    self._current_timeline_filter = "All actions"
    self._mode_filter_actions = {}

    def _apply_timeline_filter(label, slug):
        self._current_timeline_filter = label
        for action_slug, action in getattr(self, "_mode_filter_actions", {}).items():
            action.setChecked(action_slug == slug)
        try:
            self.timeline.set_quick_filter(slug)
        except Exception:
            pass
        self.mode_filter_btn.setToolTip(f"Mode filters: {label}")
        try:
            self.status(f"Filter: {label}")
        except Exception:
            pass

    filter_items = [
        ("All actions", "all"), None,
        ("Key actions", "key"),
        ("Click actions", "click"),
        ("Delay actions", "delay"),
        ("Image actions", "image"),
        ("Condition actions", "condition"),
        ("Loop actions", "loop"),
        ("Group headers", "group"), None,
        ("Selected only", "selected"),
        ("Warnings / missing data", "warnings"),
        ("Disabled actions", "disabled"),
        ("Current group", "current group"),
    ]
    for item in filter_items:
        if item is None:
            self.mode_filter_menu.addSeparator()
            continue
        label, slug = item
        act = self.mode_filter_menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(slug == "all")
        self._mode_filter_actions[slug] = act
        act.triggered.connect(lambda checked=False, label=label, slug=slug: _apply_timeline_filter(label, slug))

    def _show_mode_filter_menu():
        self.mode_filter_menu.popup(self.mode_filter_btn.mapToGlobal(self.mode_filter_btn.rect().bottomLeft()))

    self.mode_filter_btn.clicked.connect(_show_mode_filter_menu)

    self.tl_search_menu = QMenu(self)
    self.tl_search_menu.setObjectName("timeline_search_menu")
    self.tl_search_menu.setStyleSheet(toolbar_menu_style)
    search_action = QWidgetAction(self.tl_search_menu)
    search_wrap = QFrame()
    search_wrap.setObjectName("timeline_search_wrap")
    search_wrap.setStyleSheet(
        "QFrame#timeline_search_wrap { background: transparent; border: none; }"
        f"QLabel#timeline_search_results {{ color: {C['text_dim']}; font-size: 10px; font-weight: 750; }}"
        f"QPushButton#timeline_search_mini {{ background: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 7px; padding: 4px 9px; font-size: 10px; font-weight: 800; }}"
        f"QPushButton#timeline_search_mini:hover {{ border-color: {C['accent']}; color: {C['accent_hover']}; background: {C['bg_hover']}; }}"
    )
    search_lo = QVBoxLayout(search_wrap)
    search_lo.setContentsMargins(6, 5, 6, 6)
    search_lo.setSpacing(6)
    self.tl_search = QLineEdit()
    self.tl_search.setPlaceholderText("Search actions...")
    self.tl_search.setClearButtonEnabled(True)
    self.tl_search.setFixedSize(290, 34)
    self.tl_search.addAction(icon("search", 15, C["text_dim"]), QLineEdit.ActionPosition.LeadingPosition)
    self.tl_search.setStyleSheet(
        f"QLineEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 9px; padding: 5px 10px; "
        "font-size: 12px; font-weight: 650; }}"
        f"QLineEdit:focus {{ border-color: {C['accent']}; background-color: {C['bg_hover']}; }}"
    )
    search_lo.addWidget(self.tl_search)
    search_controls = QHBoxLayout()
    search_controls.setContentsMargins(0, 0, 0, 0)
    search_controls.setSpacing(5)
    self.tl_search_result_label = QLabel("Type to search")
    self.tl_search_result_label.setObjectName("timeline_search_results")
    search_controls.addWidget(self.tl_search_result_label, stretch=1)

    def _mini_search_btn(text, tip):
        btn = QPushButton(text)
        btn.setObjectName("timeline_search_mini")
        btn.setFixedHeight(26)
        btn.setToolTip(tip)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    self.tl_search_prev_btn = _mini_search_btn("Prev", "Previous search result")
    self.tl_search_next_btn = _mini_search_btn("Next", "Next search result")
    self.tl_search_clear_btn = _mini_search_btn("Clear", "Clear search")
    search_controls.addWidget(self.tl_search_prev_btn)
    search_controls.addWidget(self.tl_search_next_btn)
    search_controls.addWidget(self.tl_search_clear_btn)
    search_lo.addLayout(search_controls)
    search_action.setDefaultWidget(search_wrap)
    self.tl_search_menu.addAction(search_action)

    def _refresh_timeline_search_feedback(push_status=False):
        text = self.tl_search.text().strip() if hasattr(self, "tl_search") else ""
        if not text:
            self.tl_search_result_label.setText("Type to search")
            return
        try:
            matches = self.timeline.search_match_rows()
        except Exception:
            matches = []
        count = len(matches)
        self.tl_search_result_label.setText("No matches" if count == 0 else f"{count} match" + ("" if count == 1 else "es"))
        if push_status:
            try:
                self.status("Search: no matches" if count == 0 else f"Search: {count} match" + ("" if count == 1 else "es"))
            except Exception:
                pass

    def _timeline_search_changed(text):
        try:
            self.timeline.set_search(text)
        except Exception:
            pass
        _refresh_timeline_search_feedback(push_status=bool(str(text).strip()))

    def _jump_timeline_search(direction):
        try:
            row = self.timeline.jump_to_search_match(direction)
        except Exception:
            row = -1
        _refresh_timeline_search_feedback(push_status=True)
        if row >= 0:
            try:
                self.status(f"Search result: action {row + 1}")
            except Exception:
                pass

    def _clear_timeline_search():
        self.tl_search.clear()
        try:
            self.timeline.set_search("")
            self.timeline.viewport().update()
        except Exception:
            pass
        _refresh_timeline_search_feedback(push_status=False)
        try:
            self.status("Search cleared")
        except Exception:
            pass

    self.tl_search.textChanged.connect(_timeline_search_changed)
    self.tl_search_prev_btn.clicked.connect(lambda checked=False: _jump_timeline_search(-1))
    self.tl_search_next_btn.clicked.connect(lambda checked=False: _jump_timeline_search(1))
    self.tl_search_clear_btn.clicked.connect(lambda checked=False: _clear_timeline_search())

    def _show_timeline_search_popup():
        self.tl_search_menu.popup(self.search_top_btn.mapToGlobal(self.search_top_btn.rect().bottomLeft()))
        QTimer.singleShot(0, self.tl_search.setFocus)
        QTimer.singleShot(0, self.tl_search.selectAll)
        QTimer.singleShot(0, lambda: _refresh_timeline_search_feedback(push_status=False))

    self._show_timeline_search_popup = _show_timeline_search_popup
    self.search_top_btn.clicked.connect(_show_timeline_search_popup)

    self.macro_summary = QLabel("0 actions - 0 image checks - ~0s")
    self.macro_summary.setVisible(False)
    shell_lo.addWidget(header_dock)
    content_lo.addWidget(header_shell)

    self.timeline = TimelineView(model=self.action_model)
    content_lo.addWidget(self.timeline, stretch=1)

    self.runtime_log_panel = QFrame()
    self.runtime_log_panel.setObjectName("runtime_log_panel")
    self.runtime_log_panel.setFixedHeight(132)
    self.runtime_log_panel.setVisible(False)
    self.runtime_log_panel.setStyleSheet(
        f"QFrame#runtime_log_panel {{ background-color: {C['bg_card']}; "
        f"border-top: 1px solid {C['border']}; border-bottom: 1px solid {C['border']}; }}"
    )
    rlp_lo = QVBoxLayout(self.runtime_log_panel)
    rlp_lo.setContentsMargins(10, 6, 10, 8)
    rlp_lo.setSpacing(5)
    rlp_head = QHBoxLayout()
    rlp_title = QLabel("LIVE RUNTIME LOG")
    rlp_title.setStyleSheet(f"color: {C['text_dim']}; font-size: 10px; letter-spacing: 1px;")
    rlp_head.addWidget(rlp_title)
    rlp_head.addStretch()
    clear_log_btn = QPushButton("Clear")
    clear_log_btn.setFixedSize(54, 24)
    clear_log_btn.clicked.connect(self.clear_runtime_log_panel)
    hide_log_btn = QPushButton("Hide")
    hide_log_btn.setFixedSize(50, 24)
    hide_log_btn.clicked.connect(lambda: self.toggle_runtime_log_panel(False))
    rlp_head.addWidget(clear_log_btn)
    rlp_head.addWidget(hide_log_btn)
    rlp_lo.addLayout(rlp_head)
    self.runtime_log_edit = QPlainTextEdit()
    self.runtime_log_edit.setReadOnly(True)
    self.runtime_log_edit.setMaximumBlockCount(600)
    self.runtime_log_edit.setStyleSheet(
        f"QPlainTextEdit {{ background-color: {C['bg_tertiary']}; color: {C['text']}; "
        f"border: 1px solid {C['border']}; border-radius: 8px; padding: 6px; "
        "font-family: Consolas, monospace; font-size: 10px; }}"
    )
    rlp_lo.addWidget(self.runtime_log_edit, stretch=1)
    content_lo.addWidget(self.runtime_log_panel)

    self.playback_panel = self._make_playback_panel()
    content_lo.addWidget(self.playback_panel)
    main_lo.addWidget(content, stretch=1)
