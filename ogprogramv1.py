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

# --- STYLIZACJA I FUNKCJE WIZUALNE ---
st.set_page_config(page_title="Magazyn Pro", layout="wide")

def style_row(row):
    """Funkcja kolorująca wiersze poniżej lub równe stanowi minimalnemu"""
    color = 'background-color: rgba(255, 75, 75, 0.25)' if row['Ilość'] <= row['Stan Minimalny'] else ''
    return [color] * len(row)

st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.1);
        border: 1px solid rgba(120, 120, 120, 0.2);
        padding: 15px; border-radius: 15px;
    }
    .section-header { text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- POBIERANIE DANYCH ---
def get_data():
    try:
        res_p = supabase.table("produkty").select("*").execute()
        res_k = supabase.table("kategoria").select("id, nazwa").execute()
        df_p = pd.DataFrame(res_p.data)
        df_k = pd.DataFrame(res_k.data)

        if df_p.empty:
            return pd.DataFrame(columns=['id', 'Produkt', 'Ilość', 'Stan Minimalny', 'Cena', 'Kategoria', 'kategoria_id']), df_k
        
        if not df_k.empty:
            df_f = df_p.merge(df_k, left_on='kategoria_id', right_on='id', how='left', suffixes=('', '_kat'))
            df_f = df_f.rename(columns={
                'nazwa': 'Produkt', 
                'liczba': 'Ilość', 
                'cena': 'Cena', 
                'nazwa_kat': 'Kategoria', 
                'stan_minimalny': 'Stan Minimalny'
            })
        else:
            df_f = df_p.copy()
            df_f['Kategoria'] = "Brak"
            df_f = df_f.rename(columns={'liczba': 'Ilość', 'cena': 'Cena', 'stan_minimalny': 'Stan Minimalny', 'nazwa': 'Produkt'})

        for col in ['Ilość', 'Cena', 'Stan Minimalny']:
            df_f[col] = pd.to_numeric(df_f[col], errors='coerce').fillna(0)
            
        # KOLEJNOŚĆ KOLUMM: Produkt -> Ilość -> Stan Minimalny -> Cena -> Kategoria
        return df_f[['id', 'Produkt', 'Ilość', 'Stan Minimalny', 'Cena', 'Kategoria', 'kategoria_id']], df_k
    except Exception as e:
        st.error(f"Błąd pobierania danych: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_prod, df_kat = get_data()

# --- DASHBOARD ---
st.title("🏢 Profesjonalny System Zarządzania Magazynem")

c1, c2, c3, c4 = st.columns(4)
c1.metric("📦 Towary", len(df_prod))
c2.metric("💰 Wartość", f"{(df_prod['Ilość']*df_prod['Cena']).sum():,.2f} zł" if not df_prod.empty else "0.00 zł")
c3.metric("📂 Kategorie", len(df_kat))
niskie_stany = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Minimalny']]) if not df_prod.empty else 0
c4.metric("⚠️ Niskie stany", niskie_stany)

tabs = st.tabs(["🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj", "🏷️ Dodaj kategorię", "✏️ Edytuj towar", "📜 Historia"])

# 1. PRZEGLĄD (Zmieniona kolejność kolumn i filtrowanie)
with tabs[0]:
    st.markdown("<h2 class='section-header'>🔍 Aktualny Stan Magazynowy</h2>", unsafe_allow_html=True)
    
    if not df_prod.empty:
        col_f1, col_f2 = st.columns([2, 1])
        with col_f1:
            search = st.text_input("🔍 Szukaj produktu po nazwie...")
        with col_f2:
            sort_col = st.selectbox("Sortuj według:", ["Produkt", "Ilość", "Stan Minimalny", "Cena", "Kategoria"])

        df_display = df_prod.drop(columns=['kategoria_id', 'id']).copy()
        
        # Filtrowanie
        if search:
            df_display = df_display[df_display['Produkt'].str.contains(search, case=False)]
        
        # Sortowanie
        df_display = df_display.sort_values(by=sort_col, ascending=True)
        
        # Lp. po sortowaniu i filtrowaniu
        df_display.insert(0, 'Lp.', range(1, len(df_display) + 1))
        
        st.dataframe(
            df_display.style.apply(style_row, axis=1).format({
                'Ilość': '{:.2f}', 
                'Stan Minimalny': '{:.2f}',
                'Cena': '{:.2f} zł'
            }),
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Baza jest pusta.")

# 2. RUCH TOWARU
with tabs[1]:
    if not df_prod.empty:
        with st.form("ruch_form"):
            p_name = st.selectbox("Wybierz produkt", df_prod['Produkt'].tolist())
            t_type = st.radio("Rodzaj operacji", ["Przyjęcie", "Wydanie"], horizontal=True)
            ile = st.number_input("Ilość", min_value=1, step=1)
            if st.form_submit_button("Zatwierdź"):
                row = df_prod[df_prod['Produkt'] == p_name].iloc[0]
                nowa = int(row['Ilość'] + ile if t_type == "Przyjęcie" else row['Ilość'] - ile)
                if t_type == "Wydanie" and row['Ilość'] < ile:
                    st.error("Błąd: Brak towaru na stanie!")
                else:
                    supabase.table("produkty").update({"liczba": int(nowa)}).eq("id", int(row['id'])).execute()
                    supabase.table("historia").insert({
                        "data_operacji": datetime.now().strftime("%Y-%m-%d %H:%M"), 
                        "towar": p_name, 
                        "typ": t_type.upper(), 
                        "ilosc": int(ile)
                    }).execute()
                    st.success("Operacja wykonana pomyślnie!")
                    st.rerun()

# 3. ZAREJESTRUJ NOWY TOWAR
with tabs[2]:
    if df_kat.empty:
        st.error("Najpierw dodaj kategorię!")
    else:
        with st.form("reg_form"):
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                n = st.text_input("Nazwa towaru")
                k_name = st.selectbox("Kategoria", df_kat['nazwa'].tolist())
            with col_r2:
                c = st.number_input("Cena", min_value=0, step=1)
                si = st.number_input("Stan początkowy", min_value=0, step=1)
                sm = st.number_input("Stan minimalny (alert)", min_value=0, step=1)
            
            if st.form_submit_button("Zarejestruj"):
                if n:
                    try:
                        kid = int(df_kat[df_kat['nazwa'] == k_name]['id'].iloc[0])
                        supabase.table("produkty").insert({
                            "nazwa": str(n), 
                            "liczba": int(si), 
                            "cena": int(c), 
                            "kategoria_id": kid, 
                            "stan_minimalny": int(sm)
                        }).execute()
                        st.success("Produkt dodany do bazy!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd zapisu: {e}")

# 4. DODAJ KATEGORIĘ
with tabs[3]:
    ca, cb = st.columns(2)
    with ca:
        st.subheader("➕ Nowa kategoria")
        with st.form("add_kat"):
            nk = st.text_input("Nazwa kategorii")
            if st.form_submit_button("Zapisz"):
                if nk:
                    supabase.table("kategoria").insert({"nazwa": nk}).execute()
                    st.rerun()
    with cb:
        st.subheader("🗑️ Usuń kategorię")
        if not df_kat.empty:
            kat_del = st.selectbox("Wybierz kategorię", df_kat['nazwa'].tolist())
            if st.button("Usuń kategorię"):
                id_k = int(df_kat[df_kat['nazwa'] == kat_del]['id'].iloc[0])
                if not df_prod[df_prod['kategoria_id'] == id_k].empty:
                    st.error("Nie można usunąć kategorii zawierającej produkty!")
                else:
                    supabase.table("kategoria").delete().eq("id", id_k).execute()
                    st.rerun()

# 5. EDYTUJ TOWAR
with tabs[4]:
    if not df_prod.empty:
        edit_p = st.selectbox("Wybierz produkt do edycji", df_prod['Produkt'].tolist())
        row_e = df_prod[df_prod['Produkt'] == edit_p].iloc[0]
        with st.form("edit_form"):
            en = st.text_input("Zmień nazwę", value=row_e['Produkt'])
            ec = st.number_input("Zmień cenę", value=int(row_e['Cena']), min_value=0)
            esm = st.number_input("Zmień stan minimalny", value=int(row_e['Stan Minimalny']), min_value=0)
            ekat = st.selectbox("Zmień kategorię", df_kat['nazwa'].tolist(), 
                                index=df_kat['nazwa'].tolist().index(row_e['Kategoria']) if row_e['Kategoria'] in df_kat['nazwa'].tolist() else 0)
            
            c_ed1, c_ed2 = st.columns(2)
            with c_ed1:
                if st.form_submit_button("💾 Zapisz zmiany"):
                    kid_e = int(df_kat[df_kat['nazwa'] == ekat]['id'].iloc[0])
                    supabase.table("produkty").update({
                        "nazwa": en, 
                        "cena": int(ec), 
                        "stan_minimalny": int(esm), 
                        "kategoria_id": kid_e
                    }).eq("id", int(row_e['id'])).execute()
                    st.success("Dane zostały zaktualizowane!")
                    st.rerun()
            with c_ed2:
                if st.form_submit_button("🗑️ Usuń całkowicie"):
                    supabase.table("produkty").delete().eq("id", int(row_e['id'])).execute()
                    st.rerun()

# 6. HISTORIA
with tabs[5]:
    st.markdown("<h2 class='section-header'>📜 Dziennik Operacji</h2>", unsafe_allow_html=True)
    try:
        res_h = supabase.table("historia").select("*").order("id", desc=True).execute()
        if res_h.data:
            df_h = pd.DataFrame(res_h.data)
            df_h.insert(0, 'Lp.', range(1, len(df_h) + 1))
            st.dataframe(
                df_h[['Lp.', 'data_operacji', 'towar', 'typ', 'ilosc']].rename(columns={
                    'data_operacji': 'Data', 
                    'towar': 'Produkt', 
                    'typ': 'Operacja', 
                    'ilosc': 'Ilość'
                }), 
                use_container_width=True, 
                hide_index=True
            )
    except:
        st.info("Brak zapisów w historii.")
