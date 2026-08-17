import pandas as pd

# Uprav cestu k súboru, ak ho máš uložený inde
file_path = "../data/b2b_orders_cleaned_w_company_name_3.xlsx"

print(f"Načítavam dáta z: {file_path} ...")
df = pd.read_excel(file_path, dtype=str)

# ==========================================
# 1. POROVNANIE POČTOV (Email vs Firma)
# ==========================================
email_clean = df["customer_email"].str.strip().str.lower()
pocet_email = email_clean.nunique()

if "company_bill" in df.columns:
    company_clean = df["company_bill"].str.strip().str.lower().replace("", None)
    cust_company = company_clean.fillna(email_clean)
else:
    cust_company = email_clean

pocet_firma = cust_company.nunique()

print("\n" + "-" * 45)
print(f"Počet zákazníkov (Zákazník = email): {pocet_email}")
print(f"Počet zákazníkov (Zákazník = firma): {pocet_firma}")
print(f"Zoskupením podľa firmy sa počet znížil o: {pocet_email - pocet_firma}")
print("-" * 45 + "\n")


# ==========================================
# 2. VÝPIS EMAILOV S VIACERÝMI FIRMAMI
# ==========================================
# Odstránime riadky, kde názov firmy úplne chýba
df_companies = df.dropna(subset=['company_bill']).copy()

# Ponecháme pôvodnú veľkosť písmen, len odstránime medzery na krajoch
df_companies['company_clean'] = df_companies['company_bill'].str.strip()

# Zoskupíme podľa e-mailu a vytvoríme zoznam unikátnych názvov firiem
companies_per_email = df_companies.groupby('customer_email')['company_clean'].unique()

# Vyfiltrujeme len tie e-maily, ktoré majú viac ako 1 unikátny názov
multiple_companies = companies_per_email[companies_per_email.apply(len) > 1]

# Zoradíme výsledky podľa počtu unikátnych názvov (klesajúco)
multiple_companies = multiple_companies.loc[multiple_companies.apply(len).sort_values(ascending=False).index]

print("Ukážka e-mailov s viacerými názvami firiem:\n" + "="*45)

# Vypíšeme Top 10 e-mailov a ich konkrétne názvy firiem
for email, companies in multiple_companies.head(10).items():
    print(f"E-mail: {email} (počet variantov: {len(companies)})")
    for company in companies:
        print(f"  - {company}")
    print("-" * 45)