# -*- coding: utf-8 -*-
"""Churn, reaktivácia a frekvencia objednávania.

Definícia churnu použitá všade v tomto module:
    Zákazník je v časovom bode t churned, ak od jeho poslednej objednávky
    (uskutočnenej do t) prešlo viac ako N mesiacov. Budúce objednávky sa
    neberú do úvahy — ak churned zákazník objedná o mesiac, v bode t je
    aj tak churned.

Churn krivka sa počíta zo zákazníkov akvirovaných aspoň N mesiacov pred t.
Kto nakúpil prvýkrát neskôr, nemal šancu odísť a do bázy nepatrí.

Do bázy zároveň patrí len účet, ktorý nakúpil v zobrazovanom období — viď
_accounts_active_in_period.
"""

import pandas as pd

from src.common import constants as C
from src.common import data
from src.common import metrics_bridge


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


def _accounts_active_in_period(df):
    """Účty, ktoré od C.CHURN_CURVE_START aspoň raz nakúpili.

    Bez tejto podmienky by v báze navždy zostávali účty, ktoré naposledy
    nakúpili v rokoch 2018–2023. Sú churnuté v každom bode krivky, takže by
    churn stúpal len tým, že sa báza plní účtami, ktoré už nikdy neobjednajú —
    k 31. 7. 2026 by to bolo 74,3 % namiesto 59,8 %, a z toho 1 217 z 2 509
    churnutých účtov by boli účty spred zobrazovaného obdobia.
    """
    return set(df.loc[df["created_at"] >= C.CHURN_CURVE_START, "cust"])


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

    # Do bázy patria len zákazníci, ktorí mali šancu odísť a zároveň patria do
    # zobrazovaného obdobia.
    had_chance_to_leave = first_orders <= cutoff
    is_in_period = first_orders.index.isin(_accounts_active_in_period(df))
    in_base = first_orders.loc[had_chance_to_leave & is_in_period].index
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
# ── rast a netto GMV podľa pásma ──────────────────────────────────────────────
def _customers_by_band(df):
    """Zákazníci v porovnávacom období so zaradením do GMV pásma.

    Dve podmienky, rovnaké ako v account growth KPI, aby boli obe sekcie
    o tej istej populácii:
      - účet bol aktívny v porovnávacom (staršom) okne — inak ho niet kam zaradiť,
      - účet je starší ako C.ACCOUNT_GROWTH_MIN_AGE_MONTHS, teda mal k dispozícii
        celé porovnávacie okno.

    Vekový prah sa berie z konštanty account growth zámerne — je to tá istá
    hodnota z toho istého dôvodu (12 + GMV_WINDOW_MONTHS) a duplikovať ju by
    znamenalo riskovať, že sa raz rozídu.
    """
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.GMV_WINDOW_MONTHS)
    comparison = metrics_bridge.customer_comparison(df, start, end)
    age_cutoff = C.AS_OF - pd.DateOffset(months=C.ACCOUNT_GROWTH_MIN_AGE_MONTHS)

    is_active_before = comparison["previous"] > 0
    is_mature = comparison["first_order"] <= age_cutoff
    active_before = comparison.loc[is_active_before & is_mature].copy()
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


def band_window():
    """Obe okná, na ktorých stoja veľkostné pásma.

    Vracia aj koncové dni (nie exkluzívnu hranicu), aby sa dali priamo vypísať
    v popise grafu.
    """
    current_start, current_end = metrics_bridge.gmv_window(C.AS_OF, C.GMV_WINDOW_MONTHS)
    year = pd.DateOffset(years=1)
    last_day = pd.Timedelta(days=1)
    return {
        "current_start": current_start,
        "current_end": current_end - last_day,
        "previous_start": current_start - year,
        "previous_end": current_end - year - last_day,
    }


def top_band_detail(df):
    """Účty v najvyššom pásme s ich GMV v oboch oknách, od najväčšieho prírastku.

    Zákazník bez vyplneného company_bill sa v tabuľke zobrazí ako e-mail.
    """
    customers = top_band_customers(df)
    names = data.company_names(df)

    accounts = []
    for cust in customers.index:
        accounts.append(names.get(cust, cust))

    table = pd.DataFrame({
        "account": accounts,
        "previous": customers["previous"].values,
        "current": customers["current"].values,
        "delta": customers["delta"].values,
    })
    return table.sort_values("delta", ascending=False).set_index("account")
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
# ── frekvencia objednávania ───────────────────────────────────────────────────
def orders_per_customer_last_year(df):
    """Počet objednávok každého zákazníka za okno frekvencie."""
    return _frequency_window_orders(df).groupby("cust").size()


def gmv_per_customer_last_year(df):
    """GMV každého zákazníka za okno frekvencie."""
    return _frequency_window_orders(df).groupby("cust")["gmv"].sum()


def _frequency_window_orders(df):
    """Objednávky v okne, za ktoré sa meria frekvencia."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    return data.orders_in_window(df, start, end)


def frequency_window():
    """Okno, za ktoré sa meria frekvencia, aj s koncovým dňom pre výpis."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    return {"start": start, "end": end - pd.Timedelta(days=1)}


def frequency_histogram(df):
    """Histogram frekvencie: počet zákazníkov pre každý počet objednávok.

    Zahrnutí sú len zákazníci s aspoň jednou objednávkou v okne, takže
    koše idú od 1. Posledný kôš zlučuje FREQUENCY_TOP_BUCKET a vyššie.
    Stĺpce s príponou _at_or_above sú reverzný kumulatív — počet zákazníkov
    a podiel GMV pri danej frekvencii a vyššej.
    """
    counts = orders_per_customer_last_year(df)
    gmv = gmv_per_customer_last_year(df).reindex(counts.index)

    rows = []
    for orders in range(C.FREQUENCY_FIRST_BUCKET, C.FREQUENCY_TOP_BUCKET):
        rows.append(_frequency_row(str(orders), orders, counts, gmv))

    top_label = f"{C.FREQUENCY_TOP_BUCKET}+"
    rows.append(_frequency_row(top_label, C.FREQUENCY_TOP_BUCKET, counts, gmv, is_top=True))

    return pd.DataFrame(rows).set_index("orders")


def _frequency_row(label, threshold, counts, gmv, is_top=False):
    """Jeden riadok histogramu frekvencie vrátane reverzného kumulatívu."""
    if is_top:
        in_bucket = counts >= threshold
    else:
        in_bucket = counts == threshold
    at_or_above = counts >= threshold

    return {
        "orders": label,
        "order_count": threshold,
        "customers": int(in_bucket.sum()),
        "share_pct": in_bucket.sum() / len(counts) * 100,
        "customers_at_or_above": int(at_or_above.sum()),
        "share_at_or_above_pct": at_or_above.sum() / len(counts) * 100,
        "gmv_share_at_or_above_pct": gmv.loc[at_or_above].sum() / gmv.sum() * 100,
    }