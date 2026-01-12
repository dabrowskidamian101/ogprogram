import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- KONFIGURACJA POŁĄCZENIA ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception:
    st.error("Błąd kluczy w Secrets! Sprawdź czy nazwy w Streamlit Secrets są poprawne.")
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

# --- FUNKCJE POBIERANIA DANYCH (BEZPIECZNE) ---
def get_all_data():
    try:
        # Pobieramy produkty i kategorie osobno, aby uniknąć błędów Join w API
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)

        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']), df_k
        
        # Łączenie danych w Pythonie (Panda Merge)
        if not df_k.empty:
            df_final = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_final = df_final.rename(columns={
                'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
                'cena': 'Cena', 'stan_minimalny': 'Stan Min.', 'nazwa_kat': 'Kategoria'
            })
        else:
            df_final = df_p.copy()
            df_final['Kategoria'] = "Brak"

        # Formatowanie liczb
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
            
        return df_final[['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']], df_k
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# Pobranie danych
df_prod, df_kat = get_all_data()

# --- INTERFEJS ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

# Statystyki
c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))
c4.metric("⚠️ Niskie stany", len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0)

tabs = st.tabs(["🔍 Przegląd", "🔄 Ruch towaru", "📝 Zarejestruj", "✏️ Edycja/Kategorie", "📜 Historia"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        st.dataframe(df_prod.style.format({'Ilość': '{:.2f}', 'Cena': '{:.2f}', 'Stan Min.': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta. Dodaj kategorię i zarejestruj towar.")

# 2. RUCH TOWARU (PRZYJĘCIE/WYDANIE)
with tabs[1]:
    st.subheader("Przyjęcie / Wydanie towaru")
    if not df_prod.empty:
        with st.form("ruch"):
            p = st.selectbox("Wybierz towar", df_prod['Produkt'].tolist())
            t = st.radio("Rodzaj operacji", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość (całkowita)", min_value=1.0, step=1.0)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p].iloc[0]
                nowa = row['Ilość'] + ile if t == "Przyjęcie" else row['Ilość'] - ile
                if t == "Wydanie" and row['Ilość'] < ile:
                    st.error("Błąd: Brak towaru na stanie!")
                else:
                    supabase.table("produkty").update({"liczba": nowa}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p, "typ": t.upper(), "ilosc": ile, "jednostka": row['Jm']
                    }).execute()
                    st.success("Zaktualizowano stan magazynowy!")
                    st.rerun()
    else:
        st.warning("Najpierw dodaj produkty.")

# 3. ZAREJESTRUJ NOWY TOWAR
with tabs[2]:
    st.subheader("Nowy towar w systemie")
    if df_kat.empty:
        st.error("Dodaj najpierw kategorię w zakładce Edycja!")
    else:
        with st.form("reg"):
            n = st.text_input("Nazwa towaru")
            jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l"])
            k_name = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            c = st.number_input("Cena netto", min_value=0.0, step=1.0)
            sm = st.number_input("Stan minimalny", min_value=0.0, step=1.0)
            if st.form_submit_button("Dodaj produkt"):
                if n:
                    kid = int(df_kat[df_kat['nazwa'] == k_name]['id'].iloc[0])
                    supabase.table("produkty").insert({
                        "nazwa": n, "liczba": 0, "jednostka": jm, "cena": c, "stan_minimalny": sm, "kategoria_id": kid
                    }).execute()
                    st.success("Zarejestrowano pomyślnie!")
                    st.rerun()

# 4. EDYCJA I KATEGORIE
with tabs[3]:
    c_a, c_b = st.columns(2)
    with c_a:
        st.subheader("➕ Nowa kategoria")
        with st.form("k_add"):
            nk = st.text_input("Nazwa")
            if st.form_submit_button("Zapisz kategorię"):
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
    st.subheader("Historia operacji")
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            st.dataframe(pd.DataFrame(res_h.data)[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']], use_container_width=True, hide_index=True)
        else:
            st.info("Brak historii.")
    except Exception:
        st.info("Brak danych w historii.")
