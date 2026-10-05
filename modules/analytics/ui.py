"""UI утилиты «Аналитика»."""
from __future__ import annotations

import logging
from typing import Optional

import pyqtgraph as pg
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.analytics.service import AnalyticsResult, AnalyticsService

logger = logging.getLogger(__name__)


class AnalyticsWidget(QWidget):
    """Аналитика валютной пары: статистика, SMA, гибридный прогноз."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.service = AnalyticsService()
        self._result: Optional[AnalyticsResult] = None

        self._build_ui()
        self._load_data()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("Аналитика и прогноз")
        title.setStyleSheet("font-size:20px; font-weight:700; color:#111827;")
        root.addWidget(title)

        subtitle = QLabel(
            "Гибридная модель: STL-декомпозиция + ARIMA (тренд) + XGBoost (остаток). "
            "Показаны MAPE/RMSE и 95% доверительный интервал."
        )
        subtitle.setStyleSheet("color:#6b7280; font-size:13px;")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        # --- Панель управления ---
        controls = QFrame()
        controls.setStyleSheet(
            "QFrame { background:white; border-radius:8px; padding:8px; }"
        )
        ctrl = QHBoxLayout(controls)
        ctrl.setSpacing(10)

        ctrl.addWidget(QLabel("Валюта:"))
        self.currency_combo = QComboBox()
        self.currency_combo.addItems(
            self.service.currency_service.available_currencies()
        )
        self.currency_combo.setCurrentText("USD")
        ctrl.addWidget(self.currency_combo)

        ctrl.addWidget(QLabel("База:"))
        self.base_combo = QComboBox()
        self.base_combo.addItems(
            self.service.currency_service.available_bases()
        )
        self.base_combo.setCurrentText("RUB")
        ctrl.addWidget(self.base_combo)

        ctrl.addWidget(QLabel("Период (дней):"))
        self.days_spin = QSpinBox()
        self.days_spin.setRange(30, 730)
        self.days_spin.setValue(180)
        ctrl.addWidget(self.days_spin)

        ctrl.addWidget(QLabel("Прогноз (дней):"))
        self.forecast_spin = QSpinBox()
        self.forecast_spin.setRange(1, 60)
        self.forecast_spin.setValue(14)
        ctrl.addWidget(self.forecast_spin)

        self.btn_load = QPushButton("Проанализировать")
        self.btn_load.clicked.connect(self._load_data)
        ctrl.addWidget(self.btn_load)

        ctrl.addStretch(1)
        root.addWidget(controls)

        # --- Карточки со статистикой ---
        stats_card = QFrame()
        stats_card.setStyleSheet(
            "QFrame { background:white; border-radius:8px; padding:12px; }"
        )
        stats_layout = QGridLayout(stats_card)
        stats_layout.setHorizontalSpacing(24)
        stats_layout.setVerticalSpacing(6)

        self.stat_labels = {}
        fields = [
            ("Последнее", "last"),
            ("Мин.", "min"),
            ("Макс.", "max"),
            ("Среднее", "avg"),
            ("Медиана", "median"),
            ("Ст. откл.", "std"),
            ("Δ абс.", "change_abs"),
            ("Δ %", "change_pct"),
            ("Волатильность", "vol"),
            ("Тренд", "trend"),
            ("MAPE", "mape"),
            ("RMSE", "rmse"),
        ]
        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 6)
            name_lbl = QLabel(label + ":")
            name_lbl.setStyleSheet("color:#6b7280; font-size:12px;")
            value_lbl = QLabel("—")
            value_lbl.setStyleSheet(
                "color:#111827; font-size:14px; font-weight:600;"
            )
            stats_layout.addWidget(name_lbl, row * 2, col)
            stats_layout.addWidget(value_lbl, row * 2 + 1, col)
            self.stat_labels[key] = value_lbl

        root.addWidget(stats_card)

        # --- Легенда графика ---
        legend_row = QHBoxLayout()
        legend_row.setSpacing(18)
        for text, color, dash in [
            ("Факт", "#2563eb", False),
            ("SMA-7", "#d97706", True),
            ("Прогноз", "#7c3aed", True),
            ("95% интервал", "#a78bfa", False),
        ]:
            badge = QLabel("  " + text)
            style = (
                "color:#111827; font-size:12px; "
                "border-left: 4px solid {}; padding-left:6px;".format(color)
            )
            badge.setStyleSheet(style)
            legend_row.addWidget(badge)
        legend_row.addStretch(1)
        root.addLayout(legend_row)

        # --- График ---
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("w")
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.addLegend(offset=(10, 10))
        self.plot.setLabel("left", "Курс")
        self.plot.setLabel("bottom", "Дата")
        self.plot.getAxis("bottom").setPen(pg.mkPen("#6b7280"))
        self.plot.getAxis("left").setPen(pg.mkPen("#6b7280"))
        root.addWidget(self.plot, 1)

    # ---------- Логика ----------

    def _load_data(self) -> None:
        currency = self.currency_combo.currentText()
        base = self.base_combo.currentText()

        if currency == base:
            QMessageBox.warning(
                self,
                "Ошибка",
                "Валюта и база не должны совпадать.\nВыберите разные значения.",
            )
            return

        days = self.days_spin.value()
        forecast = self.forecast_spin.value()

        self.btn_load.setEnabled(False)
        self.btn_load.setText("Считаю…")

        try:
            result = self.service.analyze(currency, base, days, forecast)
        except Exception as exc:
            logger.exception("Ошибка анализа %s/%s", currency, base)
            QMessageBox.critical(self, "Ошибка", str(exc))
            result = None
        finally:
            self.btn_load.setEnabled(True)
            self.btn_load.setText("Проанализировать")

        if result is None:
            self._clear_stats()
            self.plot.clear()
            self.stat_labels["last"].setText("Нет данных за выбранный период.")
            return

        self._result = result
        self._render_stats(result)
        self._render_plot(result)

    def _clear_stats(self) -> None:
        for lbl in self.stat_labels.values():
            lbl.setText("—")

    def _render_stats(self, r: AnalyticsResult) -> None:
        sign = "+" if r.change_pct >= 0 else ""
        color = "#16a34a" if r.change_pct >= 0 else "#dc2626"

        self.stat_labels["last"].setText("{:.4f} {}".format(r.last, r.base))
        self.stat_labels["min"].setText("{:.4f}".format(r.minimum))
        self.stat_labels["max"].setText("{:.4f}".format(r.maximum))
        self.stat_labels["avg"].setText("{:.4f}".format(r.average))
        self.stat_labels["median"].setText("{:.4f}".format(r.median))
        self.stat_labels["std"].setText("{:.4f}".format(r.std_dev))
        self.stat_labels["change_abs"].setText("{:+.4f}".format(r.change_abs))
        self.stat_labels["change_pct"].setText(
            "{}{:.2f}%".format(sign, r.change_pct)
        )
        self.stat_labels["change_pct"].setStyleSheet(
            "color:{}; font-size:14px; font-weight:600;".format(color)
        )
        self.stat_labels["vol"].setText("{:.2f}%".format(r.volatility_pct))
        self.stat_labels["trend"].setText(r.trend_direction)

        # Метрики качества модели
        if r.mape is not None:
            self.stat_labels["mape"].setText("{:.2f}%".format(r.mape))
            if r.mape < 3:
                self.stat_labels["mape"].setStyleSheet(
                    "color:#16a34a; font-size:14px; font-weight:600;"
                )
            elif r.mape < 7:
                self.stat_labels["mape"].setStyleSheet(
                    "color:#d97706; font-size:14px; font-weight:600;"
                )
            else:
                self.stat_labels["mape"].setStyleSheet(
                    "color:#dc2626; font-size:14px; font-weight:600;"
                )
        else:
            self.stat_labels["mape"].setText("—")

        if r.rmse is not None:
            self.stat_labels["rmse"].setText("{:.4f}".format(r.rmse))
        else:
            self.stat_labels["rmse"].setText("—")

    def _render_plot(self, r: AnalyticsResult) -> None:
        self.plot.clear()
        self.plot.addLegend(offset=(10, 10))
        self.plot.setLabel("left", "Курс, {}".format(r.base))

        # --- Факт ---
        xs = [p.date.toordinal() for p in r.points]
        ys = [p.value for p in r.points]
        self.plot.plot(
            xs,
            ys,
            pen=pg.mkPen("#2563eb", width=2),
            name="{}/{}".format(r.currency, r.base),
        )

        # --- SMA-7 ---
        if r.sma_7:
            sma_x = [d.toordinal() for d, _ in r.sma_7]
            sma_y = [v for _, v in r.sma_7]
            self.plot.plot(
                sma_x,
                sma_y,
                pen=pg.mkPen("#d97706", width=2, style=Qt.DashLine),
                name="SMA-7",
            )

        # --- Доверительный интервал (перед линией прогноза, чтобы был под ней) ---
        if r.forecast_lower and r.forecast_upper:
            fx = [r.points[-1].date.toordinal()] + [
                d.toordinal() for d in r.forecast_dates
            ]
            lower = [r.points[-1].value] + list(r.forecast_lower)
            upper = [r.points[-1].value] + list(r.forecast_upper)

            # Закрашенная область между lower и upper
            # Рисуем "ленту": верхняя граница + обратная нижняя
            band_x = fx + list(reversed(fx))
            band_y = upper + list(reversed(lower))
            self.plot.plot(
                band_x,
                band_y,
                pen=pg.mkPen((124, 58, 237, 0)),
                fillLevel=0,
                brush=pg.mkBrush(124, 58, 237, 60),
                name="95% интервал",
            )

            # Тонкие границы интервала
            self.plot.plot(
                fx,
                lower,
                pen=pg.mkPen((124, 58, 237, 120), width=1, style=Qt.DotLine),
            )
            self.plot.plot(
                fx,
                upper,
                pen=pg.mkPen((124, 58, 237, 120), width=1, style=Qt.DotLine),
            )

        # --- Прогноз (линия) ---
        if r.forecast_dates:
            fx = [r.points[-1].date.toordinal()] + [
                d.toordinal() for d in r.forecast_dates
            ]
            fy = [r.points[-1].value] + list(r.forecast_values)
            self.plot.plot(
                fx,
                fy,
                pen=pg.mkPen("#7c3aed", width=2, style=Qt.DotLine),
                name="Прогноз",
                symbol="o",
                symbolSize=5,
                symbolBrush="#7c3aed",
            )

        # --- Оформление оси X ---
        if r.points:
            axis = self.plot.getAxis("bottom")
            axis.setTicks([self._make_ticks(r.points)])
        self.plot.enableAutoRange()

    @staticmethod
    def _make_ticks(points) -> list:
        if not points:
            return []
        step = max(1, len(points) // 8)
        ticks = []
        for i in range(0, len(points), step):
            p = points[i]
            ticks.append((p.date.toordinal(), p.date.strftime("%d.%m")))
        if ticks and ticks[-1][0] != points[-1].date.toordinal():
            p = points[-1]
            ticks.append((p.date.toordinal(), p.date.strftime("%d.%m")))
        return ticks

    # ---------- Публичные хуки ----------

    def refresh(self) -> None:
        self.service.currency_service.clear_cache()
        self._load_data()