import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except:
    st.error("Błąd kluczy w Secrets!")
    st.stop()

# --- STYLIZACJA ---
st.set_page_config(page_title="Magazyn Pro", layout="wide")
st.markdown("<style>[data-testid='stMetric'] {background-color: rgba(120,120,120,0.1); border: 1px solid rgba(120,120,120,0.2); padding: 15px; border-radius: 15px; color: white;}</style>", unsafe_allow_html=True)

# --- FUNKCJE POBIERANIA ---
def get_data():
    try:
        # Pobieramy produkty i kategorie osobno, żeby uniknąć błędów joinowania
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)

        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']), df_k
        
        # Łączymy dane w Pythonie (to bezpieczniejsze niż SQL Join w Supabase)
        if not df_k.empty:
            df_final = df_p.merge(df_k, left_on='kategoria_id', right_on='id', suffixes=('', '_kat'))
            df_final = df_final.rename(columns={
                'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
                'cena': 'Cena', 'stan_minimalny': 'Stan Min.', 'nazwa_kat': 'Kategoria'
            })
        else:
            df_final = df_p.copy()
            df_final['Kategoria'] = "Brak"

        # Zaokrąglenia dla estetyki (image_0fcd2e.png)
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
            
        return df_final[['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']], df_k
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame()

df_prod, df_kat = get_data()

# --- DASHBOARD ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))
c4.metric("⚠️ Niskie stany", len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0)

tabs = st.tabs(["🔍 Przegląd", "🔄 Ruch towaru", "📝 Zarejestruj", "✏️ Edycja/Kategorie", "📜 Historia"])

# 1. PRZEGLĄD
with tabs[0]:
    if not df_prod.empty:
        st.dataframe(df_prod.style.format({'Ilość': '{:.2f}', 'Cena': '{:.2f}', 'Stan Min.': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta. Dodaj kategorię i towar.")

# 2. RUCH TOWARU
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch"):
            p = st.selectbox("Produkt", df_prod['Produkt'].tolist())
            t = st.radio("Typ", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1.0, step=1.0)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p].iloc[0]
                nowa = row['Ilość'] + ile if t == "Przyjęcie" else row['Ilość'] - ile
                supabase.table("produkty").update({"liczba": nowa}).eq("id", int(row['id'])).execute()
                supabase.table("historia").insert({
                    "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "towar": p, "typ": t.upper(), "ilosc": ile, "jednostka": row['Jm']
                }).execute()
                st.rerun()

# 3. ZAREJESTRUJ
with tabs[2]:
    if df_kat.empty:
        st.warning("Dodaj najpierw kategorię!")
    else:
        with st.form("reg"):
            n = st.text_input("Nazwa")
            jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l"])
            k_nazwa = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            c = st.number_input("Cena", min_value=0.0, step=1.0)
            sm = st.number_input("Stan min.", min_value=0.0, step=1.0)
            if st.form_submit_button("Dodaj"):
                kid = int(df_kat[df_kat['nazwa'] == k_nazwa]['id'].iloc[0])
                supabase.table("produkty").insert({
                    "nazwa": n, "liczba": 0, "jednostka": jm, "cena": c, "stan_minimalny": sm, "kategoria_id": kid
                }).execute()
                st.rerun()

# 4. EDYCJA I KATEGORIE
with tabs[3]:
    c_a, c_b = st.columns(2)
    with c_a:
        st.subheader("➕ Nowa kategoria")
        with st.form("k_add"):
            nk = st.text_input("Nazwa")
            if st.form_submit_button("Zapisz"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.rerun()
    with c_b:
        st.subheader("🗑️ Usuń produkt")
        if not df_prod.empty:
            p_del = st.selectbox("Wybierz towar", df_prod['Produkt'].tolist())
            if st.button("Usuń bezpowrotnie"):
                id_del = int(df_prod[df_prod['Produkt'] == p_del]['id'].iloc[0])
                supabase.table("produkty").delete().eq("id", id_del).execute()
                st.rerun()

# 5. HISTORIA
with tabs[4]:
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            st.dataframe(pd.DataFrame(res_h.data), use_container_width=True, hide_index=True)
    except:
        st.info("Historia jest pusta.")
