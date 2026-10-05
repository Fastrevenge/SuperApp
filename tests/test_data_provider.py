"""Тесты парсеров CBRProvider (без реальных запросов)."""
from datetime import date

import pytest

from modules.currency_tracker.data_provider import CBRProvider
from modules.currency_tracker.service import CurrencyService


DAILY_XML = b"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs Date="01.01.2024" name="Foreign Currency Market">
    <Valute ID="R01235">
        <NumCode>840</NumCode>
        <CharCode>USD</CharCode>
        <Nominal>1</Nominal>
        <Name>Dollar</Name>
        <Value>90,1234</Value>
    </Valute>
    <Valute ID="R01239">
        <NumCode>978</NumCode>
        <CharCode>EUR</CharCode>
        <Nominal>1</Nominal>
        <Name>Euro</Name>
        <Value>98,5678</Value>
    </Valute>
</ValCurs>
"""

DYNAMIC_XML = b"""<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01235" DateRange1="01.01.2024" DateRange2="03.01.2024">
    <Record Date="01.01.2024" Id="R01235">
        <Nominal>1</Nominal><Value>90,0000</Value>
    </Record>
    <Record Date="02.01.2024" Id="R01235">
        <Nominal>1</Nominal><Value>91,0000</Value>
    </Record>
    <Record Date="03.01.2024" Id="R01235">
        <Nominal>1</Nominal><Value>92,5000</Value>
    </Record>
</ValCurs>
"""


def test_parse_daily():
    p = CBRProvider()
    result = p._parse_daily(DAILY_XML)
    assert result["USD"] == pytest.approx(90.1234)
    assert result["EUR"] == pytest.approx(98.5678)


def test_parse_dynamic():
    p = CBRProvider()
    points = p._parse_dynamic(DYNAMIC_XML)
    assert len(points) == 3
    assert points[0].date == date(2024, 1, 1)
    assert points[-1].value == pytest.approx(92.5)


def test_stats():
    p = CBRProvider()
    points = p._parse_dynamic(DYNAMIC_XML)
    stats = CurrencyService.compute_stats(points)
    assert stats is not None
    assert stats.minimum == pytest.approx(90.0)
    assert stats.maximum == pytest.approx(92.5)
    assert stats.change_abs == pytest.approx(2.5)


def test_unknown_currency():
    p = CBRProvider()
    with pytest.raises(ValueError):
        p.get_dynamic_rates(date(2024, 1, 1), date(2024, 1, 2), "XXX")