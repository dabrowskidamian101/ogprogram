import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE Z SECRETS ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Skonfiguruj Secrets w Streamlit Cloud (URL i KEY)!")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# --- STYLIZACJA I FUNKCJE ---
def koloruj_niskie_stany(row):
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    return [''] * len(row)

st.set_page_config(page_title="ProManager ERP", layout="wide")

# Dashboard UI
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

# --- BEZPIECZNE POBIERANIE DANYCH ---
def fetch_data():
    try:
        res = supabase.table("produkty").select("id, nazwa, liczba, jednostka, cena, stan_minimalny, kategoria(nazwa)").execute()
        if not res.data:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria'])
        
        df = pd.DataFrame(res.data)
        df['Kategoria'] = df['kategoria'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
        df = df.drop(columns=['kategoria']).rename(columns={
            'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
            'cena': 'Cena', 'stan_minimalny': 'Stan Min.'
        })
        # Wymuszanie typów numerycznych dla poprawnego formatowania
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.warning(f"Baza danych jest pusta lub niekompletna. Dodaj pierwszy towar!")
        return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria'])

df_prod = fetch_data()

# --- STATYSTYKI ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("📦 Towary", len(df_prod))
with c2: 
    val = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość", f"{val:,.2f} zł")
with c3: 
    kat_n = len(df_prod['Kategoria'].unique()) if not df_prod.empty else 0
    st.metric("📂 Kategorie", kat_n)
with c4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Do zamówienia", niskie)

# --- ZAKŁADKI ---
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj", "📜 Historia", "📊 Analiza"])

# 1. PRZEGLĄD (Z FILTROWANIEM I SORTOWANIEM)
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        f1, f2 = st.columns([2, 1])
        with f1: szukaj = st.text_input("🔍 Szukaj...")
        with f2: sortuj = st.selectbox("Sortuj wg", options=df_prod.columns.tolist(), index=1)
        
        df_v = df_prod.copy()
        if szukaj:
            df_v = df_v[df_v['Produkt'].str.contains(szukaj, case=False)]
        df_v = df_v.sort_values(by=sortuj)

        st.dataframe(df_v.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f}', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1), use_container_width=True, hide_index=True)

# 2. PRZYJĘCIE/WYDANIE (KROK 1.00)
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch"):
            p_wyb = st.selectbox("Produkt", options=df_prod['Produkt'].tolist())
            t_op = st.radio("Operacja", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1.0, step=1.0, format="%.2f")
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_wyb].iloc[0]
                nowa_q = row['Ilość'] + ile if t_op == "Przyjęcie" else row['Ilość'] - ile
                if t_op == "Wydanie" and row['Ilość'] < ile:
                    st.error("Brak towaru!")
                else:
                    supabase.table("produkty").update({"liczba": nowa_q}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p_wyb, "typ": t_op.upper(), "ilosc": ile, "jednostka": row['Jm']
                    }).execute()
                    st.rerun()

# 3. REJESTRACJA
with tabs[2]:
    kat_data = supabase.table("kategoria").select("*").execute().data
    with st.form("reg"):
        n = st.text_input("Nazwa")
        jm = st.selectbox("Jednostka", ["szt", "kg", "m"])
        k = st.selectbox("Kategoria", options=[x['nazwa'] for x in kat_data] if kat_data else [])
        c = st.number_input("Cena", min_value=0.0, step=1.0)
        sm = st.number_input("Stan min.", min_value=0.0, step=1.0)
        si = st.number_input("Stan pocz.", min_value=0.0, step=1.0)
        if st.form_submit_button("Dodaj"):
            kid = next(x['id'] for x in kat_data if x['nazwa'] == k)
            supabase.table("produkty").insert({"nazwa":n, "liczba":si, "jednostka":jm, "cena":c, "stan_minimalny":sm, "kategoria_id":kid}).execute()
            st.rerun()

# 4. EDYCJA I HISTORIA (Logika analogiczna jak wyżej, z formatowaniem .2f)
# ... (reszta kodu z poprzedniej wersji z dodanymi filtrami w historii)
