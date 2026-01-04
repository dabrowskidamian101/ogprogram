import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- KONFIGURACJA BAZY DANYCH ---
def get_connection():
    return sqlite3.connect('magazyn_v3.db', check_same_thread=False)

def inicjalizuj_baze():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kategoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            opis TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produkty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            liczba REAL DEFAULT 0,
            jednostka TEXT,
            cena REAL DEFAULT 0.0,
            stan_minimalny REAL DEFAULT 0,
            kategoria_id INTEGER,
            FOREIGN KEY (kategoria_id) REFERENCES kategoria (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historia (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_operacji TEXT,
            towar TEXT,
            typ TEXT,
            ilosc REAL,
            jednostka TEXT
        )
    ''')
    conn.commit()

# --- FUNKCJE POMOCNICZE ---
def koloruj_niskie_stany(row):
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    return [''] * len(row)

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ProManager ERP", layout="wide", page_icon="📦")
inicjalizuj_baze()
conn = get_connection()

# Stylizacja CSS dla metryk (naprawione białe okienka)
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

# Pobranie danych do DF
df_prod = pd.read_sql_query("""
    SELECT p.id, p.nazwa as Produkt, p.liczba as Ilość, p.jednostka as Jm, 
           p.cena as Cena, p.stan_minimalny as [Stan Min.], k.nazwa as Kategoria
    FROM produkty p 
    LEFT JOIN kategoria k ON p.kategoria_id = k.id
""", conn)

# --- STATYSTYKI ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Razem produktów", len(df_prod))
with col2:
    wartosc = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość magazynu", f"{wartosc:,.2f} zł")
with col3:
    kat_count = len(pd.read_sql_query("SELECT id FROM kategoria", conn))
    st.metric("📂 Kategorie", kat_count)
with col4:
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Niskie stany", niskie)

# --- ZAKŁADKI ---
tab_przeglad, tab_operacje, tab_rejestracja, tab_edycja, tab_historia, tab_analiza = st.tabs([
    "🔍 Przegląd", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj nowy towar", "✏️ Edytuj Towar/Kategorię", "📜 Historia", "📊 Analiza"
])

# ZAKŁADKA 1: PRZEGLĄD
with tab_przeglad:
    st.subheader("Stany magazynowe")
    if not df_prod.empty:
        # Formatowanie do 2 miejsc po przecinku w widoku
        df_display = df_prod.copy()
        styled_df = df_display.style.format({
            'Ilość': '{:.2f}', 'Cena': '{:.2f} zł', 'Stan Min.': '{:.2f}'
        }).apply(koloruj_niskie_stany, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("Baza jest pusta.")

# ZAKŁADKA 2: PRZYJĘCIE / WYDANIE
with tab_operacje:
    st.subheader("Ruch towaru")
    if not df_prod.empty:
        with st.form("form_ruch"):
            wybrany_p = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            typ_op = st.radio("Typ operacji", ["Przyjęcie", "Wydanie"])
            ile = st.number_input("Ilość", min_value=0.01, step=1.0, format="%.2f")
            
            if st.form_submit_button("Zatwierdź operację"):
                prod_data = df_prod[df_prod['Produkt'] == wybrany_p].iloc[0]
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if typ_op == "Przyjęcie":
                    conn.execute("UPDATE produkty SET liczba = liczba + ? WHERE nazwa = ?", (ile, wybrany_p))
                    conn.execute("INSERT INTO historia (data_operacji, towar, typ, ilosc, jednostka) VALUES (?,?,?,?,?)",
                                 (now, wybrany_p, "PRZYJĘCIE", ile, prod_data['Jm']))
                    st.success(f"Przyjęto {ile} {prod_data['Jm']}")
                else:
                    if prod_data['Ilość'] >= ile:
                        conn.execute("UPDATE produkty SET liczba = liczba - ? WHERE nazwa = ?", (ile, wybrany_p))
                        conn.execute("INSERT INTO historia (data_operacji, towar, typ, ilosc, jednostka) VALUES (?,?,?,?,?)",
                                     (now, wybrany_p, "WYDANIE", ile, prod_data['Jm']))
                        st.success(f"Wydano {ile} {prod_data['Jm']}")
                    else:
                        st.error("Niewystarczający stan magazynowy!")
                conn.commit()
                st.rerun()
    else:
        st.info("Zarejestruj najpierw produkty.")

# ZAKŁADKA 3: REJESTRACJA
with tab_rejestracja:
    st.subheader("Nowy towar")
    k_list = pd.read_sql_query("SELECT * FROM kategoria", conn)
    with st.form("form_reg"):
        c_reg1, c_reg2 = st.columns(2)
        with c_reg1:
            n_nazwa = st.text_input("Nazwa towaru")
            n_jm = st.selectbox("Jednostka", ["szt", "kg", "m", "l", "opak"])
            n_kat = st.selectbox("Kategoria", options=k_list['nazwa'].tolist() if not k_list.empty else [])
        with c_reg2:
            n_cena = st.number_input("Cena netto", min_value=0.0, format="%.2f")
            n_min = st.number_input("Stan minimalny", min_value=0.0, format="%.2f")
            n_start = st.number_input("Stan początkowy", min_value=0.0, format="%.2f")
        
        if st.form_submit_button("Zarejestruj"):
            if n_nazwa and n_kat:
                kid = k_list[k_list['nazwa'] == n_kat]['id'].values[0]
                conn.execute("INSERT INTO produkty (nazwa, liczba, jednostka, cena, stan_minimalny, kategoria_id) VALUES (?,?,?,?,?,?)",
                             (n_nazwa, n_start, n_jm, n_cena, n_min, int(kid)))
                conn.commit()
                st.success("Zarejestrowano!")
                st.rerun()

# ZAKŁADKA 4: EDYCJA TOWARU / KATEGORII
with tab_edycja:
    col_ed1, col_ed2 = st.columns(2)
    
    with col_ed1:
        st.subheader("✏️ Edytuj / Usuń Towar")
        if not df_prod.empty:
            t_do_ed = st.selectbox("Wybierz towar do zmiany", options=df_prod['Produkt'].tolist())
            t_dane = df_prod[df_prod['Produkt'] == t_do_ed].iloc[0]
            
            e_cena = st.number_input("Nowa cena", value=float(t_dane['Cena']), format="%.2f")
            e_min = st.number_input("Nowy stan min.", value=float(t_dane['Stan Min.']), format="%.2f")
            
            ce1, ce2 = st.columns(2)
            with ce1:
                if st.button("Zapisz zmiany w towarze"):
                    conn.execute("UPDATE produkty SET cena = ?, stan_minimalny = ? WHERE id = ?", (e_cena, e_min, int(t_dane['id'])))
                    conn.commit()
                    st.success("Zaktualizowano!")
                    st.rerun()
            with ce2:
                if st.button("❌ USUŃ TOWAR"):
                    conn.execute("DELETE FROM produkty WHERE id = ?", (int(t_dane['id']),))
                    conn.commit()
                    st.rerun()

    with col_ed2:
        st.subheader("📂 Zarządzaj Kategoriami")
        new_k = st.text_input("Nazwa nowej kategorii")
        if st.button("Dodaj kategorię"):
            if new_k:
                conn.execute("INSERT INTO kategoria (nazwa) VALUES (?)", (new_k,))
                conn.commit()
                st.rerun()
        
        st.divider()
        if not k_list.empty:
            k_del = st.selectbox("Usuń kategorię", options=k_list['nazwa'].tolist())
            if st.button("Usuń kategorię"):
                conn.execute("DELETE FROM kategoria WHERE nazwa = ?", (k_del,))
                conn.commit()
                st.rerun()

# ZAKŁADKA 5: HISTORIA
with tab_historia:
    st.subheader("Historia przyjęć i wydań")
    df_hist = pd.read_sql_query("SELECT data_operacji as Data, towar as Towar, typ as Typ, ilosc as Ilość, jednostka as Jm FROM historia ORDER BY id DESC", conn)
    if not df_hist.empty:
        st.dataframe(df_hist.style.format({'Ilość': '{:.2f}'}), use_container_width=True, hide_index=True)
    else:
        st.info("Brak historii operacji.")

# ZAKŁADKA 6: ANALIZA
with tab_analiza:
    if not df_prod.empty:
        fig = px.pie(df_prod, values='Ilość', names='Kategoria', title="Udział kategorii w magazynie")
        st.plotly_chart(fig, use_container_width=True)
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button("Pobierz CSV", data=csv, file_name="eksport.csv")

conn.close()
