# -*- coding: utf-8 -*-
"""Konfigurácia a konštanty pre EDA rastu GMV."""

import pandas as pd

# ── vstup a výstup ────────────────────────────────────────────────────────────
# INPUT_XLSX = "../data/b2b_orders_cleaned.xlsx"
INPUT_XLSX = "../data/b2b_orders_cleaned_w_company_name_2.xlsx"
OUTPUT_HTML = "../data/b2b_gmv_eda.html"

# Druhý, samostatný report — diagnostika KPI account growth. Má vlastný vstupný
# bod (main_kpi_diagnostics.py) a hlavného reportu sa nedotýka.
OUTPUT_HTML_KPI_DIAGNOSTICS = "../data/b2b_kpi_diagnostics.html"

# ── viditeľnosť grafov ────────────────────────────────────────────────────────
# ID grafov, ktoré sa v reporte nevykresľujú (text okolo nich zostáva).
# ID zodpovedá figure_id/id z charts.py — pri hľadaní ID grafu, ktorý chceš
# vypnúť, stačí grepnúť charts.py za "_figure(".
HIDDEN_CHARTS = set()

# ── časové hranice ────────────────────────────────────────────────────────────
# Rok, od ktorého report zobrazuje dáta — ročné tabuľky a grafy (trend,
# koncentrácia, trhy, bridge, kohorty, reaktivácie), mesačný trend, churn
# krivka aj kvartálna história account growth. Metriky s klzavým oknom alebo
# historickou bázou (napr. 12-mesačný priemer, churn báza) počítajú aj
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

# Roky, z ktorých sa počíta priemerná sezonalita. Len kompletné roky, a len
# roky zo zobrazovaného obdobia — sezónny profil nie je hodnota, ktorá by na
# svoj výpočet potrebovala staršie dáta.
SEASONALITY_YEARS = (DISPLAY_START_YEAR, 2025)

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

# Prvý mesiac churn krivky a zároveň hranica churn bázy — do bázy patrí len
# účet, ktorý od tohto dátumu aspoň raz nakúpil. Bez tej hranice by v báze
# navždy zostávali mŕtve účty z rokov 2018–2023 a churn by stúpal len tým, že
# sa báza plní účtami, ktoré už nikdy neobjednajú (74,3 % namiesto 59,8 %).
# Je to jedna hodnota pre obe veci zámerne: krivka aj báza majú začínať tam,
# kde začína zobrazované obdobie.
CHURN_CURVE_START = pd.Timestamp(year=DISPLAY_START_YEAR, month=1, day=1)

# Medzera bez objednávky, po ktorej sa ďalšia objednávka počíta ako reaktivácia.
REACTIVATION_GAP_MONTHS = 12

# ── account growth (interné KPI) ──────────────────────────────────────────────
# Účet mladší ako toto sa do KPI nepočíta. Hodnota nie je voľná:
# 12 + GMV_WINDOW_MONTHS zaručuje, že každý posudzovaný účet mal k dispozícii
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

# ── diagnostika KPI account growth (druhý report) ─────────────────────────────
# Účet s najviac týmto počtom objednávok v oboch oknách je porovnávaný na
# základe jednotiek udalostí — tam KPI meria hlavne časovanie.
KPI_DIAG_THIN_ORDERS = 2

# Po koľkých dňoch bez objednávky sa účet v diagnostike považuje za churnutý.
# Kto nakúpil neskôr, je živý — len neobjednal práve v porovnávanom okne.
KPI_DIAG_CHURN_DAYS = 180

# Popisky troch skupín, na ktoré sa delia posudzované účty. Prostredná skupina
# je jadro problému — sú to živé účty, ktoré len netrafili okno.
KPI_DIAG_ACTIVITY_LABELS = [
    "Nakúpili v aktuálnom okne",
    f"Nakúpili za posledných {KPI_DIAG_CHURN_DAYS} dní, ale mimo "
    f"{GMV_WINDOW_MONTHS}-mesačného okna",
    f"Churned — {KPI_DIAG_CHURN_DAYS}+ dní bez objednávky",
]

# Popisky scenára pravidelného objednávania.
KPI_DIAG_REGULAR_LABELS = [
    "KPI ako sa vykazuje",
    f"KPI, ak by živé účty objednávali aspoň raz za {GMV_WINDOW_MONTHS} mesiace",
]

# Pravdepodobnosti rastu, ktoré sa v scenári zabráneného churnu skúšajú.
# Nie je to rozdelenie odhadnuté z dát, ale citlivosť na jeden predpoklad:
# 0 = zachránený účet nikdy nerastie (= dnešný stav), 1 = rastie vždy.
KPI_DIAG_CHURN_PROBABILITIES = (0.0, 0.5, 1.0)

# Stredný predpoklad použitý v kombinovanom scenári. Účet, ktorý by v okne
# nakúpil, sa dostane medzi účty aktívne v oboch oknách — a tam je rast
# v podstate hod mincou, preto 0,5.
KPI_DIAG_CHURN_PREVENTED_GROWTH_RATE = 0.5

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
# FREQUENCY_TOP_BUCKET - 1. Zahrnutí sú len zákazníci s aspoň jednou
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

# Tmavšia zelená pre diagnostický report. COLOR_TEAL nemá voči pozadiu kontrast
# 3:1 a od COLOR_RED sa pri deuteranopii odlíši len s ΔE 6,9 — tento odtieň
# prejde oboma kontrolami. V hlavnom reporte zámerne nemeníme nič.
COLOR_TEAL_DARK = "#1a9268"

# Farby v grafoch diagnostiky KPI.
KPI_DIAG_COLOR_GOOD = COLOR_TEAL_DARK
KPI_DIAG_COLOR_NEUTRAL = COLOR_BLUE
KPI_DIAG_COLOR_BAD = COLOR_RED
KPI_DIAG_COLOR_MUTED = COLOR_GREY
KPI_DIAG_COLOR_TARGET = COLOR_GREY
