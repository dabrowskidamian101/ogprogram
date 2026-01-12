import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE PRZEZ SECRETS ---
try:
    # Pobieranie danych z Twoich Secrets (widocznych na image_af0202.png)
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Błąd konfiguracji kluczy Supabase. Sprawdź zakładkę Secrets w Streamlit Cloud.")
    st.stop()

# --- STYLIZACJA ---
st.set_page_config(page_title="Magazyn Pro", layout="wide")
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.1);
        border: 1px solid rgba(120, 120, 120, 0.2);
        padding: 15px; border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNKCJE POBIERANIA DANYCH ---
def fetch_products():
    try:
        # Pobieranie z relacją do kategorii
        res = supabase.table("produkty").select("id, nazwa, liczba, jednostka, cena, stan_minimalny, kategoria(nazwa)").execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        # Rozpakowanie zagnieżdżonej nazwy kategorii
        df['Kategoria'] = df['kategoria'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
        df = df.drop(columns=['kategoria']).rename(columns={
            'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
            'cena': 'Cena', 'stan_minimalny': 'Stan Min.'
        })
        # Konwersja na liczby dla zaokrągleń (image_0fcd2e.png pokazuje nadmiar zer)
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame()

def fetch_categories():
    try:
        res = supabase.table("kategoria").select("*").execute()
        return res.data if res.data else []
    except:
        return []

# Pobranie danych na starcie
df_prod = fetch_products()
kat_data = fetch_categories()

# --- DASHBOARD ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("📦 Towary", len(df_prod))
with c2: 
    val = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość", f"{val:,.2f} zł")
with c3: st.metric("📂 Kategorie", len(kat_data))
with c4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Niskie stany", niskie)

# --- ZAKŁADKI ---
tab_przeglad, tab_operacje, tab_rejestracja, tab_edycja, tab_historia = st.tabs([
    "🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj Towar/Kategorię", "📜 Historia"
])

# 1. PRZEGLĄD
with tab_przeglad:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        # Formatowanie do 2 miejsc po przecinku (naprawia problem z image_0fcd2e.png)
        st.dataframe(df_prod.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f} zł', 'Stan Min.': '{:.2f}'
        }), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta. Zacznij od dodania kategorii w zakładce 'Edytuj'.")

# 2. PRZYJĘCIE/WYDANIE
with tab_operacje:
    if not df_prod.empty:
        with st.form("form_ruch"):
            p_wyb = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            typ_op = st.radio("Operacja", ["Przyjęcie (+)", "Wydanie (-)"])
            # Krok 1.0 dla liczb całkowitych
            ile = st.number_input("Ilość", min_value=1.0, step=1.0, format="%.2f")
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_wyb].iloc[0]
                nowa_q = row['Ilość'] + ile if "+" in typ_op else row['Ilość'] - ile
                if "-" in typ_op and row['Ilość'] < ile:
                    st.error("Brak towaru na stanie!")
                else:
                    supabase.table("produkty").update({"liczba": nowa_q}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p_wyb, "typ": typ_op, "ilosc": ile, "jednostka": row['Jm']
                    }).execute()
                    st.success("Zaktualizowano stan!")
                    st.rerun()
    else:
        st.warning("Najpierw zarejestruj towary.")

# 3. ZAREJESTRUJ
with tab_rejestracja:
    if not kat_data:
        st.error("Dodaj najpierw kategorię w zakładce 'Edytuj Towar/Kategorię'!")
    else:
        with st.form("reg_form"):
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                n = st.text_input("Nazwa produktu")
                jm = st.selectbox("Jm", ["szt", "kg", "m", "l"])
                k = st.selectbox("Kategoria", options=[x['nazwa'] for x in kat_data])
            with c_r2:
                c = st.number_input("Cena netto", min_value=0.0, step=1.0, format="%.2f")
                sm = st.number_input("Stan minimalny", min_value=0.0, step=1.0, format="%.2f")
                si = st.number_input("Stan początkowy", min_value=0.0, step=1.0, format="%.2f")
            if st.form_submit_button("Dodaj produkt"):
                kid = next(x['id'] for x in kat_data if x['nazwa'] == k)
                supabase.table("produkty").insert({
                    "nazwa": n, "liczba": si, "jednostka": jm, 
                    "cena": c, "stan_minimalny": sm, "kategoria_id": kid
                }).execute()
                st.rerun()

# 4. EDYCJA I DODAWANIE KATEGORII
with tab_edycja:
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("➕ Dodaj kategorię")
        with st.form("kat_form"):
            nk = st.text_input("Nazwa nowej kategorii")
            if st.form_submit_button("Zapisz kategorię"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.rerun()
    with col_e2:
        st.subheader("✏️ Zarządzaj produktami")
        if not df_prod.empty:
            t_ed = st.selectbox("Towar do zmiany", options=df_prod['Produkt'].tolist())
            t_row = df_prod[df_prod['Produkt'] == t_ed].iloc[0]
            # Formularz edycji (image_10aa27.png)
            new_c = st.number_input("Nowa cena", value=float(t_row['Cena']), step=1.0, format="%.2f")
            new_m = st.number_input("Nowy stan min.", value=float(t_row['Stan Min.']), step=1.0, format="%.2f")
            if st.button("Zapisz zmiany w towarze"):
                supabase.table("produkty").update({"cena": new_c, "stan_minimalny": new_m}).eq("id", int(t_row['id'])).execute()
                st.rerun()
        else:
            st.info("Brak towarów do edycji.")

# 5. HISTORIA
with tab_historia:
    st.subheader("Historia operacji")
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            st.dataframe(pd.DataFrame(res_h.data)[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']], use_container_width=True, hide_index=True)
        else:
            st.info("Brak historii.")
    except:
        st.info("Brak tabeli historii.")
