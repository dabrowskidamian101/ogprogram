import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# --- KONFIGURACJA POŁĄCZENIA ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception:
    st.error("Błąd kluczy w Secrets! Sprawdź ustawienia w Streamlit Cloud.")
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
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria', 'kategoria_id']), df_k
        
        if not df_k.empty:
            df_f = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_f = df_f.rename(columns={'nazwa': 'Produkt', 'liczba': 'Ilość', 'cena': 'Cena', 'nazwa_kat': 'Kategoria'})
        else:
            df_f = df_p.copy()
            df_f['Kategoria'] = "Brak"

        for col in ['Ilość', 'Cena']:
            if col in df_f.columns:
                df_f[col] = pd.to_numeric(df_f[col], errors='coerce').fillna(0)
            
        return df_f[['id', 'Produkt', 'Ilość', 'Cena', 'Kategoria', 'kategoria_id']], df_k
    except Exception:
        return pd.DataFrame(), pd.DataFrame()

df_prod, df_kat = get_data()

# --- DASHBOARD ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

c1, c2, c3 = st.columns(3)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))

# NOWA STRUKTURA ZAKŁADEK
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "🏷️ Dodaj kategorię", "✏️ Edytuj towar", "📜 Historia"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("🔍 Stan magazynowy")
    if not df_prod.empty:
        df_display = df_prod.drop(columns=['kategoria_id']).copy()
        df_display.insert(0, 'Lp.', range(1, len(df_display) + 1))
        st.dataframe(df_display.drop(columns=['id']).style.format({'Ilość': '{:.2f}', 'Cena': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# 2. RUCH TOWARU
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch_form"):
            p_name = st.selectbox("Wybierz produkt", df_prod['Produkt'].tolist())
            t_type = st.radio("Rodzaj operacji", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_name].iloc[0]
                nowa = int(row['Ilość'] + ile if t_type == "Przyjęcie" else row['Ilość'] - ile)
                if t_type == "Wydanie" and row['Ilość'] < ile:
                    st.error("Błąd: Brak towaru!")
                else:
                    supabase.table("produkty").update({"liczba": int(nowa)}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({"data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"), "towar": p_name, "typ": t_type.upper(), "ilosc": int(ile)}).execute()
                    st.success("Zaktualizowano!")
                    st.rerun()

# 3. ZAREJESTRUJ NOWY TOWAR
with tabs[2]:
    if df_kat.empty:
        st.error("Najpierw dodaj kategorię!")
    else:
        with st.form("reg_form"):
            n = st.text_input("Nazwa towaru")
            k_name = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            c = st.number_input("Cena", min_value=0, step=1)
            si = st.number_input("Stan początkowy", min_value=0, step=1)
            if st.form_submit_button("Zarejestruj"):
                if n:
                    kid = int(df_kat[df_kat['nazwa'] == k_name]['id'].iloc[0])
                    supabase.table("produkty").insert({"nazwa": str(n), "liczba": int(si), "cena": int(c), "kategoria_id": kid}).execute()
                    st.rerun()

# 4. DODAJ KATEGORIĘ (NOWA ZAKŁADKA)
with tabs[3]:
    ca, cb = st.columns(2)
    with ca:
        st.subheader("➕ Dodaj nową kategorię")
        with st.form("add_kat_form"):
            nowa_kat_nazwa = st.text_input("Nazwa kategorii")
            if st.form_submit_button("Zapisz kategorię"):
                if nowa_kat_nazwa:
                    supabase.table("kategoria").insert({"nazwa": nowa_kat_nazwa}).execute()
                    st.success("Dodano kategorię!")
                    st.rerun()
    with cb:
        st.subheader("🗑️ Usuń kategorię")
        if not df_kat.empty:
            kat_do_usuniecia = st.selectbox("Wybierz kategorię do usunięcia", df_kat['nazwa'].tolist())
            if st.button("Usuń kategorię"):
                id_kat = int(df_kat[df_kat['nazwa'] == kat_do_usuniecia]['id'].iloc[0])
                try:
                    supabase.table("kategoria").delete().eq("id", id_kat).execute()
                    st.success("Usunięto!")
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, do której są przypisane produkty!")

# 5. EDYTUJ TOWAR (ZMODYFIKOWANA ZAKŁADKA)
with tabs[4]:
    st.subheader("✏️ Edycja parametrów towaru")
    if not df_prod.empty:
        # Wybór produktu do edycji
        produkt_do_edycji = st.selectbox("Wybierz produkt do zmiany danych", df_prod['Produkt'].tolist())
        dane_produktu = df_prod[df_prod['Produkt'] == produkt_do_edycji].iloc[0]
        
        with st.form("edit_prod_form"):
            nowa_nazwa = st.text_input("Zmień nazwę", value=dane_produktu['Produkt'])
            nowa_cena = st.number_input("Zmień cenę", value=int(dane_produktu['Cena']), min_value=0, step=1)
            # Domyślnie ustawiamy obecną kategorię
            obecna_kat_idx = df_kat['nazwa'].tolist().index(dane_produktu['Kategoria']) if dane_produktu['Kategoria'] in df_kat['nazwa'].tolist() else 0
            nowa_kat = st.selectbox("Zmień kategorię", df_kat['nazwa'].tolist(), index=obecna_kat_idx)
            
            col_e1, col_e2 = st.columns(2)
            with col_e1:
                if st.form_submit_button("Zapisz zmiany"):
                    kid_new = int(df_kat[df_kat['nazwa'] == nowa_kat]['id'].iloc[0])
                    supabase.table("produkty").update({
                        "nazwa": nowa_nazwa, 
                        "cena": int(nowa_cena), 
                        "kategoria_id": kid_new
                    }).eq("id", int(dane_produktu['id'])).execute()
                    st.success("Zaktualizowano dane produktu!")
                    st.rerun()
            with col_e2:
                if st.form_submit_button("Usuń całkowicie ten produkt"):
                    supabase.table("produkty").delete().eq("id", int(dane_produktu['id'])).execute()
                    st.warning("Produkt został usunięty.")
                    st.rerun()
    else:
        st.info("Brak towarów do edycji.")

# 6. HISTORIA
with tabs[5]:
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            df_h = pd.DataFrame(res_h.data)
            df_h.insert(0, 'Lp.', range(1, len(df_h) + 1))
            st.dataframe(df_h[['Lp.', 'data_operacji', 'towar', 'typ', 'ilosc']].rename(columns={
                'data_operacji': 'Data', 'towar': 'Produkt', 'typ': 'Typ', 'ilosc': 'Ilość'
            }), use_container_width=True, hide_index=True)
        else:
            st.info("Brak wpisów.")
    except:
        st.error("Błąd tabeli historia.")
