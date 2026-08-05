# -*- coding: utf-8 -*-
"""Konfigurácia a konštanty pre EDA rastu GMV."""

import pandas as pd

# ── vstup a výstup ────────────────────────────────────────────────────────────
INPUT_XLSX = "b2b_orders_cleaned.xlsx"
OUTPUT_HTML = "b2b_gmv_eda.html"

# ── časové hranice ────────────────────────────────────────────────────────────
# Posledný deň dát. Používa sa ako "dnešný dátum" pre churn a rolling okná.
AS_OF = pd.Timestamp("2026-07-31")

# 2018 je pilot (146 objednávok, medián 16,8 €) — vylúčené z trendov.
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

# Prvý mesiac churn krivky (skôr je báza príliš malá na stabilné čísla).
CHURN_CURVE_START = pd.Timestamp("2020-01-31")

# Medzera bez objednávky, po ktorej sa ďalšia objednávka počíta ako reaktivácia.
REACTIVATION_GAP_MONTHS = 12

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

# Histogram frekvencie má jednotkové koše od 0 po FREQUENCY_TOP_BUCKET - 1.
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
