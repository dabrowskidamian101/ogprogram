import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- KONFIGURACJA POŁĄCZENIA SUPABASE ---
# Pobieranie danych z Twoich "Secrets"
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    st.error("Błąd: Nie znaleziono kluczy SUPABASE_URL lub SUPABASE_KEY w Secrets!")
    st.stop()

@st.cache_resource
def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase()

# --- FUNKCJE POMOCNICZE ---
def koloruj_niskie_stany(row):
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    return [''] * len(row)

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ProManager Supabase ERP", layout="wide", page_icon="🏢")

# Naprawa wyglądu metryk dla ciemnego motywu
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.1);
        border: 1px solid rgba(120, 120, 120, 0.2);
        padding: 15px; border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏢 Profesjonalny System Zarządzania Magazynem")

# --- POBIERANIE DANYCH ---
def fetch_data():
    # Pobieranie produktów z joinem kategorii
    res = supabase.table("produkty").select("id, nazwa, liczba, jednostka, cena, stan_minimalny, kategoria(nazwa)").execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        df['Kategoria'] = df['kategoria'].apply(lambda x: x['nazwa'] if x else "Brak")
        df = df.drop(columns=['kategoria'])
        df = df.rename(columns={
            'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
            'cena': 'Cena', 'stan_minimalny': 'Stan Min.'
        })
    return df

df_prod = fetch_data()

# --- STATYSTYKI (Dashboard) ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Razem produktów", len(df_prod))
with col2:
    wartosc = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość magazynu", f"{wartosc:,.2f} zł")
with col3:
    kat_count = supabase.table("kategoria").select("id", count="exact").execute().count
    st.metric("📂 Kategorie", kat_count)
with col4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Niskie stany", niskie)

# --- ZAKŁADKI ---
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj Towar/Kategorię", "📜 Historia", "📊 Analiza"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        c1, c2 = st.columns([2,1])
        with c1: szukaj = st.text_input("🔍 Filtruj i szukaj...")
        with c2: sortuj = st.selectbox("Sortuj wg", options=df_prod.columns.tolist(), index=1)
        
        df_v = df_prod.copy()
        if szukaj:
            df_v = df_v[df_v['Produkt'].str.contains(szukaj, case=False) | df_v['Kategoria'].str.contains(szukaj, case=False)]
        df_v = df_view = df_v.sort_values(by=sortuj)

        st.dataframe(df_v.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f}', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# 2. PRZYJĘCIE/WYDANIE
with tabs[1]:
    st.subheader("Ruch towaru")
    if not df_prod.empty:
        with st.form("ruch_form"):
            wyb_p = st.selectbox("Produkt", options=df_prod['Produkt'].tolist())
            typ = st.radio("Typ", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1.0, step=1.0, format="%.2f")
            if st.form_submit_button("Zatwierdź"):
                p_row = df_prod[df_prod['Produkt'] == wyb_p].iloc[0]
                nowa_q = p_row['Ilość'] + ile if typ == "Przyjęcie" else p_row['Ilość'] - ile
                
                if typ == "Wydanie" and p_row['Ilość'] < ile:
                    st.error("Błąd: Niewystarczający stan!")
                else:
                    supabase.table("produkty").update({"liczba": nowa_q}).eq("id", int(p_row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": wyb_p, "typ": typ.upper(), "ilosc": ile, "jednostka": p_row['Jm']
                    }).execute()
                    st.success("Zaktualizowano stan w Supabase!")
                    st.rerun()

# 3. REJESTRACJA
with tabs[2]:
    st.subheader("Zarejestruj nowy towar")
    k_res = supabase.table("kategoria").select("*").execute()
    k_data = k_res.data
    with st.form("reg_form"):
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Nazwa")
            jm = st.selectbox("Jm", ["szt", "kg", "m", "l"])
            kat = st.selectbox("Kategoria", options=[k['nazwa'] for k in k_data])
        with c2:
            price = st.number_input("Cena", min_value=0.0, step=1.0, format="%.2f")
            s_min = st.number_input("Stan min.", min_value=0.0, step=1.0, format="%.2f")
            s_init = st.number_input("Stan pocz.", min_value=0.0, step=1.0, format="%.2f")
        
        if st.form_submit_button("Zarejestruj"):
            kid = next(k['id'] for k in k_data if k['nazwa'] == kat)
            supabase.table("produkty").insert({
                "nazwa": name, "liczba": s_init, "jednostka": jm, 
                "cena": price, "stan_minimalny": s_min, "kategoria_id": kid
            }).execute()
            st.success("Dodano produkt!")
            st.rerun()

# 4. EDYCJA I USUWANIE
with tabs[3]:
    c_e1, c_e2 = st.columns(2)
    with c_e1:
        st.subheader("Edytuj / Usuń Towar")
        if not df_prod.empty:
            t_edit = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            t_data = df_prod[df_prod['Produkt'] == t_edit].iloc[0]
            new_p = st.number_input("Nowa cena", value=float(t_data['Cena']), step=1.0, format="%.2f")
            new_m = st.number_input("Nowy stan min.", value=float(t_data['Stan Min.']), step=1.0, format="%.2f")
            
            if st.button("Zapisz zmiany"):
                supabase.table("produkty").update({"cena": new_p, "stan_minimalny": new_m}).eq("id", int(t_data['id'])).execute()
                st.rerun()
            if st.button("❌ USUŃ TOWAR"):
                supabase.table("produkty").delete().eq("id", int(t_data['id'])).execute()
                st.rerun()
    with c_e2:
        st.subheader("Zarządzaj Kategoriami")
        new_k = st.text_input("Nowa kategoria")
        if st.button("Dodaj kategorię"):
            supabase.table("kategoria").insert({"nazwa": new_k}).execute()
            st.rerun()
        st.divider()
        if k_data:
            k_del = st.selectbox("Usuń kategorię", options=[k['nazwa'] for k in k_data])
            if st.button("Usuń wybraną kategorię"):
                supabase.table("kategoria").delete().eq("nazwa", k_del).execute()
                st.rerun()

# 5. HISTORIA
with tabs[4]:
    st.subheader("Historia operacji")
    h_res = supabase.table("historia").select("*").order("id", desc=True).execute()
    if h_res.data:
        df_h = pd.DataFrame(h_res.data)
        st.dataframe(df_h[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']].rename(columns={
            'data_operacji': 'Data', 'towar': 'Produkt', 'typ': 'Typ', 'ilosc': 'Ilość', 'jednostka': 'Jm'
        }).style.format({'Ilość': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Brak wpisów w historii.")

# 6. ANALIZA
with tabs[5]:
    if not df_prod.empty:
        fig = px.pie(df_prod, values='Ilość', names='Kategoria', title="Udział kategorii")
        st.plotly_chart(fig, use_container_width=True)
