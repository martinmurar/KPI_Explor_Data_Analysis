# -*- coding: utf-8 -*-
"""Skupiny objednávok, pre ktoré sa rozoberajú nakúpené produkty.

Každá skupina je len tri veci: názov, cesta k odloženej cache a funkcia, ktorá
z exportu objednávok vyberie jej čísla objednávok. Pridať štvrtú skupinu (napr.
churnuté účty) znamená dopísať sem jeden záznam — načítavač aj sekcia reportu
zostanú nedotknuté.
"""

import pandas as pd

from src.common import constants as C
from src.common import metrics_kpi_diagnostics

SINGLE = "single"
REGULAR = "regular"
ALL = "all"


def items_start():
    """Prvý deň obdobia sekcie „Čo kto nakupuje“. None znamená celú históriu."""
    if C.ORDER_ITEMS_START_YEAR is None:
        return None
    return pd.Timestamp(year=C.ORDER_ITEMS_START_YEAR, month=1, day=1)


def period_note():
    """Obdobie sekcie do popisu grafu alebo textu."""
    if C.ORDER_ITEMS_START_YEAR is None:
        return "celá história objednávok"
    return f"objednávky od roku {C.ORDER_ITEMS_START_YEAR}"


def _in_period(df):
    """Objednávky, ktoré spadajú do obdobia sekcie."""
    start = items_start()
    if start is None:
        return df
    return df.loc[df["created_at"] >= start]


def single_order_numbers(df):
    """Objednávky zákazníkov, ktorí za celý život objednali práve raz.

    Podmienka „práve raz“ platí nad celou históriou; obdobie sekcie len
    rozhoduje, ktoré z tých objednávok sa do rozboru dostanú. Účet, ktorý svoju
    jedinú objednávku urobil skôr, teda zo skupiny vypadne celý.
    """
    single = metrics_kpi_diagnostics.single_order_accounts(df)
    return _in_period(single)["increment_id"]


def regular_order_numbers(df):
    """Objednávky bežných zákazníkov v období sekcie.

    Bežný zákazník je tu ten, ktorý za život objednal viac než raz — teda
    priamy protipól jednorazovej skupiny. Obmedzenie na posledné roky nie je
    kozmetické: sortiment sa mení a porovnávať dnešný nákup s tým z roku 2019
    by nedávalo zmysel.
    """
    orders_per_customer = df.groupby("cust").size()
    repeat = orders_per_customer.index[orders_per_customer > 1]
    return _in_period(df.loc[df["cust"].isin(repeat)])["increment_id"]


def all_order_numbers(df):
    """Všetky objednávky v očistenom datasete.

    Najširšia skupina — z jej cache sa dajú odvodiť všetky ostatné rezy bez
    ďalšieho prechodu 4 GB súborom. Používa ju report analýzy produktov.
    """
    return df["increment_id"]


GROUPS = {
    ALL: {
        "cache": C.ALL_ORDER_ITEMS_CSV,
        "numbers": all_order_numbers,
        "note": "všetky B2B objednávky",
    },
    SINGLE: {
        "cache": C.SINGLE_ORDER_ITEMS_CSV,
        "numbers": single_order_numbers,
        "note": (f"zákazníci s jedinou objednávkou za život, "
                 f"{period_note()}"),
    },
    REGULAR: {
        "cache": C.REGULAR_ORDER_ITEMS_CSV,
        "numbers": regular_order_numbers,
        "note": (f"zákazníci s viac než jednou objednávkou, "
                 f"{period_note()}"),
    },
}


def cache_path(group):
    """Kam sa odkladá výsledok filtrovania danej skupiny."""
    return GROUPS[group]["cache"]


def order_numbers(group, df):
    """Čísla objednávok danej skupiny."""
    return GROUPS[group]["numbers"](df)
