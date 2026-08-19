# -*- coding: utf-8 -*-
"""Sekcie reportu o produktoch v objednávkach.

Tretí, samostatný report. Odpovedá na inú otázku než predchádzajúce dva: nie
koľko účtov rastie, ale čo tí zákazníci kupujú a čo sa z toho dá o nich zistiť.
"""

from src.common import constants as C
import pathlib

import pandas as pd

from src.common import report as R
from src.products import charts

EUR = R.format_eur
PCT = R.format_pct
NUM = R.format_number


def _fig(figures, figure_id):
    """Vykreslí graf podľa jeho ID, alebo nič, ak je v C.HIDDEN_CHARTS."""
    if figure_id in C.HIDDEN_CHARTS:
        return ""
    for figure in figures:
        if figure["id"] == figure_id:
            return R.render_figure(figure)
    raise KeyError(f"graf s id '{figure_id}' nie je medzi figures")


def header(metrics):
    """Nadpis a prehľadové karty."""
    profile = metrics["profile"]

    cards = [
        ("Objednávok", NUM(profile["orders"])),
        ("Rôznych produktov", NUM(profile["skus"])),
        ("Priemer návratov", PCT(metrics["overall_return_pct"])),
    ]

    html = f"""
<h1>Čo B2B zákazníci kupujú</h1>
<ul class="lead">
<li>Zdroj: <code>{C.INPUT_LABEL}</code> a položky objednávok</li>
<li>Stav k: {C.AS_OF:%-d. %-m. %Y}</li>
</ul>
{R.render_kpi_cards(cards)}
<p>Report skúma, či sa z obsahu nákupu dá povedať niečo, čo sa z jeho hodnoty
povedať nedá. Prvé dve sekcie hľadajú signál dostupný hneď pri prvej objednávke,
zvyšné dve popisujú, ako sa portfólio správa pred odchodom a kde je krehké.</p>
"""
    return html, []


def entry_product_section(metrics):
    """Ktorý vstupný produkt sprevádza najhoršie návraty."""
    worst = metrics["entry_products"].head(C.PRODUCT_TOP)
    reference = metrics["overall_return_pct"]
    all_products = metrics["entry_products"]

    figures = [charts.entry_product_retention(worst, reference)]

    return f"""
<h2>1. Vstupný produkt a návrat zákazníka</h2>
{_entry_product_intro(all_products, reference)}
{_fig(figures, "entry_product_retention")}
{_entry_product_text(all_products, reference)}
{R.render_rollup(f"Všetkých {NUM(len(all_products))} posudzovaných produktov",
                 _entry_product_table(all_products))}
""", figures


def _entry_product_intro(products, reference):
    """Čo sa v tejto sekcii skúša a prečo."""
    return f"""
<p>Z <b>hodnoty</b> prvej objednávky sa nedá povedať, kto sa vráti — mediány
jednorazových a opakujúcich zákazníkov sa líšia o jednotky eur. Táto sekcia
skúša, či to dokáže jej <b>obsah</b>.</p>
<p>Ku každému produktu je spočítané, koľko percent zákazníkov, ktorí ho mali
v prvej objednávke, si niekedy objednalo znova. Priemer naprieč všetkými
zákazníkmi je {PCT(reference)}. Posudzuje sa {NUM(len(products))} produktov —
tie s aspoň {C.PRODUCT_MIN_CUSTOMERS} zákazníkmi; pri menších počtoch je podiel
šum.</p>
{_sku_names_note(products)}
"""


def _sku_names_note(products):
    """Upozorní, ak produkty ešte nemajú doplnený názov."""
    unnamed = int((products["label"] == products.index).sum())
    if unnamed == 0:
        return ""

    return f"""
<p class="small">{NUM(unnamed)} z {NUM(len(products))} produktov zatiaľ nemá
doplnený názov a je uvedený svojím kódom. Názvy sa dopĺňajú do
<code>{pathlib.Path(C.SKU_NAMES_CSV).name}</code> — je to tá istá mapa, akú
používa drill-in report, takže názov doplnený raz platí v oboch.</p>
"""


def _entry_product_text(products, reference):
    """Čo z rebríčka plynie."""
    worst = products.iloc[0]
    best = products.iloc[-1]
    below = int((products["returned_pct"] < reference).sum())

    return f"""
<p>Najhorší vstupný produkt má {PCT(worst["returned_pct"])} návratov
({NUM(worst["customers"])} zákazníkov), najlepší {PCT(best["returned_pct"])}
({NUM(best["customers"])} zákazníkov). Pod priemerom je {NUM(below)}
z {NUM(len(products))} produktov.</p>
<p class="small">Pozor na príčinnosť. Nízky podiel návratov neznamená, že
produkt zákazníka odradil — môže ísť o tovar, ktorý sa kupuje raz za dlhý čas,
alebo o produkt typický pre segment, ktorý nakupuje jednorazovo. Rebríček je
miesto, kde sa treba pozrieť, nie záver.</p>
"""


def _entry_product_table(products):
    """Všetky posudzované vstupné produkty."""
    return R.render_table(
        products,
        [("label", "Produkt", str),
         ("customers", "Zákazníkov", NUM),
         ("returned", "Vrátilo sa", NUM),
         ("returned_pct", "Podiel návratov", PCT),
         ("gmv", "GMV prvých objednávok", EUR)],
        index_label="Kód",
    )


def basket_width_section(metrics):
    """Šírka prvého košíka ako signál."""
    width = metrics["basket_width"]
    reference = metrics["overall_return_pct"]

    figures = [charts.basket_width(width, reference)]

    return f"""
<h2>2. Šírka prvého košíka</h2>
<p>Hypotéza: kto si objednal jednu vec, skúšal; kto si objednal osem, plnil
sklad. Ak platí, je to signál dostupný <b>v deň prvej objednávky</b>, nie o rok
neskôr.</p>
{_fig(figures, "basket_width")}
{_basket_width_text(width, reference)}
{R.render_table(
    width,
    [("customers", "Zákazníkov", NUM),
     ("returned_pct", "Podiel návratov", PCT),
     ("median_gmv", "Medián prvej objednávky", EUR)],
    index_label="Rôznych produktov")}
""", figures


def _basket_width_text(width, reference):
    """Či hypotéza v dátach platí."""
    narrow = width.iloc[0]
    wide = width.iloc[-1]
    difference = wide["returned_pct"] - narrow["returned_pct"]

    if difference >= 10:
        verdict = ("<b>Hypotéza platí.</b> Rozdiel medzi najužším a najširším "
                   "košíkom je {gap} p. b., čo je dosť na to, aby sa podľa toho "
                   "dali nové účty triediť už pri prvej objednávke.")
    elif difference <= -10:
        verdict = ("<b>Hypotéza platí obrátene</b> — širší prvý košík sprevádza "
                   "horší návrat ({gap} p. b.). To si zaslúži vysvetlenie skôr "
                   "než opatrenie.")
    else:
        verdict = ("<b>Hypotéza neplatí.</b> Rozdiel je {gap} p. b., teda v rámci "
                   "šumu — šírka prvého košíka o návrate nič nehovorí.")

    gap = NUM(abs(difference), 1)
    return f"""
<p>Pri {narrow.name} produkte v prvej objednávke sa vráti
{PCT(narrow["returned_pct"])} zákazníkov, pri {wide.name} produktoch
{PCT(wide["returned_pct"])}. Priemer je {PCT(reference)}.</p>
<p>{verdict.format(gap=gap)}</p>
"""


def narrowing_section(metrics):
    """Zužuje sa košík pred odchodom?"""
    left = metrics["narrowing_left"]
    right = metrics["narrowing_right"]

    figures = [charts.assortment_narrowing(
        left, right, metrics["narrowing_left_label"], metrics["narrowing_right_label"])]

    return f"""
<h2>3. Zužovanie sortimentu pred odchodom</h2>
<p>O odchode účtu sa dnes dozvieme, až keď je hotový. Táto sekcia skúša, či mu
predchádza zúženie košíka — či účet pred koncom prestáva kupovať šírku
sortimentu a doberá už len jednu-dve veci.</p>
{_fig(figures, "assortment_narrowing")}
{_narrowing_text(metrics)}
""", figures


def _narrowing_text(metrics):
    """Čo z dvoch kriviek plynie."""
    left = metrics["narrowing_left"]
    right = metrics["narrowing_right"]

    left_change = left["products"].iloc[-1] - left["products"].iloc[0]
    right_change = right["products"].iloc[-1] - right["products"].iloc[0]

    if left_change < -0.5 and left_change < right_change:
        verdict = ("<b>Zúženie je vidieť.</b> Odídené účty pred koncom nakupujú "
                   "užší sortiment, kým aktívne si šírku držia. Je to použiteľný "
                   "varovný signál.")
    else:
        verdict = ("<b>Zúženie v dátach nie je.</b> Obe krivky sa správajú "
                   "podobne, takže šírka košíka odchod nepredpovedá — účty "
                   "odchádzajú bez varovania v sortimente.")

    return f"""
<p>Odídeným účtom sa počet rôznych produktov medzi prvým a posledným oknom
zmenil o {NUM(left_change, 1)}, aktívnym o {NUM(right_change, 1)}.</p>
<p>{verdict}</p>
"""


def dependence_section(metrics):
    """Kde je portfólio krehké."""
    split = metrics["dependence_split"]
    fragile = metrics["fragile_accounts"]

    figures = [charts.dependence_split(split)]

    return f"""
<h2>4. Závislosť účtov na jedinom produkte</h2>
<p>Účet, ktorému jeden produkt drží väčšinu GMV, nie je stabilný odberateľ, ale
jedna objednávka opakovaná dokola. Stačí výpadok skladu — v sekcii o dobropisoch
bol „nebola na sklade, expedovalo sa bez nej“ jedným z dôvodov — a odíde celý
účet, nie jedna položka.</p>
{_fig(figures, "dependence_split")}
{_dependence_text(split, fragile)}
{_fragile_rollup(fragile)}
""", figures


def _fragile_rollup(fragile):
    """Zoznam krehkých účtov. Prázdny zoznam sa nevykresľuje ako prázdna tabuľka."""
    if len(fragile) == 0:
        return ""
    return R.render_rollup(f"Zoznam {NUM(len(fragile))} najkrehkejších účtov",
                           _fragile_table(fragile))


def _dependence_text(split, fragile):
    """Aká veľká je krehká časť portfólia."""
    risky = split.iloc[-1]

    if risky["accounts"] == 0:
        return f"""
<p>Žiadny posudzovaný účet nemá viac než
{C.PRODUCT_DEPENDENCE_EDGES[-1]} % GMV v jedinom produkte — z tejto strany je
portfólio zdravé.</p>
"""

    return f"""
<p>Jeden produkt drží viac než {C.PRODUCT_DEPENDENCE_EDGES[-1]} % GMV pri
{NUM(risky["accounts"])} účtoch, ktoré spolu robia {EUR(risky["gmv"])}, teda
{PCT(risky["gmv_share_pct"])} posudzovaného GMV. V zozname nižšie je
{NUM(len(fragile))} najväčších z nich — pri každom aj produkt, na ktorom
visí, a jeho zaradenie inde v analýze.</p>
<p class="small">Pomlčka v posledných dvoch stĺpcoch znamená, že účet nie je
v menovateli KPI, takže sa o jeho raste ani odchode do nuly nedá nič povedať.
Prvé dva stĺpce platia pre každý účet: „1 objednávka“ je počet objednávok za
celý život, „churnutý“ znamená {C.KPI_DIAG_CHURN_DAYS}+ dní bez objednávky.</p>
"""


def _fragile_table(fragile):
    """Najväčšie účty závislé na jedinom produkte, s ich zaradením inde."""
    return R.render_table(
        fragile,
        [("gmv", "GMV účtu", EUR),
         ("top_share_pct", "Podiel top produktu", PCT),
         ("top_label", "Produkt", str),
         ("products", "Rôznych produktov", NUM),
         ("single_order", "1 objednávka", _flag),
         ("churned", "Churnutý", _flag),
         ("growing", "Rastúci", _flag),
         ("dropped_to_zero", "Odišiel do nuly", _flag)],
        index_label="Účet",
    )


def _flag(value):
    """Áno/nie, alebo pomlčka pri účte, ktorý KPI neposudzuje."""
    if pd.isna(value):
        return "—"
    return "áno" if value else "nie"


SECTION_BUILDERS = [
    header,
    entry_product_section,
    basket_width_section,
    narrowing_section,
    dependence_section,
]


def build_all(metrics):
    """Poskladá HTML všetkých sekcií a zoznam grafov."""
    html_parts = []
    figures = []
    for position, builder in enumerate(SECTION_BUILDERS):
        section_html, section_figures = builder(metrics)
        html_parts.append(R.render_collapsible(section_html))
        if position == 0:
            html_parts.append(R.FOLD_TOOLBAR_HTML)
        for figure in section_figures:
            if figure["id"] not in C.HIDDEN_CHARTS:
                figures.append(figure)
    return "\n".join(html_parts), figures
