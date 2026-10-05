"""Провайдер данных о курсах валют с API ЦБ РФ."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

import requests
import xml.etree.ElementTree as ET

from core.config import CBR_DAILY, CBR_DYNAMIC

logger = logging.getLogger(__name__)

CURRENCY_CODES: Dict[str, str] = {
    "USD": "R01235",
    "EUR": "R01239",
    "CNY": "R01375",
    "GBP": "R01035",
    "JPY": "R01820",
    "CHF": "R01775",
    "TRY": "R01700J",
    "KZT": "R01335",
}


@dataclass
class RatePoint:
    date: date
    value: float
    nominal: int = 1


class CBRProvider:
    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "SuperApp/0.1"})

    def get_daily_rates(self, on_date: Optional[date] = None) -> Dict[str, float]:
        params: Dict[str, str] = {}
        if on_date:
            params["date_req"] = on_date.strftime("%d/%m/%Y")
        response = self._session.get(CBR_DAILY, params=params, timeout=self.timeout)
        response.raise_for_status()
        return self._parse_daily(response.content)

    def get_dynamic_rates(
        self, date_from: date, date_to: date, currency: str
    ) -> List[RatePoint]:
        code = CURRENCY_CODES.get(currency.upper())
        if not code:
            raise ValueError("Неизвестная валюта: {}".format(currency))
        params = {
            "date_req1": date_from.strftime("%d/%m/%Y"),
            "date_req2": date_to.strftime("%d/%m/%Y"),
            "VAL_NM_RQ": code,
        }
        response = self._session.get(CBR_DYNAMIC, params=params, timeout=self.timeout)
        response.raise_for_status()
        return self._parse_dynamic(response.content)

    def _parse_daily(self, content: bytes) -> Dict[str, float]:
        root = ET.fromstring(content)
        result: Dict[str, float] = {}
        for valute in root.findall("Valute"):
            char_code = valute.findtext("CharCode")
            value_str = (valute.findtext("Value") or "0").replace(",", ".")
            nominal_str = valute.findtext("Nominal") or "1"
            try:
                value = float(value_str) / int(nominal_str)
            except ValueError:
                continue
            if char_code:
                result[char_code] = value
        return result

    def _parse_dynamic(self, content: bytes) -> List[RatePoint]:
        root = ET.fromstring(content)
        points: List[RatePoint] = []
        for rec in root.findall("Record"):
            date_attr = rec.get("Date")
            value_str = (rec.findtext("Value") or "0").replace(",", ".")
            nominal_str = rec.findtext("Nominal") or "1"
            if not date_attr:
                continue
            try:
                d = datetime.strptime(date_attr, "%d.%m.%Y").date()
                value = float(value_str) / int(nominal_str)
            except (ValueError, TypeError):
                continue
            points.append(RatePoint(date=d, value=value, nominal=int(nominal_str)))
        points.sort(key=lambda p: p.date)
        return points

    def get_rates_for_many(
        self, currencies: Iterable[str], date_from: date, date_to: date
    ) -> Dict[str, List[RatePoint]]:
        result: Dict[str, List[RatePoint]] = {}
        for cur in currencies:
            try:
                result[cur] = self.get_dynamic_rates(date_from, date_to, cur)
            except Exception as exc:
                logger.warning("Не удалось загрузить %s: %s", cur, exc)
                result[cur] = []
        return result