"""UI утилиты Currency Tracker (PyQt5 + pyqtgraph)."""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import pyqtgraph as pg
from PyQt5.QtCore import QDate, Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.currency_tracker.export import export_plot_png
from modules.currency_tracker.service import CurrencyService

logger = logging.getLogger(__name__)

LINE_COLORS = ["#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed"]
LIVE_REFRESH_MS = 60_000
MAX_CURRENCIES = 5

PRESETS = [
    ("USD/EUR", "USD", "EUR"),
    ("EUR/USD", "EUR", "USD"),
    ("USD/CNY", "USD", "CNY"),
    ("EUR/GBP", "EUR", "GBP"),
    ("USD/RUB", "USD", "RUB"),
    ("EUR/RUB", "EUR", "RUB"),
]


class CurrencyTrackerWidget(QWidget):
    def __init__(self, service: CurrencyService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.service = service
        self._last_series: Dict[str, List] = {}

        self._build_ui()
        self._load_data()
        self._setup_live_timer()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Курсы валют")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#111827;")
        root.addWidget(title)

        # --- Плашка живого курса ---
        live_card = QFrame()
        live_card.setStyleSheet(
            "QFrame { background:#eff6ff; border:1px solid #bfdbfe; "
            "border-radius:8px; padding:12px; }"
        )
        live_layout = QHBoxLayout(live_card)
        live_layout.setSpacing(24)

        self.live_pair_label = QLabel("USD/RUB")
        self.live_pair_label.setStyleSheet(
            "font-size:14px; font-weight:600; color:#6b7280;"
        )
        self.live_price_label = QLabel("—")
        self.live_price_label.setStyleSheet(
            "font-size:28px; font-weight:800; color:#1d4ed8;"
        )
        self.live_change_label = QLabel("")
        self.live_change_label.setStyleSheet(
            "font-size:16px; font-weight:600; color:#6b7280;"
        )
        self.cbr_rate_label = QLabel("Курс ЦБ: —")
        self.cbr_rate_label.setStyleSheet(
            "font-size:13px; color:#374151; font-family:Consolas, monospace;"
        )
        self.live_status_label = QLabel("")
        self.live_status_label.setStyleSheet(
            "font-size:12px; color:#6b7280; font-style:italic;"
        )

        live_layout.addWidget(self.live_pair_label)
        live_layout.addWidget(self.live_price_label)
        live_layout.addWidget(self.live_change_label)
        live_layout.addStretch(1)
        live_layout.addWidget(self.cbr_rate_label)
        live_layout.addWidget(self.live_status_label)
        root.addWidget(live_card)

        # --- Панель 1: валюты, база, пресет, инверсия ---
        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background:white; border-radius:8px; padding:8px; }"
        )
        ctrl_layout = QHBoxLayout(controls)
        ctrl_layout.setSpacing(8)

        ctrl_layout.addWidget(QLabel("Валюты:"))
        self.currency_combos: List[QComboBox] = []
        for i in range(MAX_CURRENCIES):
            combo = QComboBox()
            if i == 0:
                combo.addItems(self.service.available_currencies())
                combo.setCurrentText("USD")
            else:
                combo.addItem("—")
                combo.addItems(self.service.available_currencies())
            combo.currentTextChanged.connect(self._on_any_changed)
            ctrl_layout.addWidget(combo)
            self.currency_combos.append(combo)

        ctrl_layout.addWidget(QLabel("База:"))
        self.base_combo = QComboBox()
        self.base_combo.addItems(self.service.available_bases())
        self.base_combo.setCurrentText("RUB")
        self.base_combo.currentTextChanged.connect(self._on_any_changed)
        ctrl_layout.addWidget(self.base_combo)

        ctrl_layout.addWidget(QLabel("Пресет:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("—")
        for name, _cur, _base in PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.currentTextChanged.connect(self._apply_preset)
        ctrl_layout.addWidget(self.preset_combo)

        self.btn_invert = QPushButton("⇄")
        self.btn_invert.setToolTip("Инвертировать пару (валюта ↔ база)")
        self.btn_invert.setFixedWidth(36)
        self.btn_invert.clicked.connect(self._invert_pair)
        ctrl_layout.addWidget(self.btn_invert)

        ctrl_layout.addStretch(1)
        root.addWidget(controls)

        # --- Панель 2: период, режим, экспорт, LIVE ---
        controls2 = QFrame()
        controls2.setStyleSheet(
            "QFrame { background:white; border-radius:8px; padding:8px; }"
        )
        c2 = QHBoxLayout(controls2)
        c2.setSpacing(8)

        c2.addWidget(QLabel("С:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addDays(-30))
        c2.addWidget(self.date_from)

        c2.addWidget(QLabel("По:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        c2.addWidget(self.date_to)

        self.btn_load = QPushButton("Загрузить")
        self.btn_load.clicked.connect(self._load_data)
        c2.addWidget(self.btn_load)

        self.btn_reset = QPushButton("Сброс зума")
        self.btn_reset.clicked.connect(self._reset_zoom)
        c2.addWidget(self.btn_reset)

        c2.addWidget(QLabel("Режим:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Линии", "Свечи (MOEX)", "Спред (MOEX−ЦБ)"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        c2.addWidget(self.mode_combo)

        self.chk_live = QPushButton("LIVE вкл")
        self.chk_live.setCheckable(True)
        self.chk_live.setChecked(True)
        self.chk_live.toggled.connect(self._on_live_toggled)
        self.chk_live.setStyleSheet(
            "QPushButton { padding:6px 12px; border-radius:6px; }"
            "QPushButton:checked { background:#dc2626; color:white; }"
        )
        c2.addWidget(self.chk_live)

        self.btn_png = QPushButton("PNG")
        self.btn_png.clicked.connect(self._export_png)
        c2.addWidget(self.btn_png)

        self.btn_csv = QPushButton("CSV")
        self.btn_csv.clicked.connect(self._export_csv)
        c2.addWidget(self.btn_csv)

        c2.addStretch(1)
        root.addWidget(controls2)

        # --- Статистика ---
        self.stats_label = QLabel("—")
        self.stats_label.setStyleSheet(
            "background:white; border-radius:8px; padding:10px; "
            "color:#374151; font-family:Consolas, monospace;"
        )
        root.addWidget(self.stats_label)

        # --- График ---
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend(offset=(10, 10))
        self.plot.setLabel("bottom", "Дата")
        self.plot.getAxis("bottom").setPen(pg.mkPen("#6b7280"))
        self.plot.getAxis("left").setPen(pg.mkPen("#6b7280"))
        self.plot.setMouseEnabled(x=True, y=True)
        root.addWidget(self.plot, 1)

    # ---------- Таймер ----------

    def _setup_live_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.setInterval(LIVE_REFRESH_MS)
        self.timer.timeout.connect(self._refresh_live)
        self.timer.start()

    def _on_live_toggled(self, checked: bool) -> None:
        if checked:
            self.chk_live.setText("LIVE вкл")
            self.timer.start()
            self._refresh_live()
        else:
            self.chk_live.setText("LIVE выкл")
            self.timer.stop()

    # ---------- События ----------

    def _on_any_changed(self, _t: str = "") -> None:
        self._update_axis_label()
        self._refresh_live()
        self._load_data()

    def _on_mode_changed(self, _t: str) -> None:
        self._load_data()

    def _update_axis_label(self) -> None:
        base = self.base_combo.currentText()
        mode = self.mode_combo.currentText()
        if mode.startswith("Спред"):
            self.plot.setLabel("left", "MOEX − ЦБ, руб.")
        else:
            self.plot.setLabel("left", "Курс, {}".format(base))

    def _apply_preset(self, name: str) -> None:
        if name == "—":
            return
        for pname, cur, base in PRESETS:
            if pname == name:
                self.base_combo.blockSignals(True)
                self.currency_combos[0].blockSignals(True)
                self.base_combo.setCurrentText(base)
                self.currency_combos[0].setCurrentText(cur)
                for combo in self.currency_combos[1:]:
                    combo.blockSignals(True)
                    combo.setCurrentText("—")
                    combo.blockSignals(False)
                self.base_combo.blockSignals(False)
                self.currency_combos[0].blockSignals(False)
                self._on_any_changed()
                return

    def _invert_pair(self) -> None:
        cur = self.currency_combos[0].currentText()
        base = self.base_combo.currentText()
        if not cur or cur == "—" or cur == base:
            return
        self.currency_combos[0].blockSignals(True)
        self.base_combo.blockSignals(True)
        self.currency_combos[0].setCurrentText(base)
        self.base_combo.setCurrentText(cur)
        self.currency_combos[0].blockSignals(False)
        self.base_combo.blockSignals(False)
        self._on_any_changed()

    # ---------- Live ----------

    def _refresh_live(self) -> None:
        cur = self.currency_combos[0].currentText()
        base = self.base_combo.currentText()
        if not cur or cur == "—":
            self.live_pair_label.setText("—")
            self.live_price_label.setText("—")
            self.live_change_label.setText("")
            self.cbr_rate_label.setText("Курс ЦБ: —")
            self.live_status_label.setText("")
            return

        self.live_pair_label.setText("{}/{}".format(cur, base))

        if cur == base:
            self.live_price_label.setText("1.0000")
            self.live_change_label.setText("")
            self.cbr_rate_label.setText("Курс ЦБ: 1.0000")
            self.live_status_label.setText("")
            return

        cbr_cur = self.service.get_last_cbr_rate(cur)
        cbr_base = (
            self.service.get_last_cbr_rate(base)
            if base != "RUB"
            else (date.today(), 1.0)
        )

        cbr_value: Optional[float] = None
        if cbr_cur and cbr_base:
            d = cbr_cur[0]
            if base == "RUB":
                cbr_value = cbr_cur[1]
            else:
                cbr_value = cbr_cur[1] / cbr_base[1] if cbr_base[1] else None
            if cbr_value is not None:
                self.cbr_rate_label.setText(
                    "Курс ЦБ: {:.4f} {} (на {})".format(
                        cbr_value, base, d.strftime("%d.%m.%Y")
                    )
                )
        if cbr_value is None:
            self.cbr_rate_label.setText("Курс ЦБ: нет данных")

        if not self.service.moex_supported(cur) or (
            base != "RUB" and not self.service.moex_supported(base)
        ):
            self.live_price_label.setText("—")
            self.live_change_label.setText("")
            self.live_status_label.setText("MOEX: пара не торгуется")
            return

        price = self.service.get_live_price(cur, base)
        if price is None:
            self.live_price_label.setText("—")
            self.live_change_label.setText("")
            self.live_status_label.setText("MOEX: нет данных (биржа закрыта?)")
            return

        self.live_price_label.setText("{:.4f} {}".format(price, base))

        if cbr_value:
            diff = price - cbr_value
            diff_pct = (diff / cbr_value * 100) if cbr_value else 0.0
            arrow = "+" if diff >= 0 else "-"
            color = "#16a34a" if diff >= 0 else "#dc2626"
            self.live_change_label.setText(
                "{} {:+.4f} ({:+.2f}%) к ЦБ".format(arrow, diff, diff_pct)
            )
            self.live_change_label.setStyleSheet(
                "font-size:16px; font-weight:600; color:{};".format(color)
            )
        else:
            self.live_change_label.setText("")

        self.live_status_label.setText(
            "MOEX · обновлено {}".format(datetime.now().strftime("%H:%M:%S"))
        )

    # ---------- Загрузка ----------

    def _collect_currencies(self) -> List[str]:
        base = self.base_combo.currentText()
        result: List[str] = []
        for combo in self.currency_combos:
            c = combo.currentText()
            if not c or c == "—" or c == base:
                continue
            if c not in result:
                result.append(c)
        return result

    def _load_data(self) -> None:
        date_from = self.date_from.date().toPyDate()
        date_to = self.date_to.date().toPyDate()
        if date_from > date_to:
            QMessageBox.warning(self, "Ошибка", "Дата начала больше даты конца.")
            return

        base = self.base_combo.currentText()
        mode = self.mode_combo.currentText()
        currencies = self._collect_currencies()

        self.plot.clear()
        self.plot.addLegend(offset=(10, 10))
        self._last_series.clear()
        self._update_axis_label()

        if not currencies:
            self.stats_label.setText("Выберите хотя бы одну валюту, отличную от базы.")
            return

        if mode.startswith("Спред"):
            self._render_spread(currencies[0], base)
            return

        if mode.startswith("Свечи"):
            self._render_candles(currencies[0], base, date_from, date_to)
            return

        self._render_lines(currencies, base, date_from, date_to)

    def _render_lines(
        self, currencies: List[str], base: str, date_from: date, date_to: date
    ) -> None:
        stats_lines: List[str] = []
        all_series: List = []

        for idx, cur in enumerate(currencies):
            try:
                series = self.service.get_series(cur, base, date_from, date_to)
            except Exception:
                logger.exception("Ошибка загрузки %s/%s", cur, base)
                continue

            if not series:
                stats_lines.append("{}/{}: нет данных".format(cur, base))
                continue

            self._last_series["{}/{}".format(cur, base)] = series
            xs = [p.date.toordinal() for p in series]
            ys = [p.value for p in series]
            color = LINE_COLORS[idx % len(LINE_COLORS)]

            self.plot.plot(
                xs,
                ys,
                pen=pg.mkPen(color, width=2),
                name="{}/{}".format(cur, base),
                symbol=None,
            )
            all_series.append(series)

            stats = self.service.compute_stats(series)
            if stats:
                sign = "+" if stats.change_pct >= 0 else ""
                stats_lines.append(
                    "{}/{}: min={:.4f}  max={:.4f}  avg={:.4f}  delta={}{:.2f}%".format(
                        cur,
                        base,
                        stats.minimum,
                        stats.maximum,
                        stats.average,
                        sign,
                        stats.change_pct,
                    )
                )

        if all_series:
            axis = self.plot.getAxis("bottom")
            axis.setTicks([self._make_date_ticks(all_series[0])])
            self.plot.enableAutoRange()
        else:
            stats_lines.append("Нет данных.")

        self.stats_label.setText("   |   ".join(stats_lines) if stats_lines else "—")

    def _render_spread(self, currency: str, base: str) -> None:
        if base != "RUB":
            self.stats_label.setText("Спред считается только к RUB.")
            return

        spread = self.service.get_spread_series(currency, base, interval=60, days=30)
        if not spread:
            self.stats_label.setText(
                "Спред {}/{}: нет данных (MOEX недоступен).".format(currency, base)
            )
            return

        self._last_series["{}/{} (спред)".format(currency, base)] = spread
        xs = [p.date.toordinal() for p in spread]
        ys = [p.value for p in spread]

        self.plot.plot(
            xs,
            ys,
            pen=pg.mkPen("#7c3aed", width=2),
            name="Спред {}/{}".format(currency, base),
            symbol="o",
            symbolSize=6,
        )
        self.plot.addLine(y=0, pen=pg.mkPen("#9ca3af", style=Qt.DashLine))
        self.plot.getAxis("bottom").setTicks([self._make_date_ticks(spread)])
        self.plot.enableAutoRange()

        stats = self.service.compute_stats(spread)
        if stats:
            sign = "+" if stats.change_pct >= 0 else ""
            self.stats_label.setText(
                "Спред {}/{}: min={:+.4f}  max={:+.4f}  avg={:+.4f}  delta={}{:.2f}%".format(
                    currency,
                    base,
                    stats.minimum,
                    stats.maximum,
                    stats.average,
                    sign,
                    stats.change_pct,
                )
            )

    def _render_candles(
        self, currency: str, base: str, date_from: date, date_to: date
    ) -> None:
        if base != "RUB":
            self.stats_label.setText("Свечи MOEX доступны только к RUB.")
            return
        if not self.service.moex_supported(currency):
            self.stats_label.setText("Свечи: {} не торгуется на MOEX.".format(currency))
            return

        candles = self.service.get_candles(
            currency, interval=60, date_from=date_from, date_to=date_to
        )
        if not candles:
            self.stats_label.setText("Свечи {}/{}: нет данных.".format(currency, base))
            return

        xs = [c.time.timestamp() for c in candles]

        for c in candles:
            x = c.time.timestamp()
            color = "#16a34a" if c.close >= c.open else "#dc2626"
            self.plot.plot([x, x], [c.low, c.high], pen=pg.mkPen(color, width=1))

        width = (xs[1] - xs[0]) * 0.7 if len(xs) > 1 else 300
        brushes = [
            pg.mkBrush("#16a34a") if c.close >= c.open else pg.mkBrush("#dc2626")
            for c in candles
        ]
        bar = pg.BarGraphItem(
            x=xs,
            height=[abs(c.close - c.open) for c in candles],
            y0=[min(c.open, c.close) for c in candles],
            width=width,
            brushes=brushes,
            pens=brushes,
        )
        self.plot.addItem(bar)
        self.plot.enableAutoRange()

        self.stats_label.setText(
            "Свечи {}/{}: {} шт, часовой интервал.".format(
                currency, base, len(candles)
            )
        )

    @staticmethod
    def _make_date_ticks(series) -> List[Tuple[int, str]]:
        if not series:
            return []
        step = max(1, len(series) // 8)
        ticks: List[Tuple[int, str]] = []
        for i in range(0, len(series), step):
            p = series[i]
            ticks.append((p.date.toordinal(), p.date.strftime("%d.%m")))
        if ticks and ticks[-1][0] != series[-1].date.toordinal():
            p = series[-1]
            ticks.append((p.date.toordinal(), p.date.strftime("%d.%m")))
        return ticks

    # ---------- Экспорт ----------

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить график", "chart.png", "PNG (*.png)"
        )
        if not path:
            return
        try:
            export_plot_png(self.plot, path)
            QMessageBox.information(self, "Готово", "Сохранено: {}".format(path))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def _export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить данные", "data.csv", "CSV (*.csv)"
        )
        if not path:
            return
        if not self._last_series:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите данные.")
            return
        try:
            import csv

            date_set = set()
            for series in self._last_series.values():
                for p in series:
                    date_set.add(p.date)
            dates = sorted(date_set)

            maps = {
                name: {p.date: p.value for p in series}
                for name, series in self._last_series.items()
            }
            names = ["date"] + list(maps.keys())
            rows = []
            for d in dates:
                row = [d.isoformat()]
                for name in maps:
                    val = maps[name].get(d)
                    row.append("" if val is None else "{:.6f}".format(val))
                rows.append(row)

            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(names)
                w.writerows(rows)

            QMessageBox.information(self, "Готово", "Сохранено: {}".format(path))
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    # ---------- Хуки ----------

    def refresh(self) -> None:
        self.service.clear_cache()
        self._refresh_live()
        self._load_data()

    def _reset_zoom(self) -> None:
        self.plot.enableAutoRange()