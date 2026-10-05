"""Бизнес-логика утилиты «Аналитика» — гибридный прогноз."""
from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.arima.model import ARIMA
from xgboost import XGBRegressor

from modules.currency_tracker.data_provider import CBRProvider, RatePoint
from modules.currency_tracker.service import CurrencyService

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning)


@dataclass
class AnalyticsResult:
    """Результат анализа ряда."""
    currency: str
    base: str
    date_from: date
    date_to: date
    points: List[RatePoint]
    minimum: float
    maximum: float
    average: float
    median: float
    std_dev: float
    first: float
    last: float
    change_abs: float
    change_pct: float
    volatility_pct: float
    trend_slope: float
    trend_direction: str
    sma_7: List[Tuple[date, float]]
    forecast_dates: List[date]
    forecast_values: List[float]
    forecast_lower: List[float] = field(default_factory=list)
    forecast_upper: List[float] = field(default_factory=list)
    mape: Optional[float] = None
    rmse: Optional[float] = None


class AnalyticsService:
    """Гибридный анализ: STL-декомпозиция + ARIMA (тренд) + XGBoost (остаток)."""

    def __init__(self) -> None:
        self.currency_service = CurrencyService(CBRProvider())

    # ---------- Публичный API ----------

    def analyze(
        self,
        currency: str,
        base: str,
        days: int = 90,
        forecast_days: int = 14,
        sma_window: int = 7,
    ) -> Optional[AnalyticsResult]:
        date_to = date.today()
        date_from = date_to - timedelta(days=days)

        points = self.currency_service.get_series(currency, base, date_from, date_to)
        if not points:
            return None
        if len(points) < 20:
            logger.warning("Слишком мало данных для гибридного прогноза: %d точек", len(points))
            # Фолбэк на простую регрессию при малом числе точек
            return self._analyze_simple(currency, base, points, forecast_days, sma_window)

        values = np.array([p.value for p in points], dtype=float)
        n = len(values)

        # Базовая статистика
        minimum = float(np.min(values))
        maximum = float(np.max(values))
        average = float(np.mean(values))
        median = float(np.median(values))
        std_dev = float(np.std(values, ddof=1))
        first = float(values[0])
        last = float(values[-1])
        change_abs = last - first
        change_pct = (change_abs / first * 100) if first else 0.0
        volatility_pct = (std_dev / average * 100) if average else 0.0

        # Простой наклон для отображения направления
        slope, intercept = self._linear_regression(values)
        slope_pct = (slope / average * 100) if average else 0.0
        if slope_pct > 0.05:
            direction = "вверх"
        elif slope_pct < -0.05:
            direction = "вниз"
        else:
            direction = "боковик"

        sma = self._sma(points, sma_window)

        # ---------- Гибридный прогноз ----------
        try:
            forecast_values, forecast_lower, forecast_upper = self._hybrid_forecast(
                values, forecast_days
            )
        except Exception as exc:
            logger.exception("Гибридный прогноз не удался: %s", exc)
            # Фолбэк на линейную регрессию
            forecast_values = [
                intercept + slope * (n - 1 + i) for i in range(1, forecast_days + 1)
            ]
            forecast_lower = []
            forecast_upper = []

        forecast_dates = [points[-1].date + timedelta(days=i) for i in range(1, forecast_days + 1)]

        # ---------- Оценка качества (walk-forward на последних 20%) ----------
        mape, rmse = self._evaluate_hybrid(values, test_size=max(5, n // 5))

        return AnalyticsResult(
            currency=currency,
            base=base,
            date_from=points[0].date,
            date_to=points[-1].date,
            points=points,
            minimum=minimum,
            maximum=maximum,
            average=average,
            median=median,
            std_dev=std_dev,
            first=first,
            last=last,
            change_abs=change_abs,
            change_pct=change_pct,
            volatility_pct=volatility_pct,
            trend_slope=slope,
            trend_direction=direction,
            sma_7=sma,
            forecast_dates=forecast_dates,
            forecast_values=forecast_values,
            forecast_lower=forecast_lower,
            forecast_upper=forecast_upper,
            mape=mape,
            rmse=rmse,
        )

    # ---------- Гибридная модель ----------

    def _hybrid_forecast(
        self, values: np.ndarray, horizon: int
    ) -> Tuple[List[float], List[float], List[float]]:
        """STL + ARIMA (тренд) + XGBoost (остаток).

        Шаги:
        1. STL-декомпозиция на тренд, сезонность, остаток.
        2. ARIMA на тренд (прогноз на horizon шагов).
        3. XGBoost на остаток (лаговые признаки, прогноз на horizon).
        4. Сумма тренд + сезонность + остаток.
        5. Доверительный интервал из остатков ARIMA/XGBoost.
        """
        n = len(values)

        # STL требует минимум 2 полных периода сезонности.
        # Для дневных данных без явной сезонности используем period=7 (неделя).
        period = min(7, max(2, n // 3))
        stl = STL(values, period=period, robust=True)
        decomp = stl.fit()
        trend = decomp.trend
        seasonal = decomp.seasonal
        resid = decomp.resid

        # --- ARIMA на тренд ---
        # Простая авто-подборка порядка: пробуем (1,1,1) и (2,1,1)
        best_aic = np.inf
        best_arima_fit = None
        for order in [(1, 1, 1), (2, 1, 1), (1, 1, 0)]:
            try:
                model = ARIMA(trend, order=order)
                fit = model.fit()
                if fit.aic < best_aic:
                    best_aic = fit.aic
                    best_arima_fit = fit
            except Exception:
                continue
        if best_arima_fit is None:
            # Фолбэк: линейная экстраполяция тренда
            trend_forecast = np.array([trend[-1]] * horizon)
            trend_se = np.std(trend) * np.ones(horizon)
        else:
            fc = best_arima_fit.get_forecast(steps=horizon)
            trend_forecast = fc.predicted_mean
            trend_se = fc.se_mean

        # --- XGBoost на остаток (resid) ---
        # Формируем лаговые признаки
        lag = min(5, n // 5)
        if lag < 2:
            lag = 2
        X_res, y_res = self._make_lagged(resid, lag)
        resid_forecast = np.zeros(horizon)
        if len(X_res) >= 10:
            try:
                xgb = XGBRegressor(
                    n_estimators=50,
                    max_depth=3,
                    learning_rate=0.1,
                    objective="reg:squarederror",
                    verbosity=0,
                )
                xgb.fit(X_res, y_res)
                # Рекурсивный прогноз остатка
                last_window = list(resid[-lag:])
                for i in range(horizon):
                    x_in = np.array(last_window[-lag:]).reshape(1, -1)
                    pred = float(xgb.predict(x_in)[0])
                    resid_forecast[i] = pred
                    last_window.append(pred)
            except Exception as exc:
                logger.warning("XGBoost на остатке не удался: %s", exc)
                resid_forecast = np.zeros(horizon)
        else:
            resid_forecast = np.zeros(horizon)

        # --- Сезонность ---
        # Простейшее допущение: повторяем последний сезонный цикл
        if period > 0 and len(seasonal) >= period:
            seasonal_forecast = np.array(
                [seasonal[-period + (i % period)] for i in range(horizon)]
            )
        else:
            seasonal_forecast = np.zeros(horizon)

        # --- Итоговый прогноз ---
        forecast = trend_forecast + seasonal_forecast + resid_forecast

        # --- Доверительный интервал (95%) ---
        # Оценка остаточной дисперсии после STL + ARIMA + XGBoost
        fitted_trend = best_arima_fit.fittedvalues if best_arima_fit is not None else trend
        total_resid = values - (fitted_trend + seasonal + resid_forecast[:n] if len(resid_forecast) >= n else fitted_trend + seasonal)
        # Упрощённо: используем std остатков STL и se тренда
        sigma = float(np.std(resid, ddof=1))
        z = 1.96  # 95%
        lower = forecast - z * sigma - trend_se
        upper = forecast + z * sigma + trend_se

        return (
            [float(v) for v in forecast],
            [float(v) for v in lower],
            [float(v) for v in upper],
        )

    def _make_lagged(
        self, series: np.ndarray, lag: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Формирует X (лаги) и y (следующее значение)."""
        X, y = [], []
        for i in range(lag, len(series)):
            X.append(series[i - lag : i])
            y.append(series[i])
        return np.array(X), np.array(y)

    # ---------- Оценка качества ----------

    def _evaluate_hybrid(
        self, values: np.ndarray, test_size: int = 10
    ) -> Tuple[Optional[float], Optional[float]]:
        """Walk-forward оценка: обучаем на первых n-test_size, проверяем на последних."""
        n = len(values)
        if n < test_size + 15:
            return None, None
        train = values[: n - test_size]
        test = values[n - test_size :]
        try:
            forecast, _, _ = self._hybrid_forecast(train, test_size)
            forecast = np.array(forecast)
            mape = float(np.mean(np.abs((test - forecast) / test)) * 100)
            rmse = float(np.sqrt(np.mean((test - forecast) ** 2)))
            return mape, rmse
        except Exception as exc:
            logger.warning("Оценка качества не удалась: %s", exc)
            return None, None

    # ---------- Фолбэк для малых рядов ----------

    def _analyze_simple(
        self,
        currency: str,
        base: str,
        points: List[RatePoint],
        forecast_days: int,
        sma_window: int,
    ) -> AnalyticsResult:
        values = np.array([p.value for p in points], dtype=float)
        n = len(values)
        minimum = float(np.min(values))
        maximum = float(np.max(values))
        average = float(np.mean(values))
        median = float(np.median(values))
        std_dev = float(np.std(values, ddof=1)) if n > 1 else 0.0
        first = float(values[0])
        last = float(values[-1])
        change_abs = last - first
        change_pct = (change_abs / first * 100) if first else 0.0
        volatility_pct = (std_dev / average * 100) if average else 0.0
        slope, intercept = self._linear_regression(values)
        slope_pct = (slope / average * 100) if average else 0.0
        direction = "вверх" if slope_pct > 0.05 else ("вниз" if slope_pct < -0.05 else "боковик")
        sma = self._sma(points, sma_window)
        forecast_values = [intercept + slope * (n - 1 + i) for i in range(1, forecast_days + 1)]
        forecast_dates = [points[-1].date + timedelta(days=i) for i in range(1, forecast_days + 1)]
        return AnalyticsResult(
            currency=currency,
            base=base,
            date_from=points[0].date,
            date_to=points[-1].date,
            points=points,
            minimum=minimum,
            maximum=maximum,
            average=average,
            median=median,
            std_dev=std_dev,
            first=first,
            last=last,
            change_abs=change_abs,
            change_pct=change_pct,
            volatility_pct=volatility_pct,
            trend_slope=slope,
            trend_direction=direction,
            sma_7=sma,
            forecast_dates=forecast_dates,
            forecast_values=forecast_values,
        )

    # ---------- Статистика ----------

    @staticmethod
    def _linear_regression(values: np.ndarray) -> Tuple[float, float]:
        n = len(values)
        if n < 2:
            return 0.0, float(values[0]) if n else 0.0
        xs = np.arange(n)
        mean_x = xs.mean()
        mean_y = values.mean()
        num = np.sum((xs - mean_x) * (values - mean_y))
        den = np.sum((xs - mean_x) ** 2)
        if den == 0:
            return 0.0, float(mean_y)
        slope = num / den
        intercept = mean_y - slope * mean_x
        return float(slope), float(intercept)

    @staticmethod
    def _sma(
        points: List[RatePoint], window: int
    ) -> List[Tuple[date, float]]:
        if len(points) < window or window < 2:
            return []
        result: List[Tuple[date, float]] = []
        for i in range(window - 1, len(points)):
            chunk = points[i - window + 1 : i + 1]
            avg = sum(p.value for p in chunk) / window
            result.append((points[i].date, avg))
        return result