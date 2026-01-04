import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px

# --- KONFIGURACJA BAZY DANYCH ---
def get_connection():
    return sqlite3.connect('magazyn.db', check_same_thread=False)

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
    conn.commit()

# --- FUNKCJE POMOCNICZE ---
def koloruj_niskie_stany(row):
    # Jeśli stan jest mniejszy lub równy minimalnemu - koloruj na czerwono
    if row['Ilość'] <= row['Stan Min.']:
        return ['background-color: rgba(255, 75, 75, 0.3)'] * len(row)
    return [''] * len(row)

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="System Magazynowy Pro", layout="wide", page_icon="📦")
inicjalizuj_baze()
conn = get_connection()

# Stylizacja CSS
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: rgba(120, 120, 120, 0.1);
        border: 1px solid rgba(120, 120, 120, 0.2);
        padding: 15px; border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📦 Zaawansowany System Magazynowy")

# Pobranie danych
df_prod = pd.read_sql_query("""
    SELECT p.id, p.nazwa as Produkt, p.liczba as Ilość, p.jednostka as Jm, 
           p.cena as Cena, p.stan_minimalny as [Stan Min.], k.nazwa as Kategoria
    FROM produkty p 
    LEFT JOIN kategoria k ON p.kategoria_id = k.id
""", conn)

# --- STATYSTYKI ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 Razem towarów", len(df_prod))
with col2:
    wartosc = (df_prod['Ilość'] * df_prod['Cena']).sum() if not df_prod.empty else 0
    st.metric("💰 Wartość netto", f"{wartosc:,.2f} zł")
with col3:
    st.metric("📂 Kategorie", len(df_prod['Kategoria'].unique()))
with col4:
    # Licznik niskich stanów na podstawie nowej kolumny stan_minimalny
    niskie = len(df_prod[df_prod['Ilość'] <= df_prod['Stan Min.']]) if not df_prod.empty else 0
    st.metric("⚠️ Do zamówienia", niskie)

# --- ZAKŁADKI ---
tab_przeglad, tab_operacje, tab_rejestracja, tab_kategorie, tab_analiza = st.tabs([
    "🔍 Przegląd Magazynu", "🔄 Przyjęcie/Wydanie", "📝 Zarejestruj nowy towar", "📁 Zarządzaj kategoriami", "📊 Analiza"
])

# ZAKŁADKA 1: PRZEGLĄD (Z PODŚWIETLANIEM)
with tab_przeglad:
    st.subheader("Stany magazynowe (Podświetlone na czerwono = poniżej minimum)")
    if not df_prod.empty:
        # Aplikujemy stylizację kolorami
        styled_df = df_prod.style.apply(koloruj_niskie_stany, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("Magazyn jest pusty.")

# ZAKŁADKA 2: PRZYJĘCIE / WYDANIE
with tab_operacje:
    st.subheader("Szybka aktualizacja stanu (Ruch towaru)")
    if not df_prod.empty:
        with st.form("form_ruch"):
            wybrany_p = st.selectbox("Wybierz towar", options=df_prod['Produkt'].tolist())
            typ_operacji = st.radio("Typ operacji", ["Przyjęcie (+)", "Wydanie (-)"])
            ilosc_zmiana = st.number_input("Ilość", min_value=0.1, step=1.0)
            
            if st.form_submit_button("Wykonaj operację"):
                if typ_operacji == "Przyjęcie (+)":
                    conn.execute("UPDATE produkty SET liczba = liczba + ? WHERE nazwa = ?", (ilosc_zmiana, wybrany_p))
                else:
                    # Sprawdzenie czy nie wyjdziemy na minus
                    obecna_ilosc = df_prod[df_prod['Produkt'] == wybrany_p]['Ilość'].values[0]
                    if obecna_ilosc >= ilosc_zmiana:
                        conn.execute("UPDATE produkty SET liczba = liczba - ? WHERE nazwa = ?", (ilosc_zmiana, wybrany_p))
                    else:
                        st.error("Brak wystarczającej ilości towaru!")
                conn.commit()
                st.rerun()
    else:
        st.info("Najpierw zarejestruj towar.")

# ZAKŁADKA 3: REJESTRACJA NOWEGO TOWARU
with tab_rejestracja:
    st.subheader("Formularz rejestracji towaru")
    kat_list = pd.read_sql_query("SELECT * FROM kategoria", conn)
    
    if kat_list.empty:
        st.warning("Dodaj najpierw kategorię w zakładce 'Zarządzaj kategoriami'!")
    else:
        with st.form("form_rejestracja", clear_on_submit=True):
            col_a, col_b = st.columns(2)
            with col_a:
                n_nazwa = st.text_input("Nazwa towaru")
                n_jm = st.selectbox("Jednostka miary", ["szt", "kg", "m", "opak", "l"])
                n_kat = st.selectbox("Kategoria", options=kat_list['nazwa'].tolist())
            with col_b:
                n_cena = st.number_input("Cena zakupu netto", min_value=0.0, format="%.2f")
                n_min = st.number_input("Minimalny stan magazynowy", min_value=0.0)
                n_start = st.number_input("Stan początkowy", min_value=0.0)
            
            if st.form_submit_button("Zarejestruj towar w systemie"):
                k_id = kat_list[kat_list['nazwa'] == n_kat]['id'].values[0]
                conn.execute("""
                    INSERT INTO produkty (nazwa, liczba, jednostka, cena, stan_minimalny, kategoria_id) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (n_nazwa, n_start, n_jm, n_cena, n_min, int(k_id)))
                conn.commit()
                st.success(f"Towar {n_nazwa} został pomyślnie zarejestrowany.")
                st.rerun()

# ZAKŁADKA 4: KATEGORIE I USUWANIE
with tab_kategorie:
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.subheader("Dodaj kategorię")
        with st.form("form_kat_new"):
            nk = st.text_input("Nazwa")
            ok = st.text_input("Opis")
            if st.form_submit_button("Dodaj"):
                conn.execute("INSERT INTO kategoria (nazwa, opis) VALUES (?, ?)", (nk, ok))
                conn.commit()
                st.rerun()
    
    with col_k2:
        st.subheader("Usuń kategorię")
        if not kat_list.empty:
            kat_do_usuniecia = st.selectbox("Wybierz kategorię do usunięcia", options=kat_list['nazwa'].tolist())
            st.error("UWAGA: Usunięcie kategorii może wpłynąć na przypisane produkty!")
            if st.button("Usuń bezpowrotnie"):
                conn.execute("DELETE FROM kategoria WHERE nazwa = ?", (kat_do_usuniecia,))
                conn.commit()
                st.rerun()

# ZAKŁADKA 5: ANALIZA
with tab_analiza:
    if not df_prod.empty:
        fig = px.bar(df_prod, x='Produkt', y='Ilość', color='Kategoria', 
                     title="Poziom zapasów w podziale na towary", text='Jm')
        st.plotly_chart(fig, use_container_width=True)
        
        # Przycisk eksportu
        csv = df_prod.to_csv(index=False).encode('utf-8')
        st.download_button("Pobierz raport (CSV)", data=csv, file_name="magazyn.csv")

conn.close()
