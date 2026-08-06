# -*- coding: utf-8 -*-
"""Konfigurácia a konštanty pre EDA rastu GMV."""

import pandas as pd

# ── vstup a výstup ────────────────────────────────────────────────────────────
# INPUT_XLSX = "../data/b2b_orders_cleaned.xlsx"
INPUT_XLSX = "../data/b2b_orders_cleaned_w_company_name_2.xlsx"
OUTPUT_HTML = "../data/b2b_gmv_eda.html"

# ── viditeľnosť grafov ────────────────────────────────────────────────────────
# ID grafov, ktoré sa v reporte nevykresľujú (text okolo nich zostáva).
# ID zodpovedá figure_id/id z charts.py — pri hľadaní ID grafu, ktorý chceš
# vypnúť, stačí grepnúť charts.py za "_figure(".
HIDDEN_CHARTS = {
    "ag_by_group",
    "ag_by_country",
    "ag_by_cohort",
    "ag_by_orders",
}

# ── časové hranice ────────────────────────────────────────────────────────────
# Rok, od ktorého report zobrazuje dáta — ročné tabuľky a grafy (trend,
# koncentrácia, trhy, bridge, kohorty, reaktivácie), mesačný trend, churn
# krivka aj kvartálna história account growth. Metriky s klzavým oknom alebo
# historickým menovateľom (napr. 12-mesačný priemer, churn báza) počítajú aj
# s dátami spred tohto roka — tie len nie sú v reporte vidieť, sú potrebné,
# aby prvý zobrazený bod mal platnú hodnotu. Zmena tejto jednej hodnoty
# preráta všetky časové grafy a tabuľky v reporte naraz.
DISPLAY_START_YEAR = 2024

# Posledný deň dát. Používa sa ako "dnešný dátum" pre churn a rolling okná.
AS_OF = pd.Timestamp("2026-07-31")

# 2018 je pilot (146 objednávok, medián 16,8 €) — vylúčené z trendov aj z
# výpočtov, nielen zo zobrazenia (na rozdiel od DISPLAY_START_YEAR vyššie).
FIRST_TREND_YEAR = 2019

# Rok, ktorý je v dátach nekompletný. V grafoch sa značí hviezdičkou.
PARTIAL_YEAR = 2026
PARTIAL_YEAR_LAST_MONTH = 7

# Rolling okno pre GMV analýzy podľa pásma: 3 mesiace YoY.
GMV_WINDOW_MONTHS = 3

# Roky, z ktorých sa počíta priemerná sezonalita (len kompletné roky).
SEASONALITY_YEARS = (2022, 2025)

# Šírka klzavého priemeru v mesačnom trende.
MOVING_AVERAGE_MONTHS = 12

# ── churn ─────────────────────────────────────────────────────────────────────
# Prahy pre churn krivky: zákazník je v bode t churned, ak od poslednej
# objednávky prešlo viac ako N mesiacov. Budúce objednávky sa ignorujú.
CHURN_THRESHOLDS_MONTHS = (3, 6, 12)

# Prah použitý v analýzach podľa pásma a v prehľadových číslach.
CHURN_MAIN_THRESHOLD_MONTHS = 6

# Ako dlho dozadu sa meria veľkosť zákazníka pri churne podľa pásma.
CHURN_BAND_LOOKBACK_MONTHS = 12

# Prvý mesiac churn krivky. Odvodené z DISPLAY_START_YEAR — churn báza sa aj
# tak počíta zo všetkých historicky akvirovaných zákazníkov, len sa krivka
# nekreslí skôr, ako report zobrazuje dáta.
CHURN_CURVE_START = pd.Timestamp(year=DISPLAY_START_YEAR, month=1, day=1)

# Medzera bez objednávky, po ktorej sa ďalšia objednávka počíta ako reaktivácia.
REACTIVATION_GAP_MONTHS = 12

# ── account growth (interné KPI) ──────────────────────────────────────────────
# Účet mladší ako toto sa do KPI nepočíta. Hodnota nie je voľná:
# 12 + GMV_WINDOW_MONTHS zaručuje, že každý účet v menovateli mal k dispozícii
# plné minuloročné porovnávacie okno.
ACCOUNT_GROWTH_MIN_AGE_MONTHS = 12 + GMV_WINDOW_MONTHS

# Cieľová hodnota KPI. Kreslí sa ako referenčná čiara.
ACCOUNT_GROWTH_TARGET_PCT = 60

# Prvý bod kvartálneho časového radu KPI. Odvodené z DISPLAY_START_YEAR —
# každý bod je nezávislý prierez, takže skrátenie radu nemení hodnoty
# ostávajúcich bodov, len históriu pred nimi nekreslí.
ACCOUNT_GROWTH_HISTORY_START = pd.Timestamp(year=DISPLAY_START_YEAR, month=1, day=1)

# Segment menší ako toto sa v rezoch nezobrazuje — pri jednotkách účtov je
# podiel rastúcich už len šum.
ACCOUNT_GROWTH_MIN_SEGMENT_SIZE = 15

# Koše počtu objednávok v minuloročnom okne. EDGES sú horné hranice košov,
# posledný kôš je otvorený a hranicu nemá.
ACCOUNT_GROWTH_ORDER_EDGES = [0, 1, 2, 5]
ACCOUNT_GROWTH_ORDER_BUCKETS = ["0", "1", "2", "3–5", "6+"]

# ── veľkostné pásma zákazníkov ────────────────────────────────────────────────
# Podľa GMV v porovnávacom období.
BAND_EDGES = [0, 500, 2000, 10000, 50000, float("inf")]
BAND_LABELS = ["<0,5k €", "0,5–2k €", "2–10k €", "10–50k €", ">50k €"]

# Pásma pre koncentráciu portfólia (ročné GMV zákazníka).
PORTFOLIO_EDGES = [0, 1000, 5000, 20000, 100000, float("inf")]
PORTFOLIO_LABELS = ["<1k €", "1–5k €", "5–20k €", "20–100k €", ">100k €"]

# ── ostatné parametre ─────────────────────────────────────────────────────────
# Koľko top zákazníkov sa sleduje v koncentrácii.
TOP_N_LEVELS = (1, 5, 10, 20, 50)

# Krajiny vykazované samostatne. Všetko ostatné sa zlúči do jednej kategórie.
REPORTED_COUNTRIES = ["SK", "CZ", "HU", "PL"]
OTHER_MARKET_LABEL = "Ostatné"
MARKET_ORDER = REPORTED_COUNTRIES + [OTHER_MARKET_LABEL]

# Okno, za ktoré sa meria frekvencia objednávania.
FREQUENCY_WINDOW_MONTHS = 12

# Histogram frekvencie má jednotkové koše od FREQUENCY_FIRST_BUCKET po
# FREQUENCY_TOP_BUCKET - 1. Menovateľom sú len zákazníci s aspoň jednou
# objednávkou v okne, takže koše idú od 1, nie od 0.
FREQUENCY_FIRST_BUCKET = 1

# Posledný kôš zlučuje túto frekvenciu a všetky vyššie a nesie označenie "30+".
FREQUENCY_TOP_BUCKET = 30

# Koše histogramu počtu reaktivácií za život zákazníka.
REACTIVATION_LABELS = ["0", "1", "2", "3", "4+"]

# ── farby grafov ──────────────────────────────────────────────────────────────
COLOR_BLUE = "#2a78d6"
COLOR_BLUE_LIGHT = "#a9c8ea"
COLOR_ORANGE = "#eb6834"
COLOR_TEAL = "#1baf7a"
COLOR_YELLOW = "#eda100"
COLOR_MAGENTA = "#e87ba4"
COLOR_GREEN = "#008300"
COLOR_VIOLET = "#4a3aa7"
COLOR_RED = "#e34948"
COLOR_GREY = "#898781"
COLOR_INK = "#141413"

COUNTRY_PALETTE = [
    COLOR_BLUE, COLOR_ORANGE, COLOR_TEAL, COLOR_YELLOW,
    COLOR_MAGENTA, COLOR_GREEN, COLOR_VIOLET, COLOR_RED, COLOR_GREY,
]

COHORT_PALETTE = [
    COLOR_BLUE, COLOR_ORANGE, COLOR_TEAL, COLOR_YELLOW,
    COLOR_MAGENTA, COLOR_GREEN, COLOR_VIOLET, COLOR_RED,
]

# Farby komponentov medziročnej zmeny GMV.
BRIDGE_COLORS = {
    "expansion": COLOR_BLUE,
    "reactivated": COLOR_TEAL,
    "new": COLOR_YELLOW,
    "contraction": COLOR_ORANGE,
    "churn": COLOR_RED,
}

BRIDGE_LABELS_SK = {
    "expansion": "Expanzia",
    "reactivated": "Reaktivovaní",
    "new": "Noví",
    "contraction": "Kontrakcia",
    "churn": "Churn",
}

# Poradie komponentov: najprv prírastky, potom straty.
BRIDGE_COMPONENTS = ["expansion", "reactivated", "new", "contraction", "churn"]

# Farby v grafoch account growth.
ACCOUNT_GROWTH_COLOR_GROWING = COLOR_BLUE
ACCOUNT_GROWTH_COLOR_DECLINING = COLOR_RED
ACCOUNT_GROWTH_COLOR_GMV = COLOR_INK
ACCOUNT_GROWTH_COLOR_TARGET = COLOR_GREY
ACCOUNT_GROWTH_COLOR_ABOVE_TARGET = COLOR_TEAL
