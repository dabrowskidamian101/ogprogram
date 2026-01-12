import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from supabase import create_client, Client

# --- POŁĄCZENIE PRZEZ SECRETS ---
try:
    URL = st.secrets["SUPABASE_URL"]
    KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(URL, KEY)
except Exception:
    st.error("Błąd: Skonfiguruj Secrets (URL i KEY) w panelu Streamlit Cloud!")
    st.stop()

# --- STYLIZACJA I FUNKCJE ---
def koloruj_niskie_stany(row):
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
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

# --- POBIERANIE DANYCH ---
def get_data():
    try:
        # Pobieramy tabele osobno, aby uniknąć błędów joinowania w SQL
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)

        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']), df_k
        
        # Łączenie danych w Pythonie
        if not df_k.empty:
            df_f = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_f = df_f.rename(columns={
                'nazwa': 'Produkt', 'liczba': 'Ilość', 'jednostka': 'Jm',
                'cena': 'Cena', 'stan_minimalny': 'Stan Min.', 'nazwa_kat': 'Kategoria'
            })
        else:
            df_f = df_p.copy()
            df_f['Kategoria'] = "Brak"

        # Formatowanie numeryczne
        for col in ['Ilość', 'Cena', 'Stan Min.']:
            df_f[col] = pd.to_numeric(df_f[col], errors='coerce').fillna(0)
            
        return df_f[['id', 'Produkt', 'Ilość', 'Jm', 'Cena', 'Stan Min.', 'Kategoria']], df_k
    except:
        return pd.DataFrame(), pd.DataFrame()

df_prod, df_kat = get_data()

# --- DASHBOARD ---
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("📦 Towary", len(df_prod))
with c2: 
    val = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość", f"{val:,.2f} zł")
with c3: st.metric("📂 Kategorie", len(df_kat))
with c4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Niskie stany", niskie)

# --- ZAKŁADKI ---
tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "✏️ Edytuj", "📜 Historia", "📊 Analiza"])

# 1. PRZEGLĄD
with tabs[0]:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        f1, f2 = st.columns([2, 1])
        with f1: szukaj = st.text_input("🔍 Szukaj produktu...")
        with f2: sortuj = st.selectbox("Sortuj wg", options=df_prod.columns.tolist(), index=1)
        
        df_v = df_prod.copy()
        if szukaj:
            df_v = df_v[df_v['Produkt'].str.contains(szukaj, case=False)]
        df_v = df_v.sort_values(by=sortuj)

        st.dataframe(df_v.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f} zł', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1), use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# 2. PRZYJĘCIE/WYDANIE
with tabs[1]:
    if not df_prod.empty:
        with st.form("form_ruch"):
            p_wyb = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            t_op = st.radio("Operacja", ["Przyjęcie (+)", "Wydanie (-)"])
            ile = st.number_input("Ilość", min_value=1.0, step=1.0, format="%.2f")
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_wyb].iloc[0]
                nowa_q = row['Ilość'] + ile if "+" in t_op else row['Ilość'] - ile
                
                if "-" in t_op and row['Ilość'] < ile:
                    st.error("Błąd: Brak wystarczającej ilości towaru!")
                else:
                    supabase.table("produkty").update({"liczba": float(nowa_q)}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "towar": p_wyb, "typ": t_op, "ilosc": float(ile), "jednostka": row['Jm']
                    }).execute()
                    st.success("Zaktualizowano stan!")
                    st.rerun()

# 3. ZAREJESTRUJ (POPRAWIONA REJESTRACJA)
with tabs[2]:
    st.subheader("Rejestracja nowego towaru")
    if df_kat.empty:
        st.warning("Najpierw dodaj kategorię w zakładce Edytuj!")
    else:
        with st.form("form_rejestracja_final"):
            c_r1, c_r2 = st.columns(2)
            with c_r1:
                n = st.text_input("Nazwa towaru")
                jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l"])
                k_wyb = st.selectbox("Kategoria", options=df_kat['nazwa'].tolist())
            with c_r2:
                c = st.number_input("Cena netto", min_value=0.0, step=1.0, format="%.2f")
                sm = st.number_input("Stan minimalny", min_value=0.0, step=1.0, format="%.2f")
                si = st.number_input("Stan początkowy", min_value=0.0, step=1.0, format="%.2f")
            
            if st.form_submit_button("✅ Zarejestruj produkt"):
                if n:
                    try:
                        # Wymuszamy typy danych przed wysyłką
                        k_id_int = int(df_kat[df_kat['nazwa'] == k_wyb]['id'].iloc[0])
                        supabase.table("produkty").insert({
                            "nazwa": str(n), "liczba": float(si), "jednostka": str(jm),
                            "cena": float(c), "stan_minimalny": float(sm), "kategoria_id": k_id_int
                        }).execute()
                        st.success("Produkt dodany!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd bazy: {e}")
                else:
                    st.error("Podaj nazwę towaru!")

# 4. EDYTUJ TOWAR / KATEGORIĘ
with tabs[3]:
    ce1, ce2 = st.columns(2)
    with ce1:
        st.subheader("➕ Dodaj kategorię")
        with st.form("f_k"):
            nk = st.text_input("Nazwa kategorii")
            if st.form_submit_button("Zapisz"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.rerun()
    with ce2:
        st.subheader("🗑️ Usuń towar")
        if not df_prod.empty:
            t_del = st.selectbox("Towar do usunięcia", options=df_prod['Produkt'].tolist())
            if st.button("Usuń bezpowrotnie"):
                id_to_del = int(df_prod[df_prod['Produkt'] == t_del]['id'].iloc[0])
                supabase.table("produkty").delete().eq("id", id_to_del).execute()
                st.rerun()

# 5. HISTORIA
with tabs[4]:
    st.subheader("Historia operacji")
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            st.dataframe(pd.DataFrame(res_h.data)[['data_operacji', 'towar', 'typ', 'ilosc', 'jednostka']], use_container_width=True, hide_index=True)
    except:
        st.info("Historia jest pusta.")

# 6. ANALIZA
with tabs[5]:
    if not df_prod.empty:
        fig = px.pie(df_prod, values='Ilość', names='Kategoria', title="Udział kategorii")
        st.plotly_chart(fig, use_container_width=True)
