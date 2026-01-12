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
    st.error("Błąd: Skonfiguruj Secrets (URL i KEY) w Streamlit Cloud!")
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
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception:
        return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria'])

df_prod = fetch_data()

# --- STATYSTYKI ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("📦 Towary", len(df_prod))
with c2: 
    val = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość", f"{val:,.2f} zł")
with c3: 
    try:
        kat_res = supabase.table("kategoria").select("id", count="exact").execute()
        st.metric("📂 Kategorie", kat_res.count if kat_res.count else 0)
    except:
        st.metric("📂 Kategorie", 0)
with c4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Niskie stany", niskie)

# --- ZAKŁADKI ---
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj nowy towar", "✏️ Edytuj Towar/Kategorię", "📜 Historia", "📊 Analiza"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        f1, f2 = st.columns([2, 1])
        with f1: szukaj = st.text_input("🔍 Szukaj produktu...")
        with f2: sortuj = st.selectbox("Sortuj wg", options=df_prod.columns.tolist(), index=1)
        
        df_v = df_prod.copy()
        if szukaj:
            df_v = df_v[df_view['Produkt'].str.contains(szukaj, case=False)]
        df_v = df_v.sort_values(by=sortuj)

        st.dataframe(df_v.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f} zł', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta. Zacznij od dodania kategorii i towarów.")

# 2. PRZYJĘCIE/WYDANIE
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch"):
            p_wyb = st.selectbox("Wybierz produkt", options=df_prod['Produkt'].tolist())
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
    else:
        st.info("Brak produktów do obsługi.")

# 3. REJESTRACJA NOWEGO TOWARU
with tabs[2]:
    st.subheader("Zarejestruj produkt")
    try:
        kat_data = supabase.table("kategoria").select("*").execute().data
    except:
        kat_data = []
        
    if not kat_data:
        st.warning("⚠️ Najpierw dodaj kategorię w zakładce 'Edytuj Towar/Kategorię'!")
    else:
        with st.form("reg"):
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                n = st.text_input("Nazwa produktu")
                jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l"])
                k = st.selectbox("Kategoria", options=[x['nazwa'] for x in kat_data])
            with c_r2:
                c = st.number_input("Cena netto", min_value=0.0, step=1.0, format="%.2f")
                sm = st.number_input("Stan minimalny", min_value=0.0, step=1.0, format="%.2f")
                si = st.number_input("Stan początkowy", min_value=0.0, step=1.0, format="%.2f")
            
            if st.form_submit_button("Zarejestruj towar"):
                if n:
                    kid = next(x['id'] for x in kat_data if x['nazwa'] == k)
                    supabase.table("produkty").insert({
                        "nazwa": n, "liczba": si, "jednostka": jm, 
                        "cena": c, "stan_minimalny": sm, "kategoria_id": kid
                    }).execute()
                    st.success("Dodano produkt!")
                    st.rerun()

# 4. EDYTUJ TOWAR / KATEGORIĘ (TUTAJ JEST DODAWANIE KATEGORII)
with tabs[3]:
    col_ed1, col_ed2 = st.columns(2)
    
    with col_ed1:
        st.subheader("✏️ Zarządzaj produktami")
        if not df_prod.empty:
            t_ed = st.selectbox("Wybierz produkt", options=df_prod['Produkt'].tolist())
            t_row = df_prod[df_prod['Produkt'] == t_ed].iloc[0]
            e_cena = st.number_input("Nowa cena", value=float(t_row['Cena']), step=1.0, format="%.2f")
            e_min = st.number_input("Nowy stan min.", value=float(t_row['Stan Min.']), step=1.0, format="%.2f")
            
            ce1, ce2 = st.columns(2)
            with ce1:
                if st.button("Zapisz zmiany"):
                    supabase.table("produkty").update({"cena": e_cena, "stan_minimalny": e_min}).eq("id", int(t_row['id'])).execute()
                    st.rerun()
            with ce2:
                if st.button("🗑️ Usuń produkt"):
                    supabase.table("produkty").delete().eq("id", int(t_row['id'])).execute()
                    st.rerun()
        else:
            st.info("Brak towarów do edycji.")

    with col_ed2:
        st.subheader("📂 Zarządzaj kategoriami")
        # FORMULARZ DODAWANIA KATEGORII
        with st.form("add_kat_form"):
            new_kat_name = st.text_input("Nazwa nowej kategorii")
            new_kat_desc = st.text_area("Opis (opcjonalnie)")
            if st.form_submit_button("➕ Dodaj kategorię"):
                if new_kat_name:
                    supabase.table("kategoria").insert({"nazwa": new_kat_name, "opis": new_kat_desc}).execute()
                    st.success(f"Dodano kategorię: {new_kat_name}")
                    st.rerun()
                else:
                    st.error("Podaj nazwę kategorii!")
        
        st.divider()
        # USUWANIE KATEGORII
        if kat_data:
            kat_to_del = st.selectbox("Wybierz kategorię do usunięcia", options=[x['nazwa'] for x in kat_data])
            if st.button("🗑️ Usuń kategorię"):
                try:
                    supabase.table("kategoria").delete().eq("nazwa", kat_to_del).execute()
                    st.rerun()
                except:
                    st.error("Nie można usunąć kategorii, która zawiera produkty!")

# 5. HISTORIA
with tabs[4]:
    st.subheader("Historia operacji")
    try:
        h_res = supabase.table("historia").select("*").order("id", desc=True).execute()
        if h_res.data:
            df_h = pd.DataFrame(h_res.data)
            st.dataframe(df_h[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']].style.format({'ilosc': '{:.2f}'}), use_container_width=True, hide_index=True)
        else:
            st.info("Brak historii.")
    except:
        st.info("Tabela historii jest pusta.")

# 6. ANALIZA
with tabs[5]:
    if not df_prod.empty:
        fig = px.pie(df_prod, values='Ilość', names='Kategoria', title="Podział magazynu wg kategorii")
        st.plotly_chart(fig, use_container_width=True)
