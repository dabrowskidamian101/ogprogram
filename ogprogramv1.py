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
    st.error("Błąd: Skonfiguruj Secrets (URL i KEY) w panelu Streamlit Cloud!")
    st.stop()

# Inicjalizacja klienta bez cache, aby widzieć zmiany natychmiast
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNKCJE I STYLIZACJA ---
def koloruj_niskie_stany(row):
    try:
        if row['Ilość'] <= row['Stan Min.']:
            return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    except:
        pass
    return [''] * len(row)

st.set_page_config(page_title="ProManager ERP", layout="wide")

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

# --- POBIERANIE DANYCH Z SUPABASE ---
def fetch_products():
    try:
        res = supabase.table("produkty").select("id, nazwa, liczba, jednostka, cena, stan_minimalny, kategoria(nazwa)").execute()
        if not res.data:
            return pd.DataFrame()
        df = pd.DataFrame(res.data)
        # Rozpakowanie nazwy kategorii
        df['Kategoria'] = df['kategoria'].apply(lambda x: x['nazwa'] if isinstance(x, dict) else "Brak")
        df = df.drop(columns=['kategoria']).rename(columns={
            'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
            'cena': 'Cena', 'stan_minimalny': 'Stan Min.'
        })
        # Konwersja na liczby dla zaokrągleń
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

# --- DASHBOARD (METRYKI) ---
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
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj Towar/Kategorię", "📜 Historia", "📊 Analiza"
])

# 1. PRZEGLĄD
with tab1:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        f1, f2 = st.columns([2, 1])
        with f1: szukaj = st.text_input("🔍 Filtruj po nazwie...")
        with f2: sortuj = st.selectbox("Sortuj wg", options=df_prod.columns.tolist(), index=1)
        
        df_v = df_prod.copy()
        if szukaj:
            df_v = df_v[df_v['Produkt'].str.contains(szukaj, case=False)]
        df_v = df_v.sort_values(by=sortuj)

        st.dataframe(df_v.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f}', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta. Przejdź do zakładki 'Edytuj Towar/Kategorię', aby dodać dane.")

# 2. PRZYJĘCIE/WYDANIE
with tab2:
    st.subheader("Ruch towaru")
    if not df_prod.empty:
        with st.form("form_ruch"):
            p_wyb = st.selectbox("Produkt", options=df_prod['Produkt'].tolist())
            t_op = st.radio("Typ operacji", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=1.0, step=1.0, format="%.2f")
            if st.form_submit_button("Wykonaj"):
                p_row = df_prod[df_prod['Produkt'] == p_wyb].iloc[0]
                nowa_q = p_row['Ilość'] + ile if t_op == "Przyjęcie" else p_row['Ilość'] - ile
                
                if t_op == "Wydanie" and p_row['Ilość'] < ile:
                    st.error("Błąd: Brak wystarczającej ilości towaru!")
                else:
                    supabase.table("produkty").update({"liczba": nowa_q}).eq("id", int(p_row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p_wyb, "typ": t_op.upper(), "ilosc": ile, "jednostka": p_row['Jm']
                    }).execute()
                    st.success("Zaktualizowano stan!")
                    st.rerun()
    else:
        st.warning("Najpierw zarejestruj produkty w systemie.")

# 3. ZAREJESTRUJ NOWY TOWAR
with tab3:
    st.subheader("Rejestracja towaru")
    if not kat_data:
        st.error("⚠️ Brak kategorii w bazie! Dodaj kategorię w następnej zakładce.")
    else:
        with st.form("form_reg"):
            c1, c2 = st.columns(2)
            with c1:
                n_name = st.text_input("Nazwa produktu")
                n_jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l"])
                n_kat = st.selectbox("Kategoria", options=[k['nazwa'] for k in kat_data])
            with c2:
                n_cena = st.number_input("Cena", min_value=0.0, step=1.0, format="%.2f")
                n_min = st.number_input("Stan min.", min_value=0.0, step=1.0, format="%.2f")
                n_start = st.number_input("Stan pocz.", min_value=0.0, step=1.0, format="%.2f")
            
            if st.form_submit_button("✅ Zarejestruj"):
                if n_name:
                    kid = next(k['id'] for k in kat_data if k['nazwa'] == n_kat)
                    supabase.table("produkty").insert({
                        "nazwa": n_name, "liczba": n_start, "jednostka": n_jm, 
                        "cena": n_cena, "stan_minimalny": n_min, "kategoria_id": kid
                    }).execute()
                    st.rerun()

# 4. EDYTUJ TOWAR / KATEGORIĘ (KLUCZOWA ZAKŁADKA)
with tab4:
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("➕ Dodaj kategorię")
        with st.form("form_add_kat"):
            new_kat = st.text_input("Nazwa nowej kategorii")
            if st.form_submit_button("Zapisz kategorię"):
                if new_kat:
                    try:
                        supabase.table("kategoria").insert({"nazwa": new_kat}).execute()
                        st.success(f"Dodano: {new_kat}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd zapisu. Sprawdź RLS w Supabase! ({e})")

    with col_e2:
        st.subheader("✏️ Zarządzaj towarami")
        if not df_prod.empty:
            t_edit = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            t_old = df_prod[df_prod['Produkt'] == t_edit].iloc[0]
            e_cena = st.number_input("Zmień cenę", value=float(t_old['Cena']), step=1.0)
            if st.button("💾 Zapisz"):
                supabase.table("produkty").update({"cena": e_cena}).eq("id", int(t_old['id'])).execute()
                st.rerun()
            if st.button("🗑️ USUŃ TOWAR"):
                supabase.table("produkty").delete().eq("id", int(t_old['id'])).execute()
                st.rerun()

# 5. HISTORIA
with tab5:
    st.subheader("Historia operacji")
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            df_h = pd.DataFrame(res_h.data)
            st.dataframe(df_h[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']], use_container_width=True, hide_index=True)
        else:
            st.info("Brak historii operacji.")
    except:
        st.info("Brak danych w historii.")

# 6. ANALIZA
with tab6:
    if not df_prod.empty:
        fig = px.pie(df_prod, values='Ilość', names='Kategoria', title="Udział kategorii w magazynie")
        st.plotly_chart(fig, use_container_width=True)
