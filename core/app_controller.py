"""Главный контроллер приложения."""
from __future__ import annotations

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import APP_NAME, APP_VERSION, NAV_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH
from core.module_registry import ModuleRegistry

logger = logging.getLogger(__name__)


class AppController(QMainWindow):
    """Главное окно SuperApp с боковой навигацией и стеком утилит."""

    def __init__(self) -> None:
        super().__init__()
        self.registry = ModuleRegistry()

        self.setWindowTitle("{} v{}".format(APP_NAME, APP_VERSION))
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self._build_ui()
        self._build_menu()
        self._register_modules()
        self._populate_navigation()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QLabel("  \U0001F680 {}".format(APP_NAME))
        header.setFixedHeight(48)
        header.setStyleSheet(
            "background:#1f2937; color:#f9fafb; font-size:16px; font-weight:600;"
        )
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        self.nav_list = QListWidget()
        self.nav_list.setFixedWidth(NAV_WIDTH)
        self.nav_list.setStyleSheet(
            "QListWidget { background:#111827; color:#e5e7eb; border:none;"
            " font-size:14px; padding-top:8px; }"
            "QListWidget::item { padding:12px 16px; }"
            "QListWidget::item:selected { background:#2563eb; color:white; }"
            "QListWidget::item:hover { background:#1f2937; }"
        )
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background:#f3f4f6;")

        body.addWidget(self.nav_list)
        body.addWidget(self.stack, 1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        root.addWidget(body_widget, 1)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        # --- Файл ---
        menu = self.menuBar().addMenu("&Файл")

        act_refresh = QAction("&Обновить", self)
        act_refresh.setShortcut("F5")
        act_refresh.triggered.connect(self._refresh_current)

        act_quit = QAction("&Выход", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)

        menu.addAction(act_refresh)
        menu.addSeparator()
        menu.addAction(act_quit)

        # --- Навигация ---
        nav_menu = self.menuBar().addMenu("&Навигация")

        act_home = QAction("&Домой (Курсы валют)", self)
        act_home.setShortcut("Ctrl+H")
        act_home.triggered.connect(lambda: self.nav_list.setCurrentRow(0))
        nav_menu.addAction(act_home)

        nav_menu.addSeparator()

        # Alt+1..Alt+9 — переход к модулю по номеру
        for i in range(9):
            act = QAction("Модуль &{}".format(i + 1), self)
            act.setShortcut("Alt+{}".format(i + 1))
            act.triggered.connect(
                lambda checked=False, idx=i: self._goto_module(idx)
            )
            nav_menu.addAction(act)

        # --- Справка ---
        help_menu = self.menuBar().addMenu("&Справка")
        act_about = QAction("&О программе", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    # ---------- Модули ----------

    def _register_modules(self) -> None:
        """Регистрирует все утилиты SuperApp."""

        # --- Утилита 1: Курсы валют ---
        from modules.currency_tracker.ui import CurrencyTrackerWidget
        from modules.currency_tracker.data_provider import CBRProvider
        from modules.currency_tracker.service import CurrencyService

        def make_currency_widget() -> QWidget:
            provider = CBRProvider()
            service = CurrencyService(provider)
            return CurrencyTrackerWidget(service)

        self.registry.register(
            key="currency_tracker",
            title="Курсы валют",
            icon="\U0001F4B0",
            factory=make_currency_widget,
        )

        # --- Утилита 2: Конвертер ---
        from modules.converter.ui import ConverterWidget

        self.registry.register(
            key="converter",
            title="Конвертер",
            icon="\U0001F504",
            factory=lambda: ConverterWidget(),
        )

        # --- Утилита 3: Аналитика ---
        from modules.analytics.ui import AnalyticsWidget

        self.registry.register(
            key="analytics",
            title="Аналитика",
            icon="\U0001F4C8",
            factory=lambda: AnalyticsWidget(),
        )

    def _populate_navigation(self) -> None:
        """Создаёт пункты меню. Реальные виджеты подставляются лениво."""
        self.nav_list.clear()
        for module in self.registry.all():
            item = QListWidgetItem("{}  {}".format(module.icon, module.title))
            item.setData(Qt.UserRole, module.key)
            self.nav_list.addItem(item)
            # Пустая ячейка — заполнится при первом заходе
            self.stack.addWidget(QWidget())

        if self.nav_list.count():
            self.nav_list.setCurrentRow(0)

    # ---------- События ----------

    def _on_nav_changed(self, row: int) -> None:
        """Показывает виджет модуля. Создаётся один раз, потом переиспользуется."""
        if row < 0:
            return

        module = self.registry.all()[row]
        widget = self.registry.get_widget(module.key)

        current = self.stack.widget(row)
        if current is not widget:
            if current is not None:
                self.stack.removeWidget(current)
                current.deleteLater()
            self.stack.insertWidget(row, widget)

        self.stack.setCurrentIndex(row)

    def _goto_module(self, index: int) -> None:
        """Переход к модулю по индексу, если он существует."""
        if 0 <= index < self.nav_list.count():
            self.nav_list.setCurrentRow(index)

    def _refresh_current(self) -> None:
        widget = self.stack.currentWidget()
        if hasattr(widget, "refresh"):
            widget.refresh()

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "О программе",
            "{} v{}\n\nМодульное десктопное приложение.\n\n"
            "Утилиты:\n"
            "  • Курсы валют — ЦБ РФ и MOEX\n"
            "  • Конвертер — кросс-курсы ЦБ РФ\n"
            "  • Аналитика — статистика и прогноз".format(APP_NAME, APP_VERSION),
        )