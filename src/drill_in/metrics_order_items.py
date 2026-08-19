# -*- coding: utf-8 -*-
"""Metriky nad položkami objednávok jednej skupiny zákazníkov.

Vstupom je odložená cache, ktorú vyrobí build_order_items.py. Report zdrojový
4 GB súbor nikdy nečíta — jeden prechod ním trvá jednotky minút a do generovania
reportu nepatrí. Ak cache neexistuje, sekcia sa nevykreslí a povie, čo spustiť.

Funkcie sú zámerne nezávislé od toho, o akú skupinu ide — tie isté rezy dávajú
zmysel pre jednorazových zákazníkov aj pre bežných.
"""

import os

import pandas as pd

from src.common import constants as C
from src.common import order_items


def by_sku(items):
    """Súčty za jednotlivé SKU, zoradené podľa GMV."""
    grouped = items.groupby("sku").agg(
        orders=("increment_id", "nunique"),
        qty=("qty", "sum"),
        gmv=("gmv", "sum"),
    )
    grouped["gmv_share_pct"] = grouped["gmv"] / grouped["gmv"].sum() * 100
    grouped["orders_share_pct"] = (grouped["orders"]
                                   / items["increment_id"].nunique() * 100)
    return with_labels(grouped.sort_values("gmv", ascending=False))


def basket_profile(items):
    """Ako vyzerá typický nákupný košík skupiny."""
    per_order = items.groupby("increment_id").agg(
        lines=("sku", "size"),
        units=("qty", "sum"),
        gmv=("gmv", "sum"),
    )
    return {
        "orders": len(per_order),
        "lines": len(items),
        "skus": items["sku"].nunique(),
        "median_lines": per_order["lines"].median(),
        "median_units": per_order["units"].median(),
        "median_gmv": per_order["gmv"].median(),
        "single_line_pct": (per_order["lines"] == 1).mean() * 100,
    }


def concentration(sku_totals):
    """Aký podiel GMV skupiny tvorí prvých N najsilnejších produktov."""
    total = sku_totals["gmv"].sum()

    rows = []
    for level in C.SINGLE_ORDER_ITEMS_LEVELS:
        if level > len(sku_totals):
            continue
        rows.append({
            "segment": f"Top {level} produktov",
            "gmv_share_pct": sku_totals["gmv"].head(level).sum() / total * 100,
        })
    return pd.DataFrame(rows).set_index("segment")


def displayed_skus(sku_totals, top=None):
    """SKU, ktoré sa v reporte naozaj zobrazia — zjednotenie oboch rebríčkov."""
    count = top or C.SINGLE_ORDER_ITEMS_TOP
    by_gmv = sku_totals.sort_values("gmv", ascending=False).head(count)
    by_orders = sku_totals.sort_values("orders", ascending=False).head(count)
    return sku_totals.loc[by_gmv.index.union(by_orders.index)]


# ── mapa SKU → názov produktu ─────────────────────────────────────────────────
def load_sku_names():
    """Mapa SKU → názov produktu. Chýbajúci súbor znamená prázdnu mapu."""
    if not os.path.exists(C.SKU_NAMES_CSV):
        return {}

    table = pd.read_csv(C.SKU_NAMES_CSV, dtype="string").fillna("")
    return dict(zip(table["sku"], table["name"]))


def with_labels(sku_totals):
    """Doplní plný názov produktu a jeho skrátenú podobu do grafu.

    label je to, čo sa ukáže v hover a v tabuľke, short_label to, čo sa vojde
    na os grafu. Ak produkt názov nemá, obe sú jeho kód — kód sa neskracuje,
    lebo by prestal identifikovať produkt.
    """
    names = load_sku_names()
    labelled = sku_totals.copy()

    labels, short_labels = [], []
    for sku in labelled.index:
        name = names.get(sku) or sku
        labels.append(name)
        short_labels.append(sku if name == sku else short_label(name))

    labelled["label"] = labels
    labelled["short_label"] = short_labels
    return labelled


def short_label(name, limit=None):
    """Skrátený názov produktu do grafu."""
    text = _without_noise(name)
    limit = limit or C.SKU_LABEL_MAX_CHARS
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip(" -") + "…"


def _without_noise(name):
    """Vyhodí z názvu časti, ktoré sú pri každom produkte rovnaké.

    Názov je členený pomlčkami (napr. "Zinok - GymBeam 00 - 90 tab"), takže sa
    čistí po častiach — časť, z ktorej po odstránení značky nič nezostane, sa
    zahodí celá.
    """
    parts = []
    for part in name.split(" - "):
        for token in C.SKU_LABEL_DROP:
            part = part.replace(token, "")
        part = " ".join(part.split())
        if part:
            parts.append(part)
    return " - ".join(parts) or name


def save_sku_names(names):
    """Zapíše mapu SKU → názov, zoradenú podľa SKU."""
    table = pd.DataFrame(sorted(names.items()), columns=["sku", "name"])
    table.to_csv(C.SKU_NAMES_CSV, index=False)
    return len(table), int((table["name"] == "").sum())


# ── cache ─────────────────────────────────────────────────────────────────────
def load_cached_items(cache_path):
    """Položky skupiny z odloženej cache, alebo None ak cache nie je."""
    return order_items.cached_items(cache_path)


def gift_sample_skus(items):
    """Kódy darčeka a vzorky, ktoré sa v položkách naozaj vyskytujú.

    Zoznam je pevný (C.GIFT_SAMPLE_SKUS), nehľadá sa podľa názvu — „+ darček“
    v názve má aj bežne predávaný tovar. Slúži len na spočítanie objednávok;
    z rebríčkov ani zo súčtov sa tieto produkty nevyhadzujú.
    """
    present = set(items["sku"].unique())
    return {sku for sku in C.GIFT_SAMPLE_SKUS if sku in present}


def gift_or_sample(items):
    """Koľko objednávok skupiny obsahovalo produkt darček alebo vzorku.

    Pri jednorazových zákazníkoch je objednávka a účet to isté, takže podiel
    objednávok je zároveň podielom účtov.
    """
    matching = gift_sample_skus(items)

    orders = items["increment_id"].nunique()
    with_gift = items.loc[items["sku"].isin(matching), "increment_id"].nunique()
    return {
        "products": len(matching),
        "orders": orders,
        "orders_with_gift": with_gift,
        "share_pct": with_gift / orders * 100 if orders else 0.0,
    }
