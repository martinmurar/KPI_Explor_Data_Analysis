# -*- coding: utf-8 -*-
"""Konfigurácia a konštanty pre EDA rastu GMV."""

import pathlib

import pandas as pd

# ── vstup a výstup ────────────────────────────────────────────────────────────
# Cesty sa odvodzujú od umiestnenia tohto súboru, nie od aktuálneho adresára —
# vstupné body sú v dvoch rôznych podpriečinkoch a rovnaká relatívna cesta by
# v každom z nich ukazovala inam.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

# INPUT_XLSX = str(DATA_DIR / "b2b_orders_cleaned.xlsx")
INPUT_XLSX = str(DATA_DIR / "b2b_orders_cleaned_w_company_name_3.xlsx")
OUTPUT_HTML = str(DATA_DIR / "b2b_gmv_eda.html")

# Druhý, samostatný report — drill-in do KPI account growth. Má vlastný vstupný
# bod (main_drill_in.py) a hlavného reportu sa nedotýka.
OUTPUT_HTML_DRILL_IN = str(DATA_DIR / "b2b_account_growth_drill_in.html")

# Do hlavičky reportu ide len názov súboru — absolútna cesta by tam zavadzala.
INPUT_LABEL = pathlib.Path(INPUT_XLSX).name

# ── položky objednávok ────────────────────────────────────────────────────────
# Export SKU jednotlivých objednávok. Má cez 4 GB a takmer 95 mil. riadkov,
# takže sa číta po častiach — nikdy nie celý naraz. Nie je súčasťou pipeline
# žiadneho reportu, používajú ho len ad-hoc analýzy.
ORDER_ITEMS_CSV = str(DATA_DIR / "orders_sku.csv")

# Koľko riadkov naraz drží v pamäti jeden prechod. 2 mil. riadkov je zhruba
# 300 MB — bezpečné aj na stroji s 3 GB pamäte.
ORDER_ITEMS_CHUNK_ROWS = 2_000_000

# Odložené výsledky filtrovania pre jednotlivé skupiny zákazníkov.
SINGLE_ORDER_ITEMS_CSV = str(DATA_DIR / "single_order_items.csv")
REGULAR_ORDER_ITEMS_CSV = str(DATA_DIR / "regular_order_items.csv")
ALL_ORDER_ITEMS_CSV = str(DATA_DIR / "b2b_order_items.csv")

# Koľko najsilnejších SKU sa vypisuje v grafe a v tabuľke.
SINGLE_ORDER_ITEMS_TOP = 15

# Úrovne, na ktorých sa meria koncentrácia GMV do najsilnejších SKU.
SINGLE_ORDER_ITEMS_LEVELS = (10, 25, 50, 100)

# Od akého podielu top 10 SKU na GMV sa nákup považuje za sústredený.
SINGLE_ORDER_ITEMS_CONCENTRATED_PCT = 25

# Mapa SKU → názov produktu. Vypĺňa sa ručne; skript single_order_items.py do
# nej dopĺňa prázdne riadky pre SKU, ktoré sa v reporte zobrazujú. SKU bez
# vyplneného názvu sa v grafe ukáže ako holé SKU.
SKU_NAMES_CSV = str(DATA_DIR / "sku_names.csv")

# Najdlhší popisok produktu v grafe. Dlhší sa skráti a plný názov zostane
# v hover — v dvoch stĺpcoch vedľa seba by celé názvy zjedli plochu stĺpcov.
SKU_LABEL_MAX_CHARS = 32

# Časti názvu, ktoré v popisku nič nehovoria, lebo sú pri každom produkte
# rovnaké. Vyhadzujú sa po častiach oddelených pomlčkou.
SKU_LABEL_DROP = ("GymBeam",)

# Darček a vzorka. V rebríčkoch a súčtoch sú to bežné produkty ako každý iný;
# navyše sa len počíta, v koľkých objednávkach sa objavili. Hľadajú sa podľa
# kódu, nie podľa názvu — „+ darček“ býva aj v názve bežne predávaného balenia
# (napr. Ashwagandha + darček 90 kaps.).
GIFT_SAMPLE_SKUS = ("31571", "31577")

# ── analýza produktov (tretí report) ──────────────────────────────────────────
OUTPUT_HTML_PRODUCTS = str(DATA_DIR / "b2b_products.html")

# ── rozcestník ────────────────────────────────────────────────────────────────
# Jedna stránka so záložkami, ktorá tie tri reporty spája. Reporty zostávajú
# samostatné súbory a dajú sa otvoriť aj priamo — rozcestník ich len vkladá.
OUTPUT_HTML_PORTAL = str(DATA_DIR / "index.html")

# Záložky v poradí, v akom sa zobrazujú: (názov, súbor reportu).
PORTAL_TABS = [
    ("Hlavný report", OUTPUT_HTML),
    ("Account growth — drill-in", OUTPUT_HTML_DRILL_IN),
    ("Čo zákazníci kupujú", OUTPUT_HTML_PRODUCTS),
]

# Produkt sa do rebríčka vstupných produktov dostane, len ak ho v prvej
# objednávke malo aspoň toľko zákazníkov. Pri menšom počte je podiel návratov
# šum — jeden zákazník hore-dole ním hýbe o desiatky percent.
PRODUCT_MIN_CUSTOMERS = 25

# Koľko produktov sa vypisuje v rebríčkoch tretieho reportu.
PRODUCT_TOP = 15

# Šírka prvého košíka: koše podľa počtu rôznych produktov v prvej objednávke.
BASKET_WIDTH_EDGES = [1, 2, 3, 5, 10]
BASKET_WIDTH_BUCKETS = ["1", "2", "3", "4–5", "6–10", "11+"]

# Okná pred posledným nákupom, v ktorých sa meria šírka sortimentu.
NARROWING_WINDOWS_MONTHS = (12, 9, 6, 3)

# Účet, ktorého GMV z tejto časti tvorí jediný produkt, je krehký — výpadok
# skladu alebo lacnejšia konkurencia zoberie celý účet, nie jednu položku.
PRODUCT_DEPENDENCE_EDGES = [25, 50, 80]
PRODUCT_DEPENDENCE_BUCKETS = ["< 25 %", "25–50 %", "50–80 %", "> 80 %"]

# Účet sa do rezov podľa účtu počíta, len ak má aspoň toľko GMV — pri drobných
# účtoch je podiel jedného produktu na GMV náhoda.
PRODUCT_MIN_ACCOUNT_GMV = 500

# ── objednávky s dobropisom ───────────────────────────────────────────────────
# Dva súbory zámerne oddelene: prvý je export objednávok, ku ktorým bol
# vystavený dobropis, druhý je ručná anotácia z Slacku (príčina a odkaz na
# vlákno). Export sa dá kedykoľvek pregenerovať bez toho, aby sa stratili
# anotácie, a spájajú sa cez order_number.
CREDIT_MEMO_CSV = str(DATA_DIR / "single_orders_memos.csv")
CREDIT_MEMO_NOTES_CSV = str(DATA_DIR / "credit_memo_slack_notes.csv")

# Príčiny dobropisu v poradí, v akom sa zobrazujú. Posledné dve nie sú
# príčiny — sú to objednávky, o ktorých Slack mlčí, a objednávky, ktoré do
# analýzy strát nepatria.
CREDIT_MEMO_NO_TRACE = "Bez zmienky v Slacku"
CREDIT_MEMO_IRRELEVANT = "Nerelevantné"
CREDIT_MEMO_CATEGORIES = [
    "Chýbajúci alebo poškodený tovar",
    "Oneskorenie a komunikácia",
    "Administratíva a fakturácia",
    CREDIT_MEMO_NO_TRACE,
    CREDIT_MEMO_IRRELEVANT,
]

# Status zrušenej objednávky. Zrušené objednávky sa z datasetu vyhadzujú —
# nie sú tržbou a v exporte `_3` tvoria tretinu GMV.
CANCELED_STATUS = "canceled"

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

# Od ktorého roku sa berú objednávky bežných zákazníkov v analýze položiek.
# Sortiment sa mení, porovnávať dnešný nákup s tým spred piatich rokov by
# nedávalo zmysel. Definované až tu, lebo vychádza z DISPLAY_START_YEAR.
ORDER_ITEMS_START_YEAR = DISPLAY_START_YEAR

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

# Prvý mesiac churn krivky a zároveň hranica churn bázy — do bázy patrí len
# účet, ktorý od tohto dátumu aspoň raz nakúpil. Bez tej hranice by v báze
# navždy zostávali mŕtve účty z rokov 2018–2023 a churn by stúpal len tým, že
# sa báza plní účtami, ktoré už nikdy neobjednajú (74,3 % namiesto 59,8 %).
# Je to jedna hodnota pre obe veci zámerne: krivka aj báza majú začínať tam,
# kde začína zobrazované obdobie.
CHURN_CURVE_START = pd.Timestamp(year=DISPLAY_START_YEAR, month=1, day=1)

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

# ── diagnostika KPI account growth (druhý report) ─────────────────────────────
# Účet s najviac týmto počtom objednávok v oboch oknách je porovnávaný na
# základe jednotiek udalostí — tam KPI meria hlavne časovanie.
# Okno, za ktoré drill-in počíta objednávky posudzovaných účtov. Nie je to
# FREQUENCY_WINDOW_MONTHS z hlavného reportu: 15 mesiacov presne pokryje obe
# okná KPI (minuloročné aj aktuálne), takže „účet bez objednávky v okne“ je
# skutočne mŕtvy účet a nie účet, ktorý nakúpil tesne pred 12-mesačnou hranicou.
KPI_DIAG_WINDOW_MONTHS = 12

# Názov stĺpca s GMV za toto okno. Dĺžka okna je priamo v názve, takže po zmene
# KPI_DIAG_WINDOW_MONTHS sa nedá omylom čítať číslo za iné obdobie.
KPI_DIAG_GMV_KEY = f"gmv_{KPI_DIAG_WINDOW_MONTHS}m"

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

# ── veľkostné pásma zákazníkov ────────────────────────────────────────────────
# Podľa GMV v porovnávacom období.
BAND_EDGES = [0, 500, 2000, 10000, 50000, float("inf")]
BAND_LABELS = ["<0,5k €", "0,5–2k €", "2–10k €", "10–50k €", ">50k €"]

# ── ostatné parametre ─────────────────────────────────────────────────────────
# Koľko top zákazníkov sa sleduje v koncentrácii.
TOP_N_LEVELS = (1, 5, 10, 20, 50)

# Krajiny vykazované samostatne. Všetko ostatné sa zlúči do jednej kategórie.
REPORTED_COUNTRIES = ["SK", "CZ", "HU", "PL"]
OTHER_MARKET_LABEL = "Ostatné"

# Okno, za ktoré sa meria frekvencia objednávania.
FREQUENCY_WINDOW_MONTHS = 12

# Histogram frekvencie má jednotkové koše od FREQUENCY_FIRST_BUCKET po
# FREQUENCY_TOP_BUCKET - 1. Zahrnutí sú len zákazníci s aspoň jednou
# objednávkou v okne, takže koše idú od 1, nie od 0.
FREQUENCY_FIRST_BUCKET = 1

# Posledný kôš zlučuje túto frekvenciu a všetky vyššie a nesie označenie "30+".
FREQUENCY_TOP_BUCKET = 30

# Drill-in: spodný extrém je zákazník, ktorý za celý život minul menej než
# SMALL_VETERAN_LIFETIME_GMV a zároveň je starší než SMALL_VETERAN_AGE_MONTHS.
# Obe podmienky naraz — mladý zákazník s nízkou útratou ešte nemal čas rozbehnúť
# sa a jeho vyradenie by potrestalo čerstvú akvizíciu.
#
# Vek je zosúladený s ACCOUNT_GROWTH_MIN_AGE_MONTHS zámerne: filter tak vyradí
# presne tie účty, ktoré KPI vôbec posudzuje, a ani o jeden viac. Nižšia hranica
# by z datasetu brala zákazníkov, ktorých menovateľ aj tak nevidí — na KPI by to
# nemalo vplyv, ale ostatné rezy nad tým datasetom by tichu prišli o akvizíciu.
SMALL_VETERAN_LIFETIME_GMV = 1000
SMALL_VETERAN_AGE_MONTHS = ACCOUNT_GROWTH_MIN_AGE_MONTHS

# Zákazník s jedinou objednávkou sa posudzuje, až keď mal na návrat aspoň toľko
# času. Bez toho by sa medzi „stratených“ počítala aj čerstvá akvizícia, ktorá
# druhú objednávku ešte len môže urobiť.
SINGLE_ORDER_MIN_AGE_MONTHS = 12

# Koše hodnoty objednávky pre porovnanie jednorazových a opakujúcich zákazníkov.
# EDGES sú horné hranice, posledný kôš je otvorený.
ORDER_VALUE_EDGES = [100, 300, 1000, 5000]
ORDER_VALUE_BUCKETS = ["< 100 €", "100–300 €", "300–1 000 €", "1–5 tis. €", "> 5 tis. €"]

# Koše pre rez KPI podľa počtu objednávok za FREQUENCY_WINDOW_MONTHS mesiacov.
# EDGES sú horné hranice prvých košov, posledný kôš je otvorený a hranicu nemá,
# takže BUCKETS má o jeden prvok viac. Koše musia byť disjunktné — účet s 15
# objednávkami patrí do „6–15“, nie aj do „16–25“.
#
# Komentár pod grafom číta koše po skupinách: prvý je mŕtve účty, druhý a tretí
# tenký chvost, prostredné tvoria plató a posledný je otvorený. Pri zmene počtu
# košov to platí ďalej, pri zmene ich poradia už nie.
KPI_ORDER_COUNT_EDGES = [0, 1, 2, 5, 15, 25, 30]
KPI_ORDER_COUNT_BUCKETS = ["0", "1", "2", "3–5", "6–15", "16–25", "26–30", "31+"]

# ── farby grafov ──────────────────────────────────────────────────────────────
COLOR_BLUE = "#2a78d6"
COLOR_BLUE_LIGHT = "#a9c8ea"
COLOR_ORANGE = "#eb6834"
COLOR_TEAL = "#1baf7a"
COLOR_TEAL_DARK = "#1a9268"
COLOR_YELLOW = "#eda100"
COLOR_VIOLET = "#4a3aa7"
COLOR_RED = "#e34948"
COLOR_GREY = "#898781"
COLOR_INK = "#141413"

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
# Farby v grafoch diagnostiky KPI.
KPI_DIAG_COLOR_GOOD = COLOR_TEAL_DARK
KPI_DIAG_COLOR_NEUTRAL = COLOR_BLUE
KPI_DIAG_COLOR_BAD = COLOR_RED
KPI_DIAG_COLOR_TARGET = COLOR_GREY

# Farby príčin dobropisu. Prevádzková príčina je červená, administratívna
# oranžová, skupiny bez výpovednej hodnoty sivé.
CREDIT_MEMO_COLORS = {
    CREDIT_MEMO_CATEGORIES[0]: COLOR_RED,
    CREDIT_MEMO_CATEGORIES[1]: COLOR_ORANGE,
    CREDIT_MEMO_CATEGORIES[2]: COLOR_YELLOW,
    CREDIT_MEMO_NO_TRACE: COLOR_GREY,
    CREDIT_MEMO_IRRELEVANT: COLOR_BLUE_LIGHT,
}

