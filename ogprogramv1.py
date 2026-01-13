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
def get_data():
    try:
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)
        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria']), df_k
        if not df_k.empty:
            df_f = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_f = df_f.rename(columns={'nazwa': 'Produkt', 'liczba': 'Ilość', 'cena': 'Cena', 'nazwa_kat': 'Kategoria'})
        else:
            df_f = df_p.copy()
            df_f['Kategoria'] = "Brak"
        for col in ['Ilość', 'Cena']:
            df_f[col] = pd.to_numeric(df_f[col], errors='coerce').fillna(0)
        return df_f[['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria']], df_k
    except:
        return pd.DataFrame(), pd.DataFrame()

df_prod, df_kat = get_data()

# --- DASHBOARD ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")
c1, c2, c3 = st.columns(3)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))

tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj", "📜 Historia"])

# 1. PRZEGLĄD
with tabs[0]:
    if not df_prod.empty:
        st.dataframe(df_prod.style.format({'Ilość': '{:.2f}', 'Cena': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# 2. RUCH TOWARU (Zapisuje do Historii)
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch"):
            p_name = st.selectbox("Produkt", df_prod['Produkt'].tolist())
            t_type = st.radio("Typ", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_name].iloc[0]
                nowa = int(row['Ilość'] + ile if t_type == "Przyjęcie" else row['Ilość'] - ile)
                if t_type == "Wydanie" and row['Ilość'] < ile:
                    st.error("Brak towaru!")
                else:
                    supabase.table("produkty").update({"liczba": nowa}).eq("id", int(row['id'])).execute()
                    # ZAPIS DO HISTORII
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p_name, "typ": t_type.upper(), "ilosc": int(ile), "jednostka": "szt"
                    }).execute()
                    st.success("Zaktualizowano!")
                    st.rerun()

# 3. ZAREJESTRUJ (Naprawa błędu BigInt)
with tabs[2]:
    if df_kat.empty:
        st.error("Dodaj kategorię!")
    else:
        with st.form("reg"):
            n = st.text_input("Nazwa")
            k_n = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            c = st.number_input("Cena", min_value=0, step=1)
            si = st.number_input("Stan pocz.", min_value=0, step=1)
            if st.form_submit_button("Zarejestruj"):
                if n:
                    kid = int(df_kat[df_kat['nazwa'] == k_n]['id'].iloc[0])
                    supabase.table("produkty").insert({
                        "nazwa": n, "liczba": int(si), "cena": int(c), "kategoria_id": kid
                    }).execute()
                    st.rerun()

# 4. EDYTUJ / KATEGORIE
with tabs[3]:
    ca, cb = st.columns(2)
    with ca:
        with st.form("k_add"):
            nk = st.text_input("Nowa kategoria")
            if st.form_submit_button("Zapisz"):
                if nk: supabase.table("kategoria").insert({"nazwa": nk}).execute(); st.rerun()
    with cb:
        if not df_prod.empty:
            p_del = st.selectbox("Usuń towar", df_prod['Produkt'].tolist())
            if st.button("Usuń"):
                supabase.table("produkty").delete().eq("id", int(df_prod[df_prod['Produkt'] == p_del]['id'].iloc[0])).execute()
                st.rerun()

# 5. HISTORIA
with tabs[4]:
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            st.dataframe(pd.DataFrame(res_h.data)[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']], use_container_width=True, hide_index=True)
        else:
            st.info("Historia jest pusta. Wykonaj przyjęcie lub wydanie towaru.")
    except Exception as e:
        st.error(f"Błąd tabeli historia: {e}. Upewnij się, że kliknąłeś RUN w SQL Editorze!")
