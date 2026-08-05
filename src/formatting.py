# -*- coding: utf-8 -*-
"""Formátovanie čísiel v slovenskom zápise.

Vlastný modul preto, že formátovanie potrebuje aj report.py (tabuľky), aj
charts.py (texty v hover). Bez toho by jeden musel importovať druhý.
"""

import pandas as pd

THOUSANDS_SEPARATOR = "\u00a0"
DECIMAL_SEPARATOR = ","
MISSING_VALUE = "—"


def format_number(value, decimals=0):
    """Číslo s medzerou ako oddeľovačom tisícov a čiarkou pred desatinami."""
    if value is None or pd.isna(value):
        return MISSING_VALUE
    text = f"{value:,.{decimals}f}"
    return text.replace(",", THOUSANDS_SEPARATOR).replace(".", DECIMAL_SEPARATOR)


def format_eur(value, decimals=0):
    if value is None or pd.isna(value):
        return MISSING_VALUE
    return format_number(value, decimals) + "\u00a0€"


def format_pct(value, decimals=1):
    if value is None or pd.isna(value):
        return MISSING_VALUE
    return format_number(value, decimals) + "\u00a0%"


def format_signed_eur(value):
    if value is None or pd.isna(value):
        return MISSING_VALUE
    prefix = "+" if value > 0 else "-"
    return prefix + format_eur(value)


def format_signed_pct(value, decimals=1):
    if value is None or pd.isna(value):
        return MISSING_VALUE
    prefix = "+" if value > 0 else "-"
    return prefix + format_pct(value, decimals)
