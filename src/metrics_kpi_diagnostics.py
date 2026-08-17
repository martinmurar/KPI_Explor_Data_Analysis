# -*- coding: utf-8 -*-
"""Diagnostika interného KPI account growth — prečo je nízke a čo ho posunie.

Tento modul nepočíta KPI, to robí metrics_account_growth. Odpovedá na inú
otázku: ktorá časť odstupu od cieľa je vlastnosť biznisu a ktorá je vlastnosť
definície metriky.

Všetko vychádza z jednej tabuľky metrics_account_growth.account_table, takže
každé číslo tu je konzistentné s tým, čo vykazuje hlavný report.

Scenáre v tomto module sú kontrafaktuálna aritmetika, nie prognózy. Ukazujú,
koľko priestoru v KPI leží v danom mechanizme, nie koľko sa z neho získa.
"""

import pandas as pd

from src import constants as C
import data
import metrics_bridge


# Popisky skupín podľa zmeny počtu objednávok. Poradie je od najlepšej.
FREQUENCY_MORE = "Viac objednávok"
FREQUENCY_SAME = "Rovnaký počet"
FREQUENCY_FEWER = "Menej objednávok"
FREQUENCY_ORDER = [FREQUENCY_MORE, FREQUENCY_SAME, FREQUENCY_FEWER]


# ── 1. frekvencia objednávok ──────────────────────────────────────────────────
def frequency_effect(table):
    """Podiel rastúcich podľa toho, či účet objednal viac/rovnako/menejkrát.

    Len účty aktívne v oboch oknách — pri účte, ktorý v jednom okne nenakúpil,
    je porovnanie počtu objednávok bezobsažné.
    """
    active = _active_in_both(table)
    groups = {
        FREQUENCY_MORE: active["current_orders"] > active["previous_orders"],
        FREQUENCY_SAME: active["current_orders"] == active["previous_orders"],
        FREQUENCY_FEWER: active["current_orders"] < active["previous_orders"],
    }

    rows = []
    for label in FREQUENCY_ORDER:
        rows.append(_frequency_row(label, active.loc[groups[label]]))
    return pd.DataFrame(rows).set_index("segment")


def _active_in_both(table):
    """Účty s nenulovým GMV v oboch oknách."""
    return table.loc[(table["previous"] > 0) & (table["current"] > 0)]


def kpi_by_order_count(table, df):
    """KPI počítané osobitne pre každý kôš podľa počtu objednávok za rok.

    Kôš určuje počet objednávok za posledných FREQUENCY_WINDOW_MONTHS mesiacov,
    teda za aktuálne obdobie. Kôš 0 preto vyjde nutne 0 % — kto za rok nenakúpil,
    nemá GMV ani v kratšom okne KPI a je automaticky klesajúci. Nie je to chyba
    rezu, ale jeho hlavný nález: ukazuje, koľko posudzovaných účtov je mŕtvych.
    """
    buckets = _orders_last_year(table, df).map(_order_count_bucket)

    rows = []
    for label in C.KPI_ORDER_COUNT_BUCKETS:
        members = table.loc[buckets == label]
        if len(members) == 0:
            continue
        rows.append(_frequency_row(label, members))
    return pd.DataFrame(rows).set_index("segment")


def _orders_last_year(table, df):
    """Počet objednávok každého posudzovaného účtu za posledný rok."""
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    window = data.orders_in_window(df, start, end)
    counts = window.groupby("cust").size()
    return counts.reindex(table.index).fillna(0).astype(int)


def _order_count_bucket(count):
    """Popisok koša pre daný počet objednávok.

    KPI_ORDER_COUNT_EDGES sú horné hranice prvých košov; čo sa do žiadnej
    nezmestí, patrí do posledného, otvoreného koša.
    """
    for edge, label in zip(C.KPI_ORDER_COUNT_EDGES, C.KPI_ORDER_COUNT_BUCKETS):
        if count <= edge:
            return label
    return C.KPI_ORDER_COUNT_BUCKETS[-1]


def _frequency_row(label, members):
    """Jeden riadok rezu: počet účtov, podiel rastúcich a netto zmena GMV."""
    return {
        "segment": label,
        "customers": len(members),
        "growing": int(members["growing"].sum()),
        "growing_pct": members["growing"].mean() * 100 if len(members) else float("nan"),
        "net_delta": members["current"].sum() - members["previous"].sum(),
    }


# ── 2. kedy účty naposledy nakúpili ───────────────────────────────────────────
def activity_split(table, df):
    """Všetky posudzované účty rozdelené podľa toho, kedy naposledy nakúpili.

    Churnutý je účet, ktorý nenakúpil KPI_DIAG_CHURN_DAYS dní. Prostredná
    skupina je jadro problému — sú to živé účty, ktoré len netrafili okno, a KPI
    ich aj tak počíta ako klesajúce.
    """
    groups = _activity_groups(table, df)

    rows = []
    for index, label in enumerate(C.KPI_DIAG_ACTIVITY_LABELS):
        members = table.loc[groups[label]]
        rows.append({
            "segment": label,
            "customers": len(members),
            "share_pct": len(members) / len(table) * 100,
            "growing_pct": members["growing"].mean() * 100 if len(members) else 0.0,
            "previous_gmv": members["previous"].sum(),
            "status": index,
        })
    return pd.DataFrame(rows).set_index("segment")


def _activity_groups(table, df):
    """Masky troch skupín posudzovaných účtov podľa poslednej objednávky."""
    in_window = table["current"] > 0
    alive = _alive_mask(table, df)
    return {
        C.KPI_DIAG_ACTIVITY_LABELS[0]: in_window,
        C.KPI_DIAG_ACTIVITY_LABELS[1]: ~in_window & alive,
        C.KPI_DIAG_ACTIVITY_LABELS[2]: ~in_window & ~alive,
    }


def _alive_mask(table, df):
    """Účty, ktoré nakúpili za posledných KPI_DIAG_CHURN_DAYS dní."""
    last_order = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(table.index)
    return last_order >= C.AS_OF - pd.Timedelta(days=C.KPI_DIAG_CHURN_DAYS)


def outside_window_accounts(table, df):
    """Živé účty, ktoré v aktuálnom okne nenakúpili."""
    return table.loc[(table["current"] == 0) & _alive_mask(table, df)]


def churned_accounts(table, df):
    """Churnuté účty medzi posudzovanými."""
    return table.loc[(table["current"] == 0) & ~_alive_mask(table, df)]


def regular_ordering_scenario(table, df):
    """KPI dnes vs KPI, keby živé účty objednávali aspoň raz za okno.

    Živý účet s nulovým GMV v aktuálnom okne sa v scenári počíta ako rastúci.
    Je to horná hranica — účet, ktorý začne objednávať, je rastúci len ak
    prekročí svoje minuloročné GMV, a všetky tieto účty ho majú nenulové.
    """
    converted = len(outside_window_accounts(table, df))
    scenario_growing = table["growing"].sum() + converted
    return _scenario_table(table, C.KPI_DIAG_REGULAR_LABELS,
                           scenario_growing, converted)


# ── 3. čo ak by sme zabránili churnu ──────────────────────────────────────────
def churn_prevented_sensitivity(table, df):
    """KPI, keby churnuté účty boli aktívne v okne, pri troch predpokladoch rastu.

    Skúša sa KPI_DIAG_CHURN_PROBABILITIES — od 0 (zachránený účet nikdy
    nerastie, teda dnešný stav) po 1 (rastie vždy). Nepoužíva sa náhodná
    simulácia, počíta sa priamo očakávaná hodnota.

    Posudzovaná skupina sa nemení — churnuté účty v nej už sú, mení sa len to, či sa
    počítajú ako rastúce.
    """
    prevented = len(churned_accounts(table, df))
    growing = table["growing"].sum()

    rows = []
    for probability in C.KPI_DIAG_CHURN_PROBABILITIES:
        rows.append({
            "segment": _probability_label(probability),
            "probability_pct": probability * 100,
            "customers": len(table),
            "growing_pct": (growing + prevented * probability) / len(table) * 100,
        })
    result = pd.DataFrame(rows).set_index("segment")
    result["prevented"] = prevented
    return result


def _probability_label(probability):
    """Popisok scenára podľa predpokladanej pravdepodobnosti rastu."""
    percent = int(round(probability * 100))
    if probability == 0:
        return f"{percent} % — dnešný stav"
    return f"{percent} % zachránených rastie"
def _scenario_table(table, labels, scenario_growing, converted):
    """Dvojriadková tabuľka: KPI dnes a KPI v scenári.

    Posudzovaná skupina sa v scenári nemení — účty v nej už sú, mení sa len
    to, či sa počítajú ako rastúce.
    """
    rows = [
        {"segment": labels[0],
         "customers": len(table),
         "growing_pct": table["growing"].mean() * 100},
        {"segment": labels[1],
         "customers": len(table),
         "growing_pct": scenario_growing / len(table) * 100},
    ]
    result = pd.DataFrame(rows).set_index("segment")
    result["converted"] = converted
    return result


# ── zhrnutie pre karty a text ─────────────────────────────────────────────────
def diagnostics_summary(table, df):
    """Čísla, na ktoré sa odvoláva text sekcií."""
    in_window = table.loc[table["current"] > 0]
    both = _active_in_both(table)

    return {
        "growing_pct": table["growing"].mean() * 100,
        "active_in_both_growing_pct": both["growing"].mean() * 100,
        "accounts": len(table),
        "growing": int(table["growing"].sum()),
        "gmv_growing_pct": table.loc[table["growing"], "current"].sum()
                           / table["current"].sum() * 100,
        "thin_pct": _thin_share(table),
        "in_window": len(in_window),
        "in_window_growing_pct": in_window["growing"].mean() * 100,
        "outside_window": len(outside_window_accounts(table, df)),
        "churned": len(churned_accounts(table, df)),
        "cannot_grow": len(table.loc[table["current"] == 0]),
    }


def _thin_share(table):
    """Podiel posudzovaných účtov s najviac KPI_DIAG_THIN_ORDERS objednávkami v oboch oknách."""
    limit = C.KPI_DIAG_THIN_ORDERS
    thin = table.loc[(table["previous_orders"] <= limit) & (table["current_orders"] <= limit)]
    return len(thin) / len(table) * 100


# ── účty vyradené filtrom spodných extrémov ───────────────────────────────────
# Popisky rozpadu vyradených účtov podľa aktivity za posledný rok.
DROPPED_DORMANT = "Bez objednávky za rok"
DROPPED_ACTIVE = "Aspoň jedna objednávka za rok"
DROPPED_ACTIVITY_ORDER = [DROPPED_DORMANT, DROPPED_ACTIVE]


def dropped_accounts(table, filtered_table, df):
    """Detail účtov, ktoré filter spodných extrémov vyradí z menovateľa KPI.

    Nie je to celý odfiltrovaný dataset — drvivá väčšina odfiltrovaných
    zákazníkov v menovateli nikdy nebola. Zaujímavé sú práve tie účty, ktoré
    v ňom boli a filtrom z neho vypadli, lebo len tie hýbu hodnotou KPI.

    „Za celý život“ znamená od začiatku dát, nie od C.DISPLAY_START_YEAR.
    """
    dropped = table.index.difference(filtered_table.index)
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    window = data.orders_in_window(df, start, end)
    names = data.company_names(df)

    detail = table.loc[dropped, ["country", "growing"]].copy()
    detail["name"] = [names.get(cust, cust) for cust in detail.index]
    detail["lifetime_gmv"] = df.groupby("cust")["gmv"].sum().reindex(dropped)
    detail["lifetime_orders"] = df.groupby("cust").size().reindex(dropped)
    detail["gmv_12m"] = window.groupby("cust")["gmv"].sum().reindex(dropped).fillna(0.0)
    detail["orders_12m"] = window.groupby("cust").size().reindex(dropped).fillna(0).astype(int)
    detail["last_order"] = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(dropped)
    return detail.sort_values("lifetime_gmv", ascending=False)


def dropped_activity_split(detail):
    """Vyradené účty rozdelené podľa aktivity za rok a podľa príznaku rastu.

    Rozdelenie ukazuje, prečo filter KPI nezdvihol: v jednej skupine sú samé
    klesajúce účty, v druhej prevažne rastúce, a filter vzal obe naraz.
    """
    dormant = detail.loc[detail["orders_12m"] == 0]
    active = detail.loc[detail["orders_12m"] > 0]

    rows = []
    for label, members in [(DROPPED_DORMANT, dormant), (DROPPED_ACTIVE, active)]:
        rows.append({
            "segment": label,
            "customers": len(members),
            "growing": int(members["growing"].sum()),
            "declining": int((~members["growing"]).sum()),
            "lifetime_gmv": members["lifetime_gmv"].sum(),
            "gmv_12m": members["gmv_12m"].sum(),
        })
    return pd.DataFrame(rows).set_index("segment")


def largest_account(table, df):
    """Najväčší posudzovaný účet podľa GMV za posledný rok.

    Slúži ako mierka pre vyradenú skupinu — bez porovnania s niečím známym je
    súčet za štyridsiatku drobných účtov len ďalšie číslo.
    """
    start, end = metrics_bridge.gmv_window(C.AS_OF, C.FREQUENCY_WINDOW_MONTHS)
    window = data.orders_in_window(df, start, end)
    gmv = window.groupby("cust")["gmv"].sum().reindex(table.index).fillna(0.0)
    cust = gmv.idxmax()
    names = data.company_names(df)
    return {"name": names.get(cust, cust), "gmv_12m": gmv.max()}


def dropped_by_country(detail):
    """Vyradené účty podľa krajiny, od najpočetnejšej."""
    counts = detail.groupby("country").size().sort_values(ascending=False)
    return counts.rename("customers").to_frame()


# ── zákazníci s jedinou objednávkou za život ──────────────────────────────────
def single_order_accounts(df):
    """Objednávky zákazníkov, ktorí za celý život objednali práve raz.

    Berú sa len tí, ktorých jediná objednávka je staršia ako
    SINGLE_ORDER_MIN_AGE_MONTHS — mladší zákazník ešte mal čas vrátiť sa
    a medzi stratených nepatrí.

    Keďže má každý z nich práve jednu objednávku, riadok objednávky je zároveň
    riadkom zákazníka a dá sa s ním ďalej pracovať priamo.
    """
    cutoff = C.AS_OF - pd.DateOffset(months=C.SINGLE_ORDER_MIN_AGE_MONTHS)
    orders_per_customer = df.groupby("cust").size()
    first_order = data.first_order_per_customer(df)

    is_single = orders_per_customer == 1
    is_mature = first_order < cutoff
    accounts = orders_per_customer.index[is_single & is_mature]
    return df.loc[df["cust"].isin(accounts)].copy()


def repeat_first_orders(df):
    """Prvé objednávky zákazníkov, ktorí sa neskôr vrátili.

    Porovnávacia skupina k single_order_accounts: rovnaká udalosť (prvý nákup),
    rovnaké obmedzenie veku, iný osud zákazníka.
    """
    cutoff = C.AS_OF - pd.DateOffset(months=C.SINGLE_ORDER_MIN_AGE_MONTHS)
    orders_per_customer = df.groupby("cust").size()
    repeat = orders_per_customer.index[orders_per_customer > 1]

    first = df.loc[df["cust"].isin(repeat)].sort_values("created_at")
    first = first.drop_duplicates("cust")
    return first.loc[first["created_at"] < cutoff]


def order_value_mix(single, repeat_first):
    """Rozdelenie hodnoty prvej objednávky v oboch skupinách, v percentách.

    Percentá, nie počty — skupiny sú rôzne veľké a v absolútnych číslach by sa
    tvary rozdelení nedali porovnať.
    """
    rows = []
    for label in C.ORDER_VALUE_BUCKETS:
        rows.append({
            "segment": label,
            "single_pct": _value_bucket_share(single, label),
            "repeat_pct": _value_bucket_share(repeat_first, label),
            "customers": int(_value_bucket_mask(single, label).sum()),
            "gmv": single.loc[_value_bucket_mask(single, label), "gmv"].sum(),
        })
    return pd.DataFrame(rows).set_index("segment")


def _value_bucket_mask(orders, label):
    """Maska objednávok patriacich do koša hodnoty."""
    position = C.ORDER_VALUE_BUCKETS.index(label)
    low = C.ORDER_VALUE_EDGES[position - 1] if position > 0 else 0.0
    if position < len(C.ORDER_VALUE_EDGES):
        return (orders["gmv"] >= low) & (orders["gmv"] < C.ORDER_VALUE_EDGES[position])
    return orders["gmv"] >= low


def _value_bucket_share(orders, label):
    """Podiel objednávok v koši hodnoty."""
    return _value_bucket_mask(orders, label).mean() * 100


def single_order_by_year(single):
    """Zákazníci s jedinou objednávkou podľa roku tej objednávky."""
    grouped = single.groupby("year").agg(customers=("cust", "size"), gmv=("gmv", "sum"))
    return grouped.sort_index()


# ── účty, ktoré odišli do nuly ────────────────────────────────────────────────
def dropped_to_zero_accounts(table, df):
    """Účty s nenulovým GMV v minuloročnom okne a nulovým v aktuálnom.

    V rozklade menovateľa je to skupina COMPOSITION_DROPPED. Sú to zabehnutí
    odberatelia, nie drobní jednorázoví zákazníci — preto stojí za to pozrieť
    sa na ne menovite.
    """
    accounts = table.loc[(table["previous"] > 0) & (table["current"] == 0)].copy()
    names = data.company_names(df)

    accounts["name"] = [names.get(cust, cust) for cust in accounts.index]
    accounts["lifetime_gmv"] = df.groupby("cust")["gmv"].sum().reindex(accounts.index)
    accounts["lifetime_orders"] = df.groupby("cust").size().reindex(accounts.index)
    accounts["last_order"] = data.last_order_per_customer(df, as_of=C.AS_OF).reindex(accounts.index)
    accounts["months_silent"] = ((C.AS_OF - accounts["last_order"]).dt.days / 30.44).round(1)
    accounts["mean_order"] = df.groupby("cust")["gmv"].mean().reindex(accounts.index)
    accounts["median_order"] = df.groupby("cust")["gmv"].median().reindex(accounts.index)
    accounts["orders_per_month"] = _orders_per_month(accounts, df)
    return accounts.sort_values("previous", ascending=False)


def _orders_per_month(accounts, df):
    """Priemerná frekvencia objednávok za celý život účtu.

    Vzťah sa meria od prvej po poslednú objednávku, nie po C.AS_OF — ticho po
    odchode nie je súčasťou toho, ako často účet nakupoval, kým nakupoval.
    Vzťah kratší než mesiac sa počíta ako mesiac, aby jednodňový účet nevyšiel
    ako extrémne frekventovaný.
    """
    first_order = data.first_order_per_customer(df).reindex(accounts.index)
    tenure_months = (accounts["last_order"] - first_order).dt.days / 30.44
    return accounts["lifetime_orders"] / tenure_months.clip(lower=1.0)


def last_order_cluster(accounts):
    """Počet odídených účtov podľa mesiaca ich poslednej objednávky.

    Zhluk v čase je najlacnejší test na spoločnú príčinu — ak účty prestali
    nakupovať naraz, ide skôr o udalosť na našej strane než o 220 nezávislých
    obchodných rozhodnutí.
    """
    grouped = accounts.groupby(accounts["last_order"].dt.to_period("M")).agg(
        customers=("previous", "size"),
        previous_gmv=("previous", "sum"),
    )
    months = pd.period_range(start=grouped.index.min(), end=grouped.index.max(), freq="M")
    return grouped.reindex(months, fill_value=0)


def monthly_gmv_by_account(df, accounts):
    """Mesačné GMV každého zadaného účtu, na spoločnej časovej osi."""
    return _monthly_by_account(df, accounts, "sum")


def monthly_orders_by_account(df, accounts):
    """Mesačný počet objednávok každého zadaného účtu, na spoločnej časovej osi."""
    return _monthly_by_account(df, accounts, "size").astype(int)


def _monthly_by_account(df, accounts, aggfunc):
    """Mesačný rez podľa účtu, na spoločnej časovej osi.

    Spoločná os je nutná — graf s prepínačom účtov prekresľuje len dáta, nie
    popisky, takže všetky série musia mať rovnakú dĺžku. Mesiace bez objednávky
    sú nuly, nie chýbajúce hodnoty, inak by v grafe vznikli diery.
    """
    start = pd.Timestamp(year=C.DISPLAY_START_YEAR, month=1, day=1)
    window = df.loc[(df["created_at"] >= start) & (df["cust"].isin(accounts))]

    months = pd.period_range(start=start, end=C.AS_OF, freq="M")
    monthly = window.pivot_table(index="month", columns="cust", values="gmv",
                                 aggfunc=aggfunc, fill_value=0)
    return monthly.reindex(index=months, columns=accounts, fill_value=0).fillna(0)
