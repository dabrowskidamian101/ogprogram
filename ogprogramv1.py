import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE PRZEZ SECRETS ---
try:
    # Pobiera dane z Twoich Secrets (image_af0202.png)
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

# --- FUNKCJE POBIERANIA DANYCH ---
def get_all_data():
    try:
        # Pobieramy produkty i kategorie osobno, aby uniknąć błędów Join w API
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)

        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria']), df_k
        
        # Łączenie danych w Pythonie (zgodnie z Twoją bazą z image_afdba2.png)
        if not df_k.empty:
            df_final = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_final = df_final.rename(columns={
                'nazwa': 'Produkt', 'liczba': 'Ilość', 'cena': 'Cena', 'nazwa_kat': 'Kategoria'
            })
        else:
            df_final = df_p.copy()
            df_final['Kategoria'] = "Brak"

        # Konwersja na typy numeryczne dla poprawnego wyświetlania
        for col in ['Ilość', 'Cena']:
            df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
            
        return df_final[['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria']], df_k
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

# Pobranie danych
df_prod, df_kat = get_all_data()

# --- INTERFEJS ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

# Statystyki
c1, c2, c3 = st.columns(3)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))

tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj", "📜 Historia"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        # Formatowanie do 2 miejsc po przecinku naprawia nadmiar zer z image_0fcd2e.png
        st.dataframe(df_prod.style.format({'Ilość': '{:.2f}', 'Cena': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# 2. RUCH TOWARU
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch"):
            p = st.selectbox("Wybierz towar", df_prod['Produkt'].tolist())
            t = st.radio("Operacja", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p].iloc[0]
                nowa = int(row['Ilość'] + ile if t == "Przyjęcie" else row['Ilość'] - ile)
                if t == "Wydanie" and row['Ilość'] < ile:
                    st.error("Błąd: Brak towaru na stanie!")
                else:
                    # WYMUSZAMY int() dla kolumny liczba (bigint w Supabase)
                    supabase.table("produkty").update({"liczba": int(nowa)}).eq("id", int(row['id'])).execute()
                    st.success("Zaktualizowano stan!")
                    st.rerun()

# 3. ZAREJESTRUJ (FIX BŁĘDU Z OBRAZKA)
with tabs[2]:
    st.subheader("Rejestracja nowego towaru")
    if df_kat.empty:
        st.error("Najpierw dodaj kategorię!")
    else:
        with st.form("form_reg_final"):
            n = st.text_input("Nazwa towaru")
            k_nazwa = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            c = st.number_input("Cena", min_value=0, step=1)
            si = st.number_input("Stan początkowy", min_value=0, step=1)
            
            if st.form_submit_button("Zarejestruj produkt"):
                if n:
                    try:
                        kid = int(df_kat[df_kat['nazwa'] == k_nazwa]['id'].iloc[0])
                        # KLUCZOWA POPRAWKA: wymuszamy int() na polach liczba i cena, 
                        # żeby nie wysyłać "0.0" do kolumny typu bigint (int8)
                        supabase.table("produkty").insert({
                            "nazwa": str(n), 
                            "liczba": int(si), 
                            "cena": int(c), 
                            "kategoria_id": kid
                        }).execute()
                        st.success("Zarejestrowano pomyślnie!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd bazy: {e}")

# 4. EDYTUJ / KATEGORIE
with tabs[3]:
    ca, cb = st.columns(2)
    with ca:
        st.subheader("➕ Nowa kategoria")
        with st.form("k_add"):
            nk = st.text_input("Nazwa")
            if st.form_submit_button("Zapisz"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.rerun()
    with cb:
        st.subheader("🗑️ Usuń produkt")
        if not df_prod.empty:
            p_del = st.selectbox("Wybierz towar", df_prod['Produkt'].tolist())
            if st.button("Usuń bezpowrotnie"):
                id_del = int(df_prod[df_prod['Produkt'] == p_del]['id'].iloc[0])
                supabase.table("produkty").delete().eq("id", id_del).execute()
                st.rerun()

# 5. HISTORIA
with tabs[4]:
    st.info("Historia wymaga tabeli 'historia' w Supabase.")
