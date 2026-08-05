# EDA rastu GMV v B2B — dokumentácia a handoff

Analýza objednávkových dát z `b2b_orders_cleaned.xlsx` s generovaným HTML reportom
(16 interaktívnych grafov). Tento dokument je napísaný tak, aby sa v práci dalo
pokračovať bez znalosti predchádzajúcej konverzácie.

---

## 1. Spustenie

```bash
pip install pandas numpy openpyxl
python3 main.py --input b2b_orders_cleaned.xlsx --output b2b_gmv_eda.html
```

Bez argumentov sa použijú predvolené cesty z `constants.py`. Beh trvá ~1 minútu,
najdlhšie churn krivky (79 časových bodov × 3 prahy).

Vstupné dáta nie sú súčasťou balíka. Očakávaný formát — jeden list, stĺpce:
`entity_id`, `customer_email`, `created_at`, `gmv`, `customer_group_id`,
`website_id`, `status`, `country`.

---

## 2. Štruktúra a tok dát

```
constants.py               — všetky konštanty, prahy a farby
formatting.py              — formátovanie čísiel (slovenský zápis)
data.py                    — načítanie, čistenie, pomocné výbery
metrics_trend.py           — trend, sezonalita, hodnota objednávky
metrics_bridge.py          — rozklad medziročnej zmeny GMV
metrics_churn.py           — churn, reaktivácie, frekvencia, pásma
metrics_concentration.py   — koncentrácia portfólia, trhy
charts.py                  — špecifikácie grafov (dáta, farby, hover)
report.py                  — HTML komponenty a JS prekladač grafov
sections.py                — text a poradie sekcií reportu
main.py                    — vstupný bod
```

Tok je jednosmerný: `data → metrics_* → charts → report`. Metriky nevedia o grafoch,
grafy nevedia o HTML. `sections.py` je jediné miesto, ktoré pozná oboje.

**Pridanie grafu** = jedna funkcia v `charts.py`, jeden riadok v `main.compute_metrics()`
a jeden riadok v príslušnej sekcii v `sections.py`.

### Ako fungujú grafy

`charts.py` nevytvára Chart.js konfiguráciu, len serializovateľný slovník:

```python
{
  "id": "frequency_histogram",
  "title": "...", "caption": "...",
  "type": "bar", "labels": [...], "datasets": [...],
  "stacked": False, "index_axis": "x",
  "value_format": "count",       # mil_eur | k_eur | eur | pct | count
  "y_max": None, "y_begin_at_zero": True,
  "hover_extras": [["riadok 1"], ["riadok 1"], ...]   # voliteľné
}
```

Preklad do Chart.js robí `CHART_BUILDER_JS` v `report.py` — jedno miesto pre
formátovanie osí a tooltipov. Séria môže mať vlastný `value_format`, keď má inú
jednotku ako zvyšok grafu (napríklad percentá vedľa počtov).

`hover_extras` pridá do tooltipu ľubovoľné riadky bez vizuálnej zmeny grafu
(cez `afterBody`). Texty sa formátujú v Pythone, JS ich len vypíše.

### Tabuľky a čísla v texte

Obe sa generujú z metrík, nič nie je napísané natvrdo. `report.render_table()` berie
DataFrame a zoznam trojíc `(stĺpec, hlavička, formátovacia funkcia)`. Čísla v komentároch
sa vkladajú f-stringami z tých istých metrík, ktoré kreslia grafy — pri novom exporte
dát sa prepočítajú a nemôžu zostať zastarané.

---

## 3. Metodické rozhodnutia

Toto je najdôležitejšia časť dokumentu. Každé rozhodnutie má dôvod; pri zmene sa
posunú aj čísla v reporte.

**Statusy sa nefiltrujú.** V dátach nie je žiadny `canceled`. Nedokončené stavy sú
0,3 % celkového GMV, ale v poslednom mesiaci ~10 % (čerstvé objednávky). Filtrovanie
na `complete` by posledný mesiac systematicky podhodnotilo.

**Zákazník = `customer_email`** (lowercase, strip). Ak firma nakupuje z viacerých
e-mailov, je v dátach ako viac zákazníkov, čo nadhodnocuje nových, churn aj reaktivácie.
Toto je najväčšie známe skreslenie analýzy. Ak sa objaví mapovanie e-mail → firma,
patrí do `data.load_orders()` a všetko ostatné sa prepočíta samo.

**Rok 2018 je pilot** (146 objednávok, medián 16,8 €) a je vylúčený z trendov cez
`FIRST_TREND_YEAR = 2019`. V dátach zostáva, aby bol správne určený `first_order`.
Rok 2019 sa nedá porovnať s pilotom, preto v bridge a YoY grafoch chýba.

**Rok 2026 je nekompletný** (do 31. 7.) a zobrazuje sa označený hviezdičkou.
Medziročné porovnania preň používajú rovnaké okno (Jan–Júl vs Jan–Júl) — vrátane
ročného bridge, kde by porovnanie čiastočného roku s celým nemalo zmysel.

**Churn.** V časovom bode *t* je zákazník churned, ak od jeho poslednej objednávky
(do *t*) prešlo viac ako N mesiacov. Budúce objednávky sa ignorujú — ak churned
zákazník objedná o mesiac, v bode *t* je aj tak churned. Menovateľ = zákazníci
akvirovaní aspoň N mesiacov pred *t*; kto nakúpil prvýkrát neskôr, nemal šancu odísť.

Pri churne podľa pásma sa veľkosť zákazníka meria za 12 mesiacov **pred** oknom,
v ktorom mohol odísť (`CHURN_BAND_LOOKBACK_MONTHS`). Inak by churned zákazníci mali
automaticky nulové GMV a pásmo by nemalo význam.

**Reaktivácia** = objednávka po medzere dlhšej ako `REACTIVATION_GAP_MONTHS` (12).
Toto je striktnejšia definícia ako komponenta *Reaktivovaní* v bridge, ktorá znamená
len „nenakúpil v porovnávacom okne". Pri ročných oknách sú si blízke, pri kratších nie —
preto sú v reporte oddelené a pri bridge je na to upozornenie.

**Bridge má kontrolu konzistencie.** `_assert_components_sum_to_delta()` overuje, že
komponenty sú vzájomne vylučujúce a ich súčet sa rovná celkovej zmene. Pri zmene
definícií skript spadne namiesto tichého vykreslenia nezmyslu.

**Trhy.** Samostatne sa vykazujú krajiny v `REPORTED_COUNTRIES` (SK, CZ, HU, PL),
všetko ostatné je zlúčené do `OTHER_MARKET_LABEL`. Zaradenie sa robí raz
v `data.load_orders()` do stĺpca `market`.

**Frekvencia objednávania** sa meria za `FREQUENCY_WINDOW_MONTHS` (12). Histogram má
jednotkové koše od 0 po `FREQUENCY_TOP_BUCKET - 1`, posledný kôš zlučuje túto frekvenciu
a vyššie. **Kôš 0 sú dormantní zákazníci, takže menovateľom je celá databáza** — bez neho
by histogram zamlčal najväčšiu skupinu v nej. V hover je reverzný kumulatív, teda počet
zákazníkov s danou frekvenciou a vyššou.

**Medián vs priemer.** Distribúcia GMV je extrémne šikmá (Gini 0,92). Priemer sám
je zavádzajúci, preto sa všade reportuje aj medián a mediánová zmena na zákazníka.

---

## 4. Konfigurácia

Pri novom exporte dát stačí posunúť v `constants.py`:

```python
AS_OF = pd.Timestamp("2026-07-31")   # posledný deň dát, "dnes" pre churn
PARTIAL_YEAR = 2026                  # nekompletný rok
PARTIAL_YEAR_LAST_MONTH = 7
```

Ďalšie parametre, ktoré menia obsah reportu:

| Konštanta | Hodnota | Význam |
|---|---|---|
| `GMV_WINDOW_MONTHS` | 3 | okno pre GMV analýzy podľa pásma (YoY) |
| `CHURN_THRESHOLDS_MONTHS` | (3, 6, 12) | prahy churn kriviek |
| `CHURN_MAIN_THRESHOLD_MONTHS` | 6 | prah v analýzach podľa pásma |
| `CHURN_BAND_LOOKBACK_MONTHS` | 12 | okno na určenie veľkosti pri churne |
| `CHURN_CURVE_START` | 2020-01-31 | prvý bod churn krivky |
| `REACTIVATION_GAP_MONTHS` | 12 | medzera definujúca reaktiváciu |
| `FREQUENCY_WINDOW_MONTHS` | 12 | okno pre histogram frekvencie |
| `FREQUENCY_TOP_BUCKET` | 30 | posledný kôš histogramu (30+) |
| `MOVING_AVERAGE_MONTHS` | 12 | šírka klzavého priemeru |
| `BAND_EDGES` | 0/500/2k/10k/50k | veľkostné pásma zákazníkov |
| `REPORTED_COUNTRIES` | SK, CZ, HU, PL | samostatne vykazované trhy |

---

## 5. Čo report obsahuje (16 grafov)

| Sekcia | Grafy |
|---|---|
| 1. Trend GMV | mesačné GMV + 12-mes. klzavý priemer; sezonalita |
| 2. Komponenty medziročnej zmeny | ročný bridge (stacked + netto línia) |
| 3. Hodnota objednávky | priemer vs medián vs p95 |
| 4. Koncentrácia | podiel top N; zákazníci na 80 % GMV; veľkostná štruktúra |
| 5. Trhy | GMV podľa trhu; medziročný rast podľa trhu |
| 6. Churn | churn v čase (3/6/12 mes.); rast a churn podľa pásma; netto GMV podľa pásma |
| 7. Lojalita a frekvencia | one-and-done podľa kohorty; histogram frekvencie |
| 8. Reaktivácie | počet reaktivácií za život; reaktivácie po rokoch + % opakovaných |
| 9. Zhrnutie | — |

---

## 6. Kľúčové zistenia (stav k 31. 7. 2026)

Aby nový chat nemusel analýzu odvodzovať znova.

**Rast je koncentrovaný do 13 účtov.** Za posledné 3 mesiace medziročne pásmo
`>50k €` (13 zákazníkov) pridalo +918 031 €, kým všetky ostatné pásma spolu
−199 936 € pri 758 zákazníkoch. Top 1 zákazník je 20,0 % GMV, top 10 je 61,0 %.
Na 80 % GMV stačí 43 zákazníkov (v 2022 ich bolo 119). HHI 773, Gini 0,92.

**Typický zákazník nerastie.** GMV rastie ~+49 % YoY, ale medián hodnoty objednávky
je 8 rokov plochý (~330–375 €, v 2026 dokonca 350 €), kým priemer vyrástol 638 → 1 541 €.
Pomer priemer/medián stúpol z 2,0× na 4,4×. Mediánová medziročná zmena GMV je negatívna
vo **všetkých** veľkostných pásmach, vrátane najväčšieho (−9,1 %).

**Churn systematicky rastie.** 6-mesačný churn stúpol z 39,2 % (1/2020) na 74,3 %
(7/2026). Krivky 3/6/12 mesiacov sú blízko seba (78,7 / 74,3 / 70,7 %) — väčšina
neaktívnych nie je dočasne stíchnutá, je dávno mimo. Churn podľa pásma klesá
zo 74,4 % (`<0,5k €`) na 7,7 % (`>50k €`); podiel rastúcich stúpa z 23,9 % na 46,2 %.

**Reaktivácia je vzácna a jednorazová.** 86,6 % zákazníkov s aspoň dvoma objednávkami
nebolo nikdy reaktivovaných; viackrát len 31 zákazníkov za celú históriu. Z reaktivácií
v 2026 pripadalo len 9 % na opakovaných reaktivantov. Odchod je v praxi definitívny,
takže win-back nie je páka na rast.

**Akvizícia klesá v kvalite.** Podiel zákazníkov s jedinou objednávkou za život stúpol
zo 17,9 % (kohorta 2019) na 38,0 % (2025). Medián objednávok za život klesol z 9 na 2,
medián LTV z 5 190 € na 755 €. Medián prvej objednávky klesol z 326 € na 268 €.

**Frekvencia je extrémne šikmá.** Z 3 981 zákazníkov v databáze 2 111 (53 %) za posledných
12 mesiacov nenakúpilo vôbec a 706 (17,7 %) urobilo jedinú objednávku. Aspoň 10 objednávok
má 7,3 % bázy, aspoň 30 len 1,8 % (72 zákazníkov). Maximum je 345 objednávok.

**Trhy.** CZ 45,3 % + SK 32,1 % = 77 % GMV. PL rastie +265 % (takmer celé na jednom
účte). Kategória `Ostatné` má 652 zákazníkov (41,9 % bázy) pri 9,1 % GMV a mediánovej
objednávke 289 € — drobní odberatelia, ktorí v metrikách „na zákazníka" vážia rovnako
ako key accounty. Práve to je mechanizmus, prečo interné KPI vykazuje nízky podiel
rastúcich zákazníkov.

**Kontext k internému KPI.** Firma vykazuje, že kvartálne medziročne rastie iba ~40 %
zákazníkov. Metrika je reprodukovateľná, ale výsledok silno závisí od menovateľa
(pri okne máj–júl 2026 vs 2025): 27,0 % z aktívnych vlani, 49,2 % z aktívnych v oboch
obdobiach, 61,5 % z aktívnych aspoň v jednom, **42,1 % z etablovaných zákazníkov
aktívnych aspoň v jednom** (najbližšie firemnému číslu), 44,4 % z tých s GMV nad 5 tis. €.
Táto porovnávacia tabuľka v aktuálnom reporte **nie je** — pochádza z predchádzajúcej
verzie analýzy a je to kandidát na doplnenie.

---

## 7. Historické poznámky a jedna oprava

Prvá verzia analýzy tvrdila, že reaktivácie sú „kolotoč" — že tí istí zákazníci oscilujú
medzi churnom a reaktiváciou. **To bolo nesprávne** a vyplývalo to z 3-mesačného okna
bridge, kde „reaktivovaný" znamená iba „nenakúpil v tom istom kvartáli vlani". Pri
striktnej definícii (medzera nad 12 mesiacov) je obraz opačný, viď sekcia 6.

Rovnako platí opatrnosť pri klesajúcich trhoch: v 3-mesačnom okne vyzeralo šesť trhov
klesajúco, v ročnom okne (Jan–Júl YoY) je z väčších trhov v mínuse podstatne menej.
Pri malých trhoch je krátky výsek príliš hlučný.

Predchádzajúca verzia bola monolitický skript (`eda.py` + starý `report.py`). Je
nahradená týmto balíkom a nemá sa spúšťať; ak sa niekde nachádza, patrí zmazať.

---

## 8. Otvorené položky

1. **Zjednotiť identitu zákazníka** (viac e-mailov = jedna firma). Bez toho sú noví,
   churn aj reaktivácie nadhodnotené. Patrí do `data.load_orders()`.
2. **GMV-vážené verzie metrík „na zákazníka"** — nevážené merajú hlavne dlhý chvost
   drobných odberateľov. Toto je hlavné odporúčanie voči internému KPI.
3. **Porovnávacia tabuľka menovateľov KPI** (viď sekcia 6) doplniť do reportu ako
   samostatnú sekciu.
4. **Kumulatívny podiel GMV do hover histogramu.** Report obsahoval aj graf frekvencie
   s logaritmickými košmi, ktorý ukazoval GMV podľa frekvencie; bol odstránený na žiadosť.
   Jeho jediný unikátny prínos (kde sedí GMV) sa dá vrátiť ako druhý riadok
   v `hover_extras` bez vizuálnej zmeny grafu.
5. **Metrika „at risk"** — zákazníci aktívni za trailing 12M bez objednávky 90+ dní
   (v predchádzajúcej verzii 41 % bázy, 7,4 % T12M GMV). Nie je portovaná.
6. **Produktová a maržová dimenzia.** Rast priemernej objednávky môže byť mix efekt
   (bulk balenia), nie skutočný rast hodnoty. Vyžaduje ďalší dataset.
7. **Offline HTML.** Chart.js sa ťahá z `cdnjs.cloudflare.com` (`CHARTJS_CDN`
   v `report.py`); bez internetu sa grafy nezobrazia. Na intranet treba knižnicu
   vložiť inline.

---

## 9. Konvencie kódu

Autorove požiadavky, ktoré treba dodržať pri ďalších úpravách:

- Čitateľnosť pred optimalizáciou. Radšej `for` cyklus než pipeline operátorov
  cez niekoľko riadkov.
- Premenná, ktorá je vhodný kandidát na konštantu, patrí na vrch `constants.py`,
  nie doprostred funkcie.
- Funkcia robí jednu vec. Keď sa začne rozrastať, dekomponovať.
- Kód sa môže rozdeliť do viacerých súborov, ak to pomôže dekompozícii.
- Pri práci na kóde si vyžiadať súhlas pred zmenami, ak nie je povedané inak.

---

## 10. Známe pasce

**Escapovanie v HTML.** Popisky pásiem ako `<0,5k €` prehliadač interpretuje ako začiatok
tagu a popisok zmizne. `report.escape()` sa musí použiť na obsah tabuliek, hlavičky
a legendy. Na tomto sa už raz stratil celý prvý riadok tabuľky.

**Žiadna druhá os.** Keď majú dve série rôzne jednotky, patria do dvoch grafov alebo
sa musí použiť `value_format` na úrovni série (tooltip potom formátuje správne, ale
os zostáva jedna).

**Kontrola grafov bez prehliadača.** JS z reportu sa dá spustiť v Node so stubmi
a overiť, že sa všetky grafy postavia a callbacky nehádžu chybu:

```javascript
const created = [];
class Chart { constructor(el, cfg) { created.push({el, cfg}); } }
Chart.defaults = {font: {}};
global.document = { getElementById: id => id };
global.Chart = Chart;
// sem vložiť obsah <script> z vygenerovaného HTML
for (const c of created) {
  const cfg = c.cfg;
  for (const ds of cfg.data.datasets) {
    const ax = cfg.options.indexAxis === 'y' ? cfg.options.scales.x : cfg.options.scales.y;
    ax.ticks.callback(10);
    cfg.options.plugins.tooltip.callbacks.label({parsed: {x: 10, y: 10}, dataset: ds});
  }
  cfg.options.plugins.tooltip.callbacks.afterBody([{dataIndex: 0}]);
}
console.log('grafov:', created.length);
```

**Kontrola dĺžok sérií.** Ak séria nemá rovnaký počet hodnôt ako `labels`, Chart.js
to nenahlási — bary sa len tichým posunom priradia k nesprávnym popiskom.
Overiť parsovaním `const SPECS = ...` z vygenerovaného HTML.

**Odstránenie grafu.** Treba odstrániť aj metriku z `main.compute_metrics()`, aj
konštanty, ktoré používala, a skontrolovať `conclusions()` v `sections.py` — tá siaha
do metrík pozíciovo (`iloc`) a po zmene košov histogramu ukazovala na nesprávny riadok.
Pri histograme frekvencie sa preto používa `.loc["0"]`, `.loc["1"]`, nie `iloc`.
