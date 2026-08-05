# -*- coding: utf-8 -*-
"""Interné KPI „account growth“ — podiel účtov s vyššími tržbami než pred rokom.

Definícia zhodná s firemným reportingom:
    GMV účtu za posledné GMV_WINDOW_MONTHS mesiacov sa porovná s GMV za to isté
    okno o rok skôr. Účet rastie, ak je aktuálne GMV vyššie, klesá ak nižšie.

Menovateľ má dve podmienky:
    1. Účet je starší ako ACCOUNT_GROWTH_MIN_AGE_MONTHS. Hodnota 15 nie je
       náhodná — je to 12 + GMV_WINDOW_MONTHS, teda každý účet v menovateli mal
       k dispozícii plné minuloročné okno.
    2. Účet bol aktívny aspoň v jednom z dvoch okien. Kto nenakúpil ani v jednom,
       nie je ani rastúci ani klesajúci a do KPI nepatrí.

Vedľa neváženého KPI sa počíta GMV-vážený variant = podiel GMV aktuálneho okna,
ktoré leží v rastúcich účtoch. Ukazuje, či nevážené KPI a tržby hovoria to isté.
"""

import pandas as pd

from src import constants as C
import data
import metrics_bridge


# Skupiny, na ktoré sa rozpadá menovateľ. Prvé dve sú rozhodnuté binárne —
# účet nakúpil alebo nenakúpil — a o rast v nich vôbec nejde.
COMPOSITION_REACTIVATED = "Reaktivované (0 → +)"
COMPOSITION_DROPPED = "Odišli do nuly (+ → 0)"
COMPOSITION_BOTH = "Aktívne v oboch oknách"
COMPOSITION_ORDER = [COMPOSITION_REACTIVATED, COMPOSITION_DROPPED, COMPOSITION_BOTH]

# Názvy skupín zákazníkov. Mapa nepokrýva všetky id v dátach — nepokryté
# zostávajú v reze pod svojím číslom, aby ticho nevypadli.
CUSTOMER_GROUP_ID_TO_NAME_MAP = {
    325: "S HU",
    295: "S CZ",
    274: "XS CZ",
    349: "S UA",
    319: "S CZ w VAT",
    322: "S SK",
    37: "S w/o VAT",
    46: "S with VAT",
    421: "M HU",
    283: "M SK",
    439: "S BG",
    262: "XS SK",
    328: "S PL",
    388: "S RO",
    490: "M RO",
    301: "M CZ"
}


# ── základná tabuľka ──────────────────────────────────────────────────────────
def account_table(df, as_of, window_months=None, min_age_months=None):
    """Tabuľka účtov v menovateli KPI s ich GMV v oboch oknách.

    window_months a min_age_months sú parametrizovateľné len preto, aby sa dala
    zmerať citlivosť KPI na definíciu. Predvolené hodnoty sú tie firemné.
    """
    if window_months is None:
        window_months = C.GMV_WINDOW_MONTHS
    if min_age_months is None:
        min_age_months = C.ACCOUNT_GROWTH_MIN_AGE_MONTHS

    table = _gmv_comparison(df, as_of, window_months)
    table = _attach_attributes(table, df)
    table = _apply_denominator(table, as_of, min_age_months)
    table["growing"] = table["current"] > table["previous"]
    table["declining"] = table["current"] < table["previous"]
    return table


def _gmv_comparison(df, as_of, window_months):
    """GMV a počet objednávok každého účtu v aktuálnom a minuloročnom okne."""
    current_start, current_end = metrics_bridge.gmv_window(as_of, window_months)
    previous_start = current_start - pd.DateOffset(years=1)
    previous_end = current_end - pd.DateOffset(years=1)

    table = pd.DataFrame({
        "previous": data.gmv_per_customer(df, previous_start, previous_end),
        "current": data.gmv_per_customer(df, current_start, current_end),
        "previous_orders": _order_count(df, previous_start, previous_end),
        "current_orders": _order_count(df, current_start, current_end),
    })
    all_accounts = pd.Index(df["cust"].unique(), name="cust")
    return table.reindex(all_accounts).fillna(0.0)


def _order_count(df, start, end):
    """Počet objednávok každého účtu v intervale [start, end)."""
    window = data.orders_in_window(df, start, end)
    return window.groupby("cust").size()


def _attach_attributes(table, df):
    """Doplní atribúty účtu použité v rezoch."""
    table = table.copy()
    table["first_order"] = data.first_order_per_customer(df)
    table["cohort_year"] = table["first_order"].dt.year
    table["country"] = _latest_value_per_customer(df, "country")
    table["customer_group_id"] = _latest_value_per_customer(df, "customer_group_id")
    return table


def _latest_value_per_customer(df, column):
    """Hodnota stĺpca z najnovšej objednávky účtu.

    Krajina ani skupina nie sú v dátach na úrovni zákazníka, len na objednávke,
    a v čase sa môžu zmeniť. Berie sa posledný stav.
    """
    ordered = df.sort_values("created_at")
    return ordered.groupby("cust")[column].last()


def _apply_denominator(table, as_of, min_age_months):
    """Nechá len účty, ktoré patria do menovateľa KPI."""
    age_cutoff = as_of - pd.DateOffset(months=min_age_months)
    is_mature = table["first_order"] <= age_cutoff
    is_active = (table["previous"] > 0) | (table["current"] > 0)
    return table.loc[is_mature & is_active].copy()


# ── prehľadové čísla ──────────────────────────────────────────────────────────
def kpi_summary(table):
    """Hlavné čísla KPI k jednému dátumu."""
    accounts = len(table)
    growing = int(table["growing"].sum())
    needed = _accounts_needed_for_target(accounts, growing)
    return {
        "accounts": accounts,
        "growing": growing,
        "growing_pct": growing / accounts * 100,
        "declining_pct": table["declining"].sum() / accounts * 100,
        "gmv_growing_pct": _gmv_growing_pct(table),
        "accounts_needed_for_target": needed,
    }


def _accounts_needed_for_target(accounts, growing):
    """Koľko ďalších rastúcich účtov treba na dosiahnutie cieľa."""
    target_count = accounts * C.ACCOUNT_GROWTH_TARGET_PCT / 100
    missing = target_count - growing
    if missing <= 0:
        return 0
    return int(missing) + 1


def _gmv_growing_pct(table):
    """Podiel GMV aktuálneho okna, ktoré leží v rastúcich účtoch."""
    total = table["current"].sum()
    if total == 0:
        return float("nan")
    return table.loc[table["growing"], "current"].sum() / total * 100


# ── rozklad menovateľa ────────────────────────────────────────────────────────
def composition(table):
    """Rozdelí menovateľ na reaktivované, odídené a aktívne v oboch oknách."""
    groups = {
        COMPOSITION_REACTIVATED: table.loc[table["previous"] == 0],
        COMPOSITION_DROPPED: table.loc[table["current"] == 0],
        COMPOSITION_BOTH: table.loc[(table["previous"] > 0) & (table["current"] > 0)],
    }

    rows = []
    for label in COMPOSITION_ORDER:
        rows.append(_composition_row(label, groups[label], len(table)))
    return pd.DataFrame(rows).set_index("group")


def _composition_row(label, members, total_accounts):
    """Jeden riadok rozkladu menovateľa."""
    growing = int(members["growing"].sum())
    return {
        "group": label,
        "customers": len(members),
        "share_pct": len(members) / total_accounts * 100,
        "growing": growing,
        "declining": len(members) - growing,
        "growing_pct": growing / len(members) * 100 if len(members) else float("nan"),
        "previous_gmv": members["previous"].sum(),
        "current_gmv": members["current"].sum(),
    }


# ── KPI v čase ────────────────────────────────────────────────────────────────
def history(df):
    """KPI v kvartálnych bodoch, vždy rovnakou definíciou."""
    rows = []
    for quarter_end in _history_points():
        table = account_table(df, quarter_end)
        summary = kpi_summary(table)
        summary["date"] = quarter_end
        rows.append(summary)
    return pd.DataFrame(rows).set_index("date")


def _history_points():
    """Konce kvartálov od začiatku histórie KPI do dátumu AS_OF."""
    return pd.date_range(start=C.ACCOUNT_GROWTH_HISTORY_START, end=C.AS_OF, freq="3ME")


# ── rezy ──────────────────────────────────────────────────────────────────────
def by_size_band(table):
    """KPI podľa veľkostného pásma, určeného GMV v minuloročnom okne.

    Minimálna veľkosť segmentu sa tu neuplatňuje — najväčšie pásmo má vždy málo
    účtov a zároveň drží väčšinu GMV, vynechať ho by bolo horšie ako ukázať ho
    s malým n.
    """
    bands = data.assign_bands(table["previous"], C.BAND_EDGES, C.BAND_LABELS)
    return _breakdown(table, bands, order=C.BAND_LABELS, min_size=1)


def by_previous_orders(table):
    """KPI podľa počtu objednávok v minuloročnom okne.

    Účet s jednou objednávkou za kvartál je porovnávaný na základe jedinej
    udalosti — KPI potom meria hlavne časovanie objednávky, nie rast.

    Reaktivované účty (nula objednávok pred rokom) sú vynechané. Sú rastúce
    z definície, takže by v tomto reze len vyrobili kôš so 100 %.
    """
    active_before = table.loc[table["previous_orders"] > 0]
    labels = _order_count_labels(active_before["previous_orders"])
    return _breakdown(active_before, labels,
                      order=C.ACCOUNT_GROWTH_ORDER_BUCKETS, min_size=1)


def _order_count_labels(order_counts):
    """Zaradí počet objednávok do koša podľa ACCOUNT_GROWTH_ORDER_BUCKETS."""
    buckets = []
    for count in order_counts:
        buckets.append(_order_count_label(count))
    return pd.Series(buckets, index=order_counts.index)


def _order_count_label(count):
    """Popisok koša pre jeden počet objednávok."""
    edges = C.ACCOUNT_GROWTH_ORDER_EDGES
    for index, edge in enumerate(edges):
        if count <= edge:
            return C.ACCOUNT_GROWTH_ORDER_BUCKETS[index]
    return C.ACCOUNT_GROWTH_ORDER_BUCKETS[-1]


def by_cohort(table):
    """KPI podľa roku prvej objednávky."""
    years = sorted(table["cohort_year"].unique())
    labels = table["cohort_year"].astype(str)
    return _breakdown(table, labels, order=[str(year) for year in years])


def by_country(table):
    """KPI podľa krajiny.

    Zámerne sa nepoužíva zlúčená kategória „Ostatné“ ako vo zvyšku reportu —
    práve v nezlúčených krajinách je rozptyl KPI najväčší a je to stopa.
    """
    return _breakdown(table, table["country"])


def by_customer_group(table):
    """KPI podľa skupiny zákazníka."""
    labels = _customer_group_labels(table["customer_group_id"])
    return _breakdown(table, labels)


def _customer_group_labels(group_ids):
    """Preloží customer_group_id na názov skupiny.

    Id, ktoré v mape nie je, zostáva ako „group <číslo>“. Bez tohto fallbacku
    by mu .map() dalo NaN, groupby by taký riadok mlčky zahodilo a skupina by
    z rezu zmizla bez akéhokoľvek signálu.
    """
    numeric_ids = group_ids.astype(int)
    names = numeric_ids.map(CUSTOMER_GROUP_ID_TO_NAME_MAP)
    return names.fillna("group " + numeric_ids.astype(str))


def _breakdown(table, segments, order=None, min_size=None):
    """KPI po segmentoch.

    order=None znamená zoradiť podľa podielu rastúcich, čo je pri nominálnych
    segmentoch (krajina, skupina) čitateľnejšie ako abecedne. Pri usporiadaných
    segmentoch (pásmo, rok) sa poradie predpisuje.
    """
    if min_size is None:
        min_size = C.ACCOUNT_GROWTH_MIN_SEGMENT_SIZE

    working = table.copy()
    working["segment"] = segments

    rows = []
    for segment, members in working.groupby("segment", observed=True):
        if len(members) < min_size:
            continue
        rows.append(_breakdown_row(segment, members))

    result = pd.DataFrame(rows).set_index("segment")
    return _sort_breakdown(result, order)


def _breakdown_row(segment, members):
    """Jeden riadok rezu."""
    growing = int(members["growing"].sum())
    return {
        "segment": segment,
        "customers": len(members),
        "growing": growing,
        "growing_pct": growing / len(members) * 100,
        "gmv_growing_pct": _gmv_growing_pct(members),
        "previous_gmv": members["previous"].sum(),
        "current_gmv": members["current"].sum(),
        "net_delta": members["current"].sum() - members["previous"].sum(),
    }


def _sort_breakdown(result, order):
    """Zoradí rez buď predpísaným poradím, alebo podľa podielu rastúcich."""
    if order is None:
        return result.sort_values("growing_pct", ascending=False)
    present = [segment for segment in order if segment in result.index]
    return result.loc[present]


# ── vplyv parametrov definície ────────────────────────────────────────────────
def definition_sensitivity(df):
    """Ako sa KPI mení s dĺžkou okna a s vekovým filtrom.

    Slúži na to, aby bolo vidieť, koľko z hodnoty KPI je vlastnosť biznisu
    a koľko je vlastnosť zvolených parametrov.
    """
    rows = []
    for months in C.ACCOUNT_GROWTH_WINDOW_VARIANTS:
        label = f"{months}-mes. okno"
        rows.append(_sensitivity_row(df, label, window_months=months))
    for age in C.ACCOUNT_GROWTH_AGE_VARIANTS:
        label = f"vek ≥ {age} mes."
        rows.append(_sensitivity_row(df, label, min_age_months=age))
    return pd.DataFrame(rows).set_index("variant")


def _sensitivity_row(df, label, window_months=None, min_age_months=None):
    """Jeden variant definície KPI."""
    table = account_table(df, C.AS_OF, window_months=window_months,
                          min_age_months=min_age_months)
    summary = kpi_summary(table)
    summary["variant"] = label
    return summary
