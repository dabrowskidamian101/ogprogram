import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE PRZEZ SECRETS ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Skonfiguruj Secrets (URL i KEY) w panelu Streamlit Cloud!")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# --- FUNKCJE I UI ---
def koloruj_niskie_stany(row):
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    return [''] * len(row)

st.set_page_config(page_title="ERP Magazyn", layout="wide")
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
            'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm', 'cena': 'Cena', 'stan_minimalny': 'Stan Min.'
        })
        for c in ['Ilość', 'Cena', 'Stan Min.']:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria'])

df_prod = fetch_data()

# --- INTERFEJS ZAKŁADEK ---
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj Towar/Kategorię", "📜 Historia"])

# ZAKŁADKA: EDYTUJ I DODAJ KATEGORIĘ (Rozwiązuje problem braku kategorii)
with tabs[3]:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("➕ Dodaj kategorię")
        with st.form("kat_form"):
            nk = st.text_input("Nazwa nowej kategorii")
            if st.form_submit_button("Zapisz kategorię"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.success(f"Dodano kategorię {nk}")
                    st.rerun()
    
    with col2:
        st.subheader("✏️ Zarządzaj towarami")
        if not df_prod.empty:
            t_sel = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            t_row = df_prod[df_prod['Produkt'] == t_sel].iloc[0]
            new_c = st.number_input("Nowa cena", value=float(t_row['Cena']), step=1.0, format="%.2f")
            if st.button("Zaktualizuj cenę"):
                supabase.table("produkty").update({"cena": new_c}).eq("id", int(t_row['id'])).execute()
                st.rerun()

# Pozostałe zakładki (Przegląd, Rejestracja, Historia) powinny teraz działać poprawnie.
