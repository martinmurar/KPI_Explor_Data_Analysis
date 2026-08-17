# -*- coding: utf-8 -*-
"""Načítanie a príprava dát o objednávkach.

Rozhodnutia:
- Zrušené objednávky sa vyhadzujú, ostatné statusy nie. Export od verzie
  `_3` obsahuje aj `canceled` — je to tretina vykazovaného GMV, takže bez
  odfiltrovania by report tvrdil tržby, ktoré nikdy nevznikli. Rozpracované
  stavy (sent, processing, pending) zostávajú: sú 0,1 % GMV, ale v poslednom
  mesiaci sú to čerstvé objednávky a filtrovanie na `complete` by posledný
  mesiac systematicky podhodnotilo.
- Zákazník = customer_email (lowercase, strip). Ak firma nakupuje z viacerých
  e-mailov, je v dátach ako viac zákazníkov -> nadhodnocuje new/churn/reactivated.
"""

import pandas as pd

from src.common import constants as C


def load_orders(path):
    """Načíta objednávky z xlsx a doplní derivované stĺpce."""
    df = pd.read_excel(path, dtype=str)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["gmv"] = pd.to_numeric(df["gmv"])
    df["cust"] = df["customer_email"].str.strip().str.lower()
    df = _drop_canceled(df)
    df = _drop_orders_after_as_of(df)
    df = _add_period_columns(df)
    df = _add_customer_columns(df)
    df["market"] = _market_group(df["country"])
    return df


def _drop_canceled(df):
    """Odstráni zrušené objednávky.

    Staršie exporty ich neobsahovali vôbec, preto sa status nefiltroval. Vo
    verzii `_3` ich pribudlo 10 416 za 30,5 mil. €; ponechané by nafúkli GMV
    aj menovateľ KPI o tretinu.
    """
    return df.loc[df["status"] != C.CANCELED_STATUS].copy()


def _drop_orders_after_as_of(df):
    """Odreže objednávky novšie ako C.AS_OF.

    Export môže obsahovať aj niekoľko dní po C.AS_OF a tie by inak pretiekli do
    metrík, ktoré samy podľa dátumu nefiltrujú — mesačný trend by mal nekompletný
    mesiac navyše, ročné súčty a koncentrácia by počítali s dátami, ktoré vôbec
    nie sú vo vykazovanom období.

    Reže sa na koniec dňa C.AS_OF, nie na jeho začiatok — objednávky z toho dňa
    do vykazovaného obdobia patria.
    """
    cutoff = C.AS_OF + pd.Timedelta(days=1)
    return df.loc[df["created_at"] < cutoff].copy()


def _market_group(countries):
    """Zaradí krajinu do vykazovaného trhu alebo do kategórie Ostatné."""
    is_reported = countries.isin(C.REPORTED_COUNTRIES)
    return countries.where(is_reported, C.OTHER_MARKET_LABEL)


def _add_period_columns(df):
    """Doplní stĺpce pre mesiac, kvartál a rok."""
    df = df.copy()
    df["month"] = df["created_at"].dt.to_period("M")
    df["quarter"] = df["created_at"].dt.to_period("Q")
    df["year"] = df["created_at"].dt.year
    return df


def _add_customer_columns(df):
    """Doplní prvú a poslednú objednávku zákazníka a akvizičnú kohortu."""
    df = df.copy()
    first_order = df.groupby("cust")["created_at"].min()
    df["first_order"] = df["cust"].map(first_order)
    df["cohort_year"] = df["first_order"].dt.year
    df["months_since_first"] = _months_between(df["first_order"], df["created_at"])
    return df


def _months_between(start, end):
    """Počet celých mesiacov medzi dvoma sériami dátumov (0 = ten istý mesiac)."""
    start_period = start.dt.to_period("M")
    end_period = end.dt.to_period("M")
    return (end_period - start_period).apply(lambda offset: offset.n)


def data_quality(df):
    """Vráti prehľad kvality dát ako slovník."""
    return {
        "orders": len(df),
        "customers": df["cust"].nunique(),
        "gmv": df["gmv"].sum(),
        "date_min": df["created_at"].min(),
        "date_max": df["created_at"].max(),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_ids": int(df["entity_id"].duplicated().sum()),
        "zero_gmv_orders": int((df["gmv"] == 0).sum()),
    }
def company_names(df):
    """Najčastejšie použitý company_bill pre každého zákazníka.

    Fakturačné údaje majú preklepy a historické varianty názvu (napr. "Kaufland"
    vs "Kaufland Slovenská republika v.o.s.") — berie sa najčastejšie použitý.
    Zákazníci bez vyplneného company_bill v zozname nie sú.
    """
    named = df.dropna(subset=["company_bill"])
    names = {}
    for cust, group in named.groupby("cust"):
        names[cust] = group["company_bill"].value_counts().idxmax()
    return names


def trend_years(df):
    """Zoznam rokov použitých v ročných grafoch a tabuľkách.

    Filtruje na C.DISPLAY_START_YEAR, nie na C.FIRST_TREND_YEAR — ide o to,
    ktoré roky sa v reporte zobrazujú, nie ktoré roky sú platné dáta.
    """
    years = sorted(df.loc[df["year"] >= C.DISPLAY_START_YEAR, "year"].unique())
    return [int(year) for year in years]


def year_label(year):
    """Označí nekompletný rok hviezdičkou."""
    if year == C.PARTIAL_YEAR:
        return f"{year}*"
    return str(year)


def orders_in_window(df, start, end):
    """Objednávky v intervale [start, end)."""
    mask = (df["created_at"] >= start) & (df["created_at"] < end)
    return df.loc[mask]


def gmv_per_customer(df, start, end):
    """GMV každého zákazníka v intervale [start, end)."""
    window = orders_in_window(df, start, end)
    return window.groupby("cust")["gmv"].sum()


def last_order_per_customer(df, as_of=None):
    """Dátum poslednej objednávky každého zákazníka do dátumu as_of."""
    if as_of is None:
        subset = df
    else:
        subset = df.loc[df["created_at"] <= as_of]
    return subset.groupby("cust")["created_at"].max()


def first_order_per_customer(df):
    """Dátum prvej objednávky každého zákazníka."""
    return df.groupby("cust")["created_at"].min()


def without_small_veterans(df):
    """Objednávky bez zákazníkov, ktorí za celý život minuli málo a už dávno.

    Odfiltrujú sa spodné extrémy: zákazník s celoživotným GMV pod
    SMALL_VETERAN_LIFETIME_GMV, ktorého prvá objednávka je staršia ako
    SMALL_VETERAN_AGE_MONTHS. Mladší zákazník zostáva bez ohľadu na útratu —
    ešte nemal čas rozbehnúť sa a jeho vyradenie by potrestalo čerstvú akvizíciu.

    Vracia objednávky, nie zákazníkov, aby sa výsledok dal poslať do rovnakých
    metrík ako pôvodný dataset.
    """
    lifetime_gmv = df.groupby("cust")["gmv"].sum()
    first_order = first_order_per_customer(df)
    cutoff = C.AS_OF - pd.DateOffset(months=C.SMALL_VETERAN_AGE_MONTHS)

    is_small = lifetime_gmv < C.SMALL_VETERAN_LIFETIME_GMV
    is_veteran = first_order < cutoff
    dropped = lifetime_gmv.index[is_small & is_veteran]
    return df.loc[~df["cust"].isin(dropped)]


def assign_bands(gmv_series, edges, labels):
    """Zaradí zákazníkov do veľkostných pásiem podľa GMV.

    Hranice sa posúvajú o malé epsilon, aby GMV presne na hranici padlo
    do nižšieho pásma a nulové GMV sa nevylúčilo.
    """
    cut_edges = [edges[0] - 0.01] + list(edges[1:])
    return pd.cut(gmv_series, bins=cut_edges, labels=labels)
