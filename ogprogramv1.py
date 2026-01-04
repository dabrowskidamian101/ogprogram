import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- KONFIGURACJA BAZY DANYCH ---
def get_connection():
    # check_same_thread=False jest wymagane dla Streamlit
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

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="ProManager 2.0", layout="wide", page_icon="🏢")
inicjalizuj_baze()
conn = get_connection()

# --- POPRAWIONA STYLIZACJA CSS (Dostosowana do motywów) ---
st.markdown("""
    <style>
    /* Stylizacja kontenerów metryk (okienek na górze) */
    [data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.1); /* Półprzezroczyste tło */
        border: 1px solid rgba(120, 120, 120, 0.2); /* Delikatna ramka */
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
        transition: transform 0.3s ease;
    }
    
    /* Efekt po najechaniu myszką na okienko */
    [data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        background-color: rgba(120, 120, 120, 0.15);
        border-color: #ff4b4b; /* Akcent kolorystyczny Streamlit */
    }

    /* Poprawa czytelności etykiet */
    [data-testid="stMetricLabel"] p {
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏢 Profesjonalny System Zarządzania Magazynem")
st.markdown("---")

# Pobranie danych do statystyk
df_prod = pd.read_sql_query("""
    SELECT p.*, k.nazwa as kat_nazwa 
    FROM produkty p 
    LEFT JOIN kategoria k ON p.kategoria_id = k.id
""", conn)

# --- SEKCE STATYSTYK (WIDGETY) ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Razem produktów", len(df_prod))
with col2:
    wartosc = (df_prod['liczba'] * df_prod['cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość magazynu", f"{wartosc:,.2f} zł")
with col3:
    kat_count = len(pd.read_sql_query("SELECT id FROM kategoria", conn))
    st.metric("📂 Kategorie", kat_count)
with col4:
    niskie_stany = len(df_prod[df_prod['liczba'] < 5]) if not df_prod.empty else 0
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
    
    # Wyświetlanie tabeli
    st.dataframe(
        filtered_df[['id', 'nazwa', 'liczba', 'cena', 'kat_nazwa']].rename(
            columns={'nazwa': 'Produkt', 'liczba': 'Ilość', 'cena': 'Cena (zł)', 'kat_nazwa': 'Kategoria'}
        ), 
        use_container_width=True,
        hide_index=True
    )

# ZAKŁADKA 2: DODAWANIE
with tab_dodaj:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Nowy Produkt")
        with st.form("form_produkt", clear_on_submit=True):
            nazwa = st.text_input("Nazwa produktu")
            liczba = st.number_input("Ilość", min_value=0, step=1)
            cena = st.number_input("Cena (zł)", min_value=0.0, format="%.2f")
            
            kat_list = pd.read_sql_query("SELECT * FROM kategoria", conn)
            opcje_kat = kat_list['nazwa'].tolist() if not kat_list.empty else []
            wybrana_kat = st.selectbox("Wybierz kategorię", options=opcje_kat)
            
            if st.form_submit_button("✅ Dodaj Produkt"):
                if nazwa and wybrana_kat:
                    k_id = kat_list[kat_list['nazwa'] == wybrana_kat]['id'].values[0]
                    conn.execute("INSERT INTO produkty (nazwa, liczba, cena, kategoria_id) VALUES (?, ?, ?, ?)", 
                                 (nazwa, liczba, cena, int(k_id)))
                    conn.commit()
                    st.success(f"Dodano produkt: {nazwa}")
                    st.rerun()
                else:
                    st.error("Wypełnij wszystkie pola!")

    with c2:
        st.subheader("Nowa Kategoria")
        with st.form("form_kat", clear_on_submit=True):
            n_kat = st.text_input("Nazwa kategorii")
            o_kat = st.text_area("Opis (opcjonalnie)")
            if st.form_submit_button("📁 Utwórz Kategorię"):
                if n_kat:
                    conn.execute("INSERT INTO kategoria (nazwa, opis) VALUES (?, ?)", (n_kat, o_kat))
                    conn.commit()
                    st.success(f"Utworzono kategorię: {n_kat}")
                    st.rerun()
                else:
                    st.error("Podaj nazwę kategorii!")

# ZAKŁADKA 3: EDYCJA I USUWANIE
with tab_edytuj:
    st.subheader("Modyfikacja istniejących danych")
    if not df_prod.empty:
        edit_id = st.selectbox("Wybierz ID produktu do zmiany", options=df_prod['id'].tolist())
        wybrany_prod = df_prod[df_prod['id'] == edit_id].iloc[0]
        
        col_e1, col_e2 = st.columns(2)
        with col_e1:
            st.write(f"**Wybrany:** {wybrany_prod['nazwa']}")
            nowa_cena = st.number_input("Zmień cenę", value=float(wybrany_prod['cena']), min_value=0.0)
            nowa_ilosc = st.number_input("Zmień ilość", value=int(wybrany_prod['liczba']), min_value=0)
            
            if st.button("💾 Zapisz zmiany"):
                conn.execute("UPDATE produkty SET cena = ?, liczba = ? WHERE id = ?", (nowa_cena, nowa_ilosc, edit_id))
                conn.commit()
                st.success("Zaktualizowano dane!")
                st.rerun()
        
        with col_e2:
            st.write("**Niebezpieczna strefa**")
            if st.button("🗑️ Usuń ten produkt na stałe"):
                conn.execute("DELETE FROM produkty WHERE id = ?", (edit_id,))
                conn.commit()
                st.warning(f"Produkt o ID {edit_id} został usunięty.")
                st.rerun()
    else:
        st.info("Brak produktów w bazie.")

# ZAKŁADKA 4: ANALIZA
with tab_analiza:
    st.subheader("Wizualizacja i eksport")
    if not df_prod.empty:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            fig1 = px.pie(df_prod, names='kat_nazwa', values='liczba', 
                         title="Udział ilościowy kategorii",
                         hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_chart2:
            df_prod['Wartość Total'] = df_prod['liczba'] * df_prod['cena']
            fig2 = px.bar(df_prod, x='nazwa', y='Wartość Total', 
                         title="Wartość finansowa poszczególnych produktów",
                         labels={'nazwa': 'Produkt', 'Wartość Total': 'Suma (zł)'},
                         color='kat_nazwa')
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()
        # Eksport danych
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Pobierz pełny raport magazynowy (CSV)",
            data=csv,
            file_name="raport_magazyn.csv",
            mime="text/csv",
        )
    else:
        st.info("Dodaj produkty, aby zobaczyć analizę.")

# Zamknięcie połączenia na końcu
conn.close()
