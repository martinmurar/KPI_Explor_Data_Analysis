# -*- coding: utf-8 -*-
"""Objednávky, na ktoré bol vystavený dobropis, a príčiny z Slacku.

Jediná časť reportu, ktorá nestojí na exporte objednávok. Vstupom sú dva CSV
súbory: zoznam objednávok s dobropisom a ručná anotácia z Slacku. Anotácia je
manuálna práca — ak sa k objednávke v Slacku nič nenašlo, neznamená to, že
problém nebol, len že sa o ňom nepísalo.
"""

import pandas as pd

from src.common import constants as C


def load_credit_memos():
    """Objednávky s dobropisom, spojené s anotáciou z Slacku."""
    orders = pd.read_csv(C.CREDIT_MEMO_CSV, dtype={"order_number": str})
    notes = pd.read_csv(C.CREDIT_MEMO_NOTES_CSV, dtype={"order_number": str})

    memos = orders.merge(notes, on="order_number", how="left", validate="one_to_one")
    _check_annotations(memos)

    memos["order_date"] = pd.to_datetime(memos["order_date"])
    memos["note"] = memos["note"].fillna("")
    memos["slack_link"] = memos["slack_link"].fillna("")
    memos["label"] = memos["company_name"].fillna(memos["customer_name"])
    return memos.sort_values("gmv", ascending=False)


def _check_annotations(memos):
    """Overí, že každá objednávka má známu kategóriu.

    Chýbajúca alebo preklepnutá kategória by inak z grafu ticho vypadla —
    súčty by nesedeli a nikto by si to nevšimol.
    """
    missing = memos.loc[memos["category"].isna(), "order_number"]
    if len(missing):
        raise ValueError(f"objednávky bez anotácie: {list(missing)}")

    unknown = set(memos["category"]) - set(C.CREDIT_MEMO_CATEGORIES)
    if unknown:
        raise ValueError(f"neznáme kategórie príčin: {sorted(unknown)}")


def causes(memos):
    """Počet objednávok, GMV a výška dobropisu podľa príčiny."""
    grouped = memos.groupby("category").agg(
        orders=("order_number", "size"),
        gmv=("gmv", "sum"),
        refund=("total_refund", "sum"),
    )
    grouped = grouped.reindex(C.CREDIT_MEMO_CATEGORIES).fillna(0)
    grouped["orders"] = grouped["orders"].astype(int)
    grouped["refund_pct"] = grouped["refund"] / grouped["gmv"] * 100
    return grouped


def explained(causes_table):
    """Riadky s naozaj zistenou príčinou.

    Bez skupín „bez zmienky“ a „nerelevantné“ — tie nie sú príčinou, len
    hranicou toho, čo sa dalo zistiť.
    """
    excluded = [C.CREDIT_MEMO_NO_TRACE, C.CREDIT_MEMO_IRRELEVANT]
    return causes_table.drop(index=excluded)


def outside_single_orders(memos, single_orders):
    """Objednávky zo zoznamu, ktoré dnes medzi jednorazovými už nie sú.

    Zoznam vznikol nad datasetom spred filtra na zrušené objednávky. Zákazník,
    ktorého jediná objednávka bola zrušená, dnes v dátach nie je vôbec, takže
    jeho objednávka v aktuálnej skupine jednorazových chýba.
    """
    return memos.loc[~memos["order_number"].isin(single_orders["increment_id"])]
