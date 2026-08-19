# -*- coding: utf-8 -*-
"""Objednávky, na ktoré bol vystavený dobropis, a zistené príčiny.

Jediná časť reportu, ktorá nestojí na exporte objednávok. Vstupom sú dva CSV
súbory: zoznam objednávok s dobropisom a ručná anotácia. Príčina sa hľadá
v Slacku a v LaDesku; anotácia je manuálna práca — ak sa k objednávke nič
nenašlo, neznamená to, že problém nebol, len že po ňom nezostala stopa.
"""

import pandas as pd

from src.common import constants as C


def load_credit_memos(df):
    """Objednávky s dobropisom, spojené s anotáciou z Slacku.

    Zrušené objednávky sa vyhadzujú. Zoznam vznikol nad exportom, ktorý ešte
    obsahoval `canceled`, takže sú v ňom aj objednávky, ktoré nikdy nevznikli —
    dobropis na ne síce bol vystavený, ale ako dôvod odchodu zákazníka nič
    nehovoria. Test je príslušnosť do už očisteného datasetu objednávok.
    """
    orders = pd.read_csv(C.CREDIT_MEMO_CSV, dtype={"order_number": str})
    notes = pd.read_csv(C.CREDIT_MEMO_NOTES_CSV, dtype={"order_number": str})

    memos = orders.merge(notes, on="order_number", how="left", validate="one_to_one")
    _check_annotations(memos)
    memos = memos.loc[memos["order_number"].isin(df["increment_id"])]

    memos["order_date"] = pd.to_datetime(memos["order_date"])
    memos["note"] = memos["note"].fillna("")
    memos["link"] = memos["link"].fillna("")
    memos["source"] = [link_source(link) for link in memos["link"]]
    memos["label"] = memos["company_name"].fillna(memos["customer_name"])
    return memos.sort_values("gmv", ascending=False)


def link_source(link):
    """Z odkazu odvodí, odkiaľ zistenie je. Prázdny odkaz nemá zdroj.

    Zdroj sa nezapisuje do CSV zvlášť — je v adrese a ručne vypĺňať dve polia,
    ktoré si musia navzájom sedieť, je len príležitosť na preklep.
    """
    if not link:
        return ""
    return C.SLACK_SOURCE if C.SLACK_DOMAIN in link else C.LADESK_SOURCE


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
    grouped = grouped.loc[grouped["orders"] > 0]
    grouped["refund_pct"] = grouped["refund"] / grouped["gmv"] * 100
    return grouped


def explained(causes_table):
    """Riadky s naozaj zistenou príčinou.

    Bez skupín „bez zmienky“ a „nerelevantné“ — tie nie sú príčinou, len
    hranicou toho, čo sa dalo zistiť.
    """
    excluded = [C.CREDIT_MEMO_NO_TRACE, C.CREDIT_MEMO_IRRELEVANT]
    return causes_table.drop(index=excluded, errors="ignore")

