import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- KONFIGURACJA BAZY DANYCH ---
def get_connection():
    conn = sqlite3.connect('sklep.db', check_same_thread=False)
    return conn

def inicjalizuj_baze():
    conn = get_connection()
    cursor = conn.cursor()
    # Tabela Kategoria
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kategoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            opis TEXT
        )
    ''')
    # Tabela Produkty
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produkty (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nazwa TEXT NOT NULL,
            liczba INTEGER DEFAULT 0,
            cena REAL DEFAULT 0.0,
            kategoria_id INTEGER,
            FOREIGN KEY (kategoria_id) REFERENCES kategoria (id)
        )
    ''')
    conn.commit()

# --- INTERFEJS UŻYTKOWNIKA ---
st.set_page_config(page_title="System Magazynowy Pro", layout="wide", page_icon="🏢")
inicjalizuj_baze()
conn = get_connection()

# Stylizacja CSS dla lepszego wyglądu
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_html=True)

st.title("🏢 Profesjonalny System Zarządzania Magazynem")
st.markdown("---")

# --- SEKCE STATYSTYK (WIDGETY) ---
df_prod = pd.read_sql_query("SELECT p.*, k.nazwa as kat_nazwa FROM produkty p LEFT JOIN kategoria k ON p.kategoria_id = k.id", conn)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Razem produktów", len(df_prod))
with col2:
    wartosc = (df_prod['liczba'] * df_prod['cena']).sum()
    st.metric("💰 Wartość magazynu", f"{wartosc:,.2f} zł")
with col3:
    st.metric("📂 Kategorie", len(df_prod['kat_nazwa'].unique()))
with col4:
    niskie_stany = len(df_prod[df_prod['liczba'] < 5])
    st.metric("⚠️ Niskie stany (<5)", niskie_stany)

# --- ZAKŁADKI (TABS) ---
tab_lista, tab_dodaj, tab_edytuj, tab_analiza = st.tabs([
    "🔍 Przegląd Magazynu", "➕ Dodaj Nowe", "✏️ Edycja i Usuwanie", "📊 Analiza i Raporty"
])

# ZAKŁADKA 1: LISTA I WYSZUKIWANIE
with tab_lista:
    st.subheader("Aktualne stany magazynowe")
    search_query = st.text_input("Wyszukaj produkt po nazwie...", "")
    
    filtered_df = df_prod.copy()
    if search_query:
        filtered_df = df_prod[df_prod['nazwa'].str.contains(search_query, case=False)]
    
    st.dataframe(filtered_df[['id', 'nazwa', 'liczba', 'cena', 'kat_nazwa']], use_container_width=True)

# ZAKŁADKA 2: DODAWANIE
with tab_dodaj:
    c1, c2 = st.columns(2)
    with c1:
        st.info("Dodaj nowy produkt")
        with st.form("form_produkt"):
            nazwa = st.text_input("Nazwa produktu")
            liczba = st.number_input("Ilość", min_value=0)
            cena = st.number_input("Cena (zł)", min_value=0.0)
            
            kat_list = pd.read_sql_query("SELECT * FROM kategoria", conn)
            wybrana_kat = st.selectbox("Kategoria", options=kat_list['nazwa'].tolist() if not kat_list.empty else ["Brak kategorii"])
            
            if st.form_submit_button("✅ Dodaj Produkt"):
                k_id = kat_list[kat_list['nazwa'] == wybrana_kat]['id'].values[0]
                conn.execute("INSERT INTO produkty (nazwa, liczba, cena, kategoria_id) VALUES (?, ?, ?, ?)", 
                             (nazwa, liczba, cena, int(k_id)))
                conn.commit()
                st.success("Produkt dodany!")
                st.rerun()

    with c2:
        st.info("Dodaj nową kategorię")
        with st.form("form_kat"):
            n_kat = st.text_input("Nazwa kategorii")
            o_kat = st.text_area("Opis kategorii")
            if st.form_submit_button("📁 Utwórz Kategorię"):
                conn.execute("INSERT INTO kategoria (nazwa, opis) VALUES (?, ?)", (n_kat, o_kat))
                conn.commit()
                st.success("Kategoria utworzona!")
                st.rerun()

# ZAKŁADKA 3: EDYCJA I USUWANIE
with tab_edytuj:
    st.warning("Strefa modyfikacji danych")
    edit_id = st.number_input("Podaj ID produktu do modyfikacji/usunięcia", min_value=1, step=1)
    
    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("🗑️ Usuń wybrany produkt", use_container_width=True):
            conn.execute(f"DELETE FROM produkty WHERE id = {edit_id}")
            conn.commit()
            st.error(f"Usunięto produkt o ID {edit_id}")
            st.rerun()
    
    with col_e2:
        nowa_cena = st.number_input("Nowa cena dla tego ID", min_value=0.0)
        if st.button("💾 Aktualizuj cenę", use_container_width=True):
            conn.execute("UPDATE produkty SET cena = ? WHERE id = ?", (nowa_cena, edit_id))
            conn.commit()
            st.success("Cena zaktualizowana!")
            st.rerun()

# ZAKŁADKA 4: ANALIZA
with tab_analiza:
    st.subheader("Wizualizacje i raporty")
    if not df_prod.empty:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig1 = px.pie(df_prod, names='kat_nazwa', values='liczba', title="Rozkład ilościowy kategorii")
            st.plotly_chart(fig1)
            
        with col_chart2:
            df_prod['Suma'] = df_prod['liczba'] * df_prod['cena']
            fig2 = px.bar(df_prod, x='nazwa', y='Suma', title="Wartość finansowa produktów", color='kat_nazwa')
            st.plotly_chart(fig2)

        # Eksport danych
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Pobierz pełny raport CSV", data=csv, file_name="raport_magazynowy.csv", mime="text/csv")
