# -*- coding: utf-8 -*-
"""Churn, reaktivácia a frekvencia objednávania.

Definícia churnu použitá všade v tomto module:
    Zákazník je v časovom bode t churned, ak od jeho poslednej objednávky
    (uskutočnenej do t) prešlo viac ako N mesiacov. Budúce objednávky sa
    neberú do úvahy — ak churned zákazník objedná o mesiac, v bode t je
    aj tak churned.

Menovateľ churn krivky = zákazníci akvirovaní aspoň N mesiacov pred t.
Kto nakúpil prvýkrát neskôr, nemal šancu odísť a do bázy nepatrí.
"""

import pandas as pd

from src import constants as C
import data
import metrics_bridge


# ── churn v čase ──────────────────────────────────────────────────────────────
def churn_curve(df, threshold_months):
    """Podiel churned zákazníkov na konci každého mesiaca."""
    rows = []
    for month_end in _month_ends(df):
        rows.append(_churn_at(df, month_end, threshold_months))
    return pd.DataFrame(rows).set_index("date")


def _month_ends(df):
    """Konce mesiacov od začiatku churn krivky do dátumu AS_OF."""
    return pd.date_range(start=C.CHURN_CURVE_START, end=C.AS_OF, freq="ME")


def _churn_at(df, as_of, threshold_months, churn_limit_months=None):
    """Churn v jednom časovom bode."""
    cutoff = as_of - pd.DateOffset(months=threshold_months)

    # df_limited limits how far into the past we consider churned customers - churn_limit_months = 24 means that if
    # the customer was inactive for more than 24 months, they won't be taken into account

    df_limited = df
    if churn_limit_months is not None:
        df_limited = df.copy()
        df_limited = df_limited[df_limited["created_at"] >= as_of - pd.DateOffset(months=churn_limit_months)]

    first_orders = data.first_order_per_customer(df)
    last_orders = data.last_order_per_customer(df_limited, as_of=as_of)

    # Do bázy patria len zákazníci, ktorí mali šancu odísť.
    in_base = first_orders.loc[first_orders <= cutoff].index
    base_last_orders = last_orders.reindex(in_base).dropna()

    churned = base_last_orders.loc[base_last_orders < cutoff]
    if len(base_last_orders) == 0:
        churn_pct = float("nan")
    else:
        churn_pct = len(churned) / len(base_last_orders) * 100

    return {
        "date": as_of,
        "base": len(base_last_orders),
        "churned": len(churned),
        "churn_pct": churn_pct,
    }


def churn_curves(df):
    """Churn krivky pre všetky prahy, spojené do jednej tabuľky."""
    result = pd.DataFrame()
    for threshold in C.CHURN_THRESHOLDS_MONTHS:
        curve = churn_curve(df, threshold)
        result[f"churn_{threshold}m"] = curve["churn_pct"]
        result[f"base_{threshold}m"] = curve["base"]
    return result


# ── churn podľa veľkostného pásma ─────────────────────────────────────────────
def churn_by_band(df):
    """Churn k dátumu AS_OF podľa veľkostného pásma zákazníka.

    Veľkosť sa meria za obdobie PRED oknom, v ktorom mohol zákazník odísť —
    inak by churned zákazníci mali automaticky nulové GMV a pásmo by nemalo zmysel.
    """
    cutoff = C.AS_OF - pd.DateOffset(months=C.CHURN_MAIN_THRESHOLD_MONTHS)
    size_start = cutoff - pd.DateOffset(months=C.CHURN_BAND_LOOKBACK_MONTHS)

    size_gmv = data.gmv_per_customer(df, size_start, cutoff)
    size_gmv = size_gmv.loc[size_gmv > 0]

    last_orders = data.last_order_per_customer(df, as_of=C.AS_OF)
    table = pd.DataFrame({"size_gmv": size_gmv})
    table["last_order"] = last_orders.reindex(table.index)
    table["is_churned"] = table["last_order"] < cutoff
    table["band"] = data.assign_bands(table["size_gmv"], C.BAND_EDGES, C.BAND_LABELS)

    return _summarise_churn_bands(table)


def _summarise_churn_bands(table):
    """Zhrnie churn po pásmach."""
    rows = []
    for band in C.BAND_LABELS:
        members = table.loc[table["band"] == band]
        if len(members) == 0:
            continue
        churned = members.loc[members["is_churned"]]
        rows.append({
            "band": band,
            "customers": len(members),
            "churned": len(churned),
            "churn_pct": len(churned) / len(members) * 100,
            "gmv_at_risk": churned["size_gmv"].sum(),
            "gmv_total": members["size_gmv"].sum(),
        })

    result = pd.DataFrame(rows).set_index("band")
    result["gmv_churn_pct"] = result["gmv_at_risk"] / result["gmv_total"] * 100
    return result


# ── rast a netto GMV podľa pásma ──────────────────────────────────────────────
def _customers_by_band(df):
    """Zákazníci aktívni v porovnávacom období (3 mesiace YoY), so zaradením do GMV pásma."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.GMV_WINDOW_MONTHS)
    comparison = metrics_bridge.customer_comparison(df, start, end)

    # Do pásiem patria len zákazníci, ktorí boli aktívni v porovnávacom období.
    active_before = comparison.loc[comparison["previous"] > 0].copy()
    active_before["band"] = data.assign_bands(active_before["previous"], C.BAND_EDGES, C.BAND_LABELS)
    return active_before


def growth_by_band(df):
    """Podiel rastúcich zákazníkov a netto zmena GMV podľa pásma, 3 mesiace YoY."""
    return _summarise_growth_bands(_customers_by_band(df))


def top_band_customers(df):
    """Zákazníci v najvyššom GMV pásme, zoradení od najväčšieho po najmenšie.

    Rovnaké zaradenie do pásma ako growth_by_band, len bez agregácie — potrebné
    na dohľadanie mien firiem pre úvodný komentár.
    """
    customers = _customers_by_band(df)
    top_label = C.BAND_LABELS[-1]
    return customers.loc[customers["band"] == top_label].sort_values("previous", ascending=False)


def _summarise_growth_bands(table):
    """Zhrnie rast po pásmach."""
    rows = []
    for band in C.BAND_LABELS:
        members = table.loc[table["band"] == band]
        if len(members) == 0:
            continue
        growing = members.loc[members["current"] > members["previous"]]
        rows.append({
            "band": band,
            "customers": len(members),
            "growing_pct": len(growing) / len(members) * 100,
            "previous_gmv": members["previous"].sum(),
            "current_gmv": members["current"].sum(),
            "net_delta": members["delta"].sum(),
            "median_change_pct": _median_change_pct(members),
        })
    return pd.DataFrame(rows).set_index("band")


def _median_change_pct(members):
    """Mediánová percentuálna zmena GMV na zákazníka."""
    change = (members["current"] / members["previous"] - 1) * 100
    return change.median()


# ── zákazníci s jednou objednávkou ────────────────────────────────────────────
def single_order_share(df):
    """Podiel zákazníkov s jedinou objednávkou za život, podľa akvizičnej kohorty."""
    per_customer = df.groupby("cust").agg(
        orders=("gmv", "size"),
        gmv=("gmv", "sum"),
        cohort_year=("cohort_year", "min"),
        first_order=("first_order", "min"),
    )

    rows = []
    for year in data.trend_years(df):
        members = per_customer.loc[per_customer["cohort_year"] == year]
        if len(members) == 0:
            continue
        single = members.loc[members["orders"] == 1]
        rows.append({
            "cohort_year": year,
            "label": data.year_label(year),
            "customers": len(members),
            "single_order_pct": len(single) / len(members) * 100,
            "median_orders": members["orders"].median(),
            "median_ltv": members["gmv"].median(),
            "is_immature": year == C.PARTIAL_YEAR,
        })
    return pd.DataFrame(rows).set_index("cohort_year")


# ── reaktivácie ───────────────────────────────────────────────────────────────
def reactivation_events(df):
    """Objednávky, ktoré nasledujú po medzere dlhšej ako REACTIVATION_GAP_MONTHS."""
    ordered = df.sort_values(["cust", "created_at"]).copy()
    ordered["previous_order"] = ordered.groupby("cust")["created_at"].shift(1)

    gap_cutoff = ordered["created_at"] - pd.DateOffset(months=C.REACTIVATION_GAP_MONTHS)
    is_reactivation = ordered["previous_order"].notna() & (ordered["previous_order"] < gap_cutoff)

    return ordered.loc[is_reactivation, ["cust", "created_at", "gmv", "previous_order"]]


def reactivation_counts(df):
    """Počet reaktivácií za život každého zákazníka (vrátane nuly)."""
    events = reactivation_events(df)
    counts = events.groupby("cust").size()
    all_customers = pd.Index(df["cust"].unique(), name="cust")
    return counts.reindex(all_customers, fill_value=0)


def reactivation_histogram(df):
    """Rozdelenie zákazníkov podľa počtu reaktivácií."""
    counts = reactivation_counts(df)
    # Zaujímajú nás len zákazníci, ktorí mali aspoň dve objednávky —
    # zákazník s jedinou objednávkou nemá ako byť reaktivovaný.
    orders_per_customer = df.groupby("cust").size()
    eligible = counts.loc[orders_per_customer >= 2]

    rows = []
    for index, label in enumerate(C.REACTIVATION_LABELS):
        is_last = index == len(C.REACTIVATION_LABELS) - 1
        if is_last:
            members = eligible.loc[eligible >= index]
        else:
            members = eligible.loc[eligible == index]
        rows.append({
            "reactivations": label,
            "customers": len(members),
            "share_pct": len(members) / len(eligible) * 100,
        })
    return pd.DataFrame(rows).set_index("reactivations")


def repeat_reactivation_by_year(df):
    """Koľko reaktivácií za rok a aký podiel z nich sú opakovaní reaktivanti.

    Odpovedá na otázku, či sa v reaktiváciách netočia stále tí istí zákazníci.
    """
    events = reactivation_events(df).sort_values("created_at").copy()
    events["event_number"] = events.groupby("cust").cumcount() + 1
    events["year"] = events["created_at"].dt.year

    rows = []
    for year in data.trend_years(df):
        year_events = events.loc[events["year"] == year]
        if len(year_events) == 0:
            continue
        repeat = year_events.loc[year_events["event_number"] >= 2]
        rows.append({
            "year": year,
            "label": data.year_label(year),
            "events": len(year_events),
            "customers": year_events["cust"].nunique(),
            "repeat_events": len(repeat),
            "repeat_pct": len(repeat) / len(year_events) * 100,
            "gmv": year_events["gmv"].sum(),
        })
    return pd.DataFrame(rows).set_index("year")


def reactivation_value(df):
    """Porovná hodnotu opakovane reaktivovaných zákazníkov so stabilnými."""
    counts = reactivation_counts(df)
    per_customer = df.groupby("cust").agg(orders=("gmv", "size"), gmv=("gmv", "sum"))
    per_customer["reactivations"] = counts

    repeat = per_customer.loc[per_customer["reactivations"] >= 2]
    once = per_customer.loc[per_customer["reactivations"] == 1]
    stable = per_customer.loc[(per_customer["reactivations"] == 0) & (per_customer["orders"] >= 2)]

    rows = []
    for label, group in [("stabilní (0 reaktivácií)", stable),
                         ("1 reaktivácia", once),
                         ("2+ reaktivácie", repeat)]:
        rows.append({
            "group": label,
            "customers": len(group),
            "median_orders": group["orders"].median(),
            "median_ltv": group["gmv"].median(),
            "total_gmv": group["gmv"].sum(),
        })
    return pd.DataFrame(rows).set_index("group")


# ── frekvencia objednávania ───────────────────────────────────────────────────
def orders_per_customer_last_year(df):
    """Počet objednávok každého zákazníka za okno frekvencie."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    window = data.orders_in_window(df, start, end)
    return window.groupby("cust").size()


def frequency_histogram(df):
    """Histogram frekvencie: počet zákazníkov pre každý počet objednávok.

    Menovateľom sú len zákazníci s aspoň jednou objednávkou v okne, takže
    koše idú od 1. Posledný kôš zlučuje FREQUENCY_TOP_BUCKET a vyššie.
    Stĺpec customers_at_or_above je reverzný kumulatív — počet zákazníkov
    s danou frekvenciou a vyššou.
    """
    counts = orders_per_customer_last_year(df)
    total = len(counts)

    rows = []
    for orders in range(C.FREQUENCY_FIRST_BUCKET, C.FREQUENCY_TOP_BUCKET):
        rows.append(_frequency_row(str(orders), (counts == orders).sum(), orders, counts, total))

    top_label = f"{C.FREQUENCY_TOP_BUCKET}+"
    top_count = (counts >= C.FREQUENCY_TOP_BUCKET).sum()
    rows.append(_frequency_row(top_label, top_count, C.FREQUENCY_TOP_BUCKET, counts, total))

    return pd.DataFrame(rows).set_index("orders")


def _frequency_row(label, customers, threshold, counts, total):
    """Jeden riadok histogramu frekvencie vrátane reverzného kumulatívu."""
    at_or_above = int((counts >= threshold).sum())
    return {
        "orders": label,
        "order_count": threshold,
        "customers": int(customers),
        "share_pct": int(customers) / total * 100,
        "customers_at_or_above": at_or_above,
        "share_at_or_above_pct": at_or_above / total * 100,
    }


def max_frequency(df):
    """Najvyššia frekvencia objednávania v okne."""
    return int(orders_per_customer_last_year(df).max())
