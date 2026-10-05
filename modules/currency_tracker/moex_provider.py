"""Провайдер биржевых котировок MOEX ISS."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

MOEX_TICKERS: Dict[str, str] = {
    "USD": "USD000UTSTOM",
    "EUR": "EUR_RUB__TOM",
    "CNY": "CNYRUB_TOM",
    "GBP": "GBPRUB_TOM",
    "CHF": "CHFRUB_TOM",
    "TRY": "TRYRUB_TOM",
    "KZT": "KZTRUB_TOM",
    "BYN": "BYNRUB_TOM",
}


@dataclass
class Tick:
    time: datetime
    price: float


@dataclass
class Candle:
    time: datetime
    open: float
    high: float
    low: float
    close: float


class MOEXProvider:
    BASE = "https://iss.moex.com/iss"

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SuperApp/0.1"})

    def is_supported(self, currency: str) -> bool:
        return currency.upper() in MOEX_TICKERS

    def get_last_price(self, currency: str) -> Optional[float]:
        ticker = MOEX_TICKERS.get(currency.upper())
        if not ticker:
            return None
        url = "{}/engines/currency/markets/selt/securities/{}.json".format(
            self.BASE, ticker
        )
        try:
            r = self._session.get(url, params={"iss.meta": "off"}, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("MOEX last price error for %s: %s", currency, exc)
            return None

        md = data.get("marketdata", {})
        cols = md.get("columns", [])
        rows = md.get("data", [])
        if "LAST" not in cols:
            return None
        idx = cols.index("LAST")
        for row in rows:
            val = row[idx]
            if val is not None:
                return float(val)
        return None

    def get_intraday_series(self, currency: str) -> List[Tick]:
        ticker = MOEX_TICKERS.get(currency.upper())
        if not ticker:
            return []
        url = "{}/engines/currency/markets/selt/securities/{}/trades.json".format(
            self.BASE, ticker
        )
        try:
            r = self._session.get(
                url,
                params={"iss.meta": "off", "limit": 1000},
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("MOEX intraday error for %s: %s", currency, exc)
            return []

        trades = data.get("trades", {})
        cols = trades.get("columns", [])
        rows = trades.get("data", [])
        if not cols or not rows:
            return []

        try:
            t_idx = cols.index("TRADETIME")
            p_idx = cols.index("PRICE")
        except ValueError:
            return []

        ticks: List[Tick] = []
        today = date.today()
        for row in rows:
            try:
                t_str = row[t_idx]
                price = row[p_idx]
                if price is None or t_str is None:
                    continue
                t = datetime.strptime(
                    "{} {}".format(today.isoformat(), t_str), "%Y-%m-%d %H:%M:%S"
                )
                ticks.append(Tick(time=t, price=float(price)))
            except (ValueError, TypeError):
                continue

        ticks.sort(key=lambda x: x.time)
        return ticks

    def get_candles(
        self,
        currency: str,
        interval: int = 60,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> List[Candle]:
        ticker = MOEX_TICKERS.get(currency.upper())
        if not ticker:
            return []

        url = "{}/engines/currency/markets/selt/securities/{}/candles.json".format(
            self.BASE, ticker
        )
        params = {"iss.meta": "off", "interval": interval, "limit": 500}
        if date_from:
            params["from"] = date_from.isoformat()
        if date_to:
            params["till"] = date_to.isoformat()

        try:
            r = self._session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            logger.warning("MOEX candles error for %s: %s", currency, exc)
            return []

        candles = data.get("candles", {})
        cols = candles.get("columns", [])
        rows = candles.get("data", [])
        if not cols or not rows:
            return []

        try:
            begin_idx = cols.index("begin")
            o_idx = cols.index("open")
            h_idx = cols.index("high")
            l_idx = cols.index("low")
            c_idx = cols.index("close")
        except ValueError:
            return []

        result: List[Candle] = []
        for row in rows:
            try:
                t = datetime.strptime(row[begin_idx], "%Y-%m-%d %H:%M:%S")
                result.append(
                    Candle(
                        time=t,
                        open=float(row[o_idx]),
                        high=float(row[h_idx]),
                        low=float(row[l_idx]),
                        close=float(row[c_idx]),
                    )
                )
            except (ValueError, TypeError):
                continue
        return result