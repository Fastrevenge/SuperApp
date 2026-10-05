"""UI утилиты «Конвертер валют»."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.currency_tracker.data_provider import CBRProvider
from modules.currency_tracker.service import CurrencyService

logger = logging.getLogger(__name__)


class ConverterWidget(QWidget):
    """Простой конвертер: сумма × кросс-курс = результат."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.service = CurrencyService(CBRProvider())
        self._build_ui()
        self._refresh_rate()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Конвертер валют")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#111827;")
        root.addWidget(title)

        subtitle = QLabel("Курсы по данным ЦБ РФ на последний рабочий день.")
        subtitle.setStyleSheet("color:#6b7280; font-size:13px;")
        root.addWidget(subtitle)

        # --- Карточка конвертера ---
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background:white; border-radius:8px; padding:16px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(12)

        # Сумма
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Сумма:"))
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 1_000_000_000)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(1000.0)
        self.amount_input.setGroupSeparatorShown(True)
        self.amount_input.valueChanged.connect(self._refresh_rate)
        row1.addWidget(self.amount_input, 1)
        card_layout.addLayout(row1)

        # Из чего
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Из:"))
        self.from_combo = QComboBox()
        self.from_combo.addItems(self.service.available_bases())
        self.from_combo.setCurrentText("USD")
        self.from_combo.currentTextChanged.connect(self._refresh_rate)
        row2.addWidget(self.from_combo, 1)

        # Кнопка «инвертировать»
        self.btn_swap = QPushButton("⇄")
        self.btn_swap.setToolTip("Поменять валюты местами")
        self.btn_swap.setFixedWidth(40)
        self.btn_swap.clicked.connect(self._swap)
        row2.addWidget(self.btn_swap)

        row2.addWidget(QLabel("В:"))
        self.to_combo = QComboBox()
        self.to_combo.addItems(self.service.available_bases())
        self.to_combo.setCurrentText("RUB")
        self.to_combo.currentTextChanged.connect(self._refresh_rate)
        row2.addWidget(self.to_combo, 1)

        card_layout.addLayout(row2)

        # Результат
        self.result_label = QLabel("—")
        self.result_label.setStyleSheet(
            "font-size:28px; font-weight:800; color:#1d4ed8; "
            "padding:12px; background:#eff6ff; border-radius:8px;"
        )
        self.result_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.result_label)

        # Пояснение
        self.rate_label = QLabel("Курс: —")
        self.rate_label.setStyleSheet(
            "font-size:13px; color:#6b7280; font-family:Consolas, monospace;"
        )
        self.rate_label.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.rate_label)

        # Кнопка обновления
        self.btn_refresh = QPushButton("Обновить курсы")
        self.btn_refresh.clicked.connect(self._force_refresh)
        card_layout.addWidget(self.btn_refresh)

        root.addWidget(card)
        root.addStretch(1)

    # ---------- Логика ----------

    def _swap(self) -> None:
        a = self.from_combo.currentText()
        b = self.to_combo.currentText()
        self.from_combo.blockSignals(True)
        self.to_combo.blockSignals(True)
        self.from_combo.setCurrentText(b)
        self.to_combo.setCurrentText(a)
        self.from_combo.blockSignals(False)
        self.to_combo.blockSignals(False)
        self._refresh_rate()

    def _force_refresh(self) -> None:
        self.service.clear_cache()
        self._refresh_rate()

    def _refresh_rate(self) -> None:
        frm = self.from_combo.currentText()
        to = self.to_combo.currentText()
        amount = self.amount_input.value()

        if frm == to:
            self.result_label.setText("{:,.2f} {}".format(amount, to))
            self.rate_label.setText("Курс: 1.0000 (одинаковые валюты)")
            return

        rate = self._get_rate(frm, to)
        if rate is None:
            self.result_label.setText("—")
            self.rate_label.setText("Курс: нет данных")
            return

        result = amount * rate
        self.result_label.setText("{:,.2f} {}".format(result, to))
        self.rate_label.setText(
            "Курс: 1 {} = {:.6f} {}  (ЦБ РФ)".format(frm, rate, to)
        )

    def _get_rate(self, frm: str, to: str) -> Optional[float]:
        """Курс frm → to через рубль.

        RUB → X = 1 / (X/RUB)
        X → RUB = X/RUB
        X → Y = (X/RUB) / (Y/RUB)
        """
        try:
            if frm == "RUB" and to == "RUB":
                return 1.0

            rate_from = self._get_to_rub(frm)
            rate_to = self._get_to_rub(to)

            if rate_from is None or rate_to is None:
                return None
            if rate_to == 0:
                return None
            return rate_from / rate_to
        except Exception as exc:
            logger.exception("Ошибка получения курса %s/%s: %s", frm, to, exc)
            return None

    def _get_to_rub(self, currency: str) -> Optional[float]:
        """Сколько рублей стоит 1 единица валюты."""
        if currency == "RUB":
            return 1.0
        rate = self.service.get_last_cbr_rate(currency)
        if rate is None:
            return None
        _, value = rate
        return value

    # ---------- Публичные хуки ----------

    def refresh(self) -> None:
        """Вызывается по F5."""
        self._force_refresh()