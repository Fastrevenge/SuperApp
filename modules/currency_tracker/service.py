"""Бизнес-логика утилиты Currency Tracker."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from modules.currency_tracker.data_provider import (
    CBRProvider,
    CURRENCY_CODES,
    RatePoint,
)
from modules.currency_tracker.moex_provider import MOEXProvider, Candle, Tick

logger = logging.getLogger(__name__)

BASE_CURRENCY = "RUB"


@dataclass
class SeriesStats:
    minimum: float
    maximum: float
    average: float
    change_abs: float
    change_pct: float


class CurrencyService:
    def __init__(
        self,
        provider: Optional[CBRProvider] = None,
        moex: Optional[MOEXProvider] = None,
    ) -> None:
        self.provider = provider or CBRProvider()
        self.moex = moex or MOEXProvider()
        self._cache: Dict[Tuple, List[RatePoint]] = {}
        self._last_cbr: Dict[str, Tuple[date, float]] = {}

    @staticmethod
    def available_currencies() -> List[str]:
        return sorted(CURRENCY_CODES.keys())

    @staticmethod
    def available_bases() -> List[str]:
        return ["RUB"] + sorted(CURRENCY_CODES.keys())

    def moex_supported(self, currency: str) -> bool:
        return self.moex.is_supported(currency)

    def _get_series_to_rub(
        self, currency: str, date_from: date, date_to: date
    ) -> List[RatePoint]:
        cur = currency.upper()
        if cur == BASE_CURRENCY:
            return []
        key = (cur, date_from, date_to)
        if key in self._cache:
            return self._cache[key]
        series = self.provider.get_dynamic_rates(date_from, date_to, cur)
        self._cache[key] = series
        return series

    def get_series(
        self, currency: str, base: str, date_from: date, date_to: date
    ) -> List[RatePoint]:
        cur = currency.upper()
        b = base.upper()
        if cur == b:
            raise ValueError("Валюта и база совпадают: {} / {}".format(cur, b))
        if b == BASE_CURRENCY:
            return self._get_series_to_rub(cur, date_from, date_to)

        series_cur = self._get_series_to_rub(cur, date_from, date_to)
        series_base = self._get_series_to_rub(b, date_from, date_to)
        if not series_cur or not series_base:
            return []

        map_cur = {p.date: p.value for p in series_cur}
        map_base = {p.date: p.value for p in series_base}
        common = sorted(set(map_cur.keys()) & set(map_base.keys()))

        result: List[RatePoint] = []
        for d in common:
            bv = map_base[d]
            if bv == 0:
                continue
            result.append(RatePoint(date=d, value=map_cur[d] / bv, nominal=1))
        return result

    def get_multi_series(
        self, currencies: List[str], base: str, date_from: date, date_to: date
    ) -> Dict[str, List[RatePoint]]:
        result: Dict[str, List[RatePoint]] = {}
        for cur in currencies:
            if cur.upper() == base.upper():
                continue
            try:
                result[cur] = self.get_series(cur, base, date_from, date_to)
            except Exception as exc:
                logger.warning("get_multi_series(%s/%s): %s", cur, base, exc)
                result[cur] = []
        return result

    def get_spread_series(
        self, currency: str, base: str, interval: int = 60, days: int = 7
    ) -> List[RatePoint]:
        if base.upper() != BASE_CURRENCY:
            return []
        if not self.moex_supported(currency):
            return []

        date_to = date.today()
        date_from = date_to - timedelta(days=days)

        candles = self.moex.get_candles(
            currency, interval=interval, date_from=date_from, date_to=date_to
        )
        if not candles:
            return []

        cbr_series = self._get_series_to_rub(currency, date_from, date_to)
        cbr_map = {p.date: p.value for p in cbr_series}

        by_date: Dict[date, float] = {}
        for c in candles:
            d = c.time.date()
            cbr_val = cbr_map.get(d)
            if cbr_val is None:
                earlier = [k for k in cbr_map.keys() if k <= d]
                if not earlier:
                    continue
                cbr_val = cbr_map[max(earlier)]
            by_date[d] = c.close - cbr_val
        return [RatePoint(date=d, value=by_date[d], nominal=1)
                for d in sorted(by_date.keys())]

    def get_last_cbr_rate(self, currency: str) -> Optional[Tuple[date, float]]:
        cur = currency.upper()
        if cur in self._last_cbr:
            return self._last_cbr[cur]

        today = date.today()
        for delta in range(0, 8):
            d = today - timedelta(days=delta)
            try:
                rates = self.provider.get_daily_rates(d)
            except Exception as exc:
                logger.debug("CBR daily error on %s: %s", d, exc)
                continue
            if cur == BASE_CURRENCY:
                result = (d, 1.0)
                self._last_cbr[cur] = result
                return result
            if cur in rates:
                result = (d, rates[cur])
                self._last_cbr[cur] = result
                return result
        return None

    def get_live_price(self, currency: str, base: str = "RUB") -> Optional[float]:
        cur = currency.upper()
        b = base.upper()
        price_cur = self.moex.get_last_price(cur) if cur != BASE_CURRENCY else 1.0
        if price_cur is None:
            return None
        if b == BASE_CURRENCY:
            return price_cur
        price_base = self.moex.get_last_price(b) if b != BASE_CURRENCY else 1.0
        if price_base is None or price_base == 0:
            return None
        return price_cur / price_base

    def get_intraday_series(self, currency: str) -> List[Tick]:
        return self.moex.get_intraday_series(currency)

    def get_candles(
        self,
        currency: str,
        interval: int = 60,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Candle]:
        return self.moex.get_candles(currency, interval, date_from, date_to)

    @staticmethod
    def compute_stats(series: List[RatePoint]) -> Optional[SeriesStats]:
        if not series:
            return None
        values = [p.value for p in series]
        first, last = values[0], values[-1]
        change_abs = last - first
        change_pct = (change_abs / first * 100) if first else 0.0
        return SeriesStats(
            minimum=min(values),
            maximum=max(values),
            average=sum(values) / len(values),
            change_abs=change_abs,
            change_pct=change_pct,
        )

    def clear_cache(self) -> None:
        self._cache.clear()
        self._last_cbr.clear()