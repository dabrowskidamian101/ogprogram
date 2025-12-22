import streamlit as st
import sqlite3
import pandas as pd

# Konfiguracja połączenia z bazą
def get_connection():
    conn = sqlite3.connect('sklep.db', check_same_thread=False)
    return conn

def inicjalizuj_baze():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS kategoria (id INTEGER PRIMARY KEY AUTOINCREMENT, nazwa TEXT, opis TEXT)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produkty (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nazwa TEXT, liczba INTEGER, cena REAL, kategoria_id INTEGER,
            FOREIGN KEY (kategoria_id) REFERENCES kategoria (id)
        )
    ''')
    conn.commit()

# --- INTERFEJS STREAMLIT ---
st.set_page_config(page_title="Zarządzanie Magazynem", layout="wide")
st.title("📦 System Zarządzania Produktami")

inicjalizuj_baze()
conn = get_connection()

# Sidebar - Dodawanie danych
st.sidebar.header("Dodaj nowe dane")
opcja = st.sidebar.selectbox("Co chcesz dodać?", ["Produkt", "Kategorię"])

if opcja == "Kategorię":
    with st.sidebar.form("form_kat"):
        n_kat = st.text_input("Nazwa kategorii")
        o_kat = st.text_area("Opis")
        if st.form_submit_button("Zapisz kategorię"):
            conn.execute("INSERT INTO kategoria (nazwa, opis) VALUES (?, ?)", (n_kat, o_kat))
            conn.commit()
            st.success("Dodano kategorię!")

elif opcja == "Produkt":
    kat_df = pd.read_sql_query("SELECT id, nazwa FROM kategoria", conn)
    with st.sidebar.form("form_prod"):
        n_prod = st.text_input("Nazwa produktu")
        l_prod = st.number_input("Liczba", min_value=0)
        c_prod = st.number_input("Cena", min_value=0.0)
        wybrana_kat = st.selectbox("Kategoria", options=kat_df['nazwa'].tolist() if not kat_df.empty else [])
        
        if st.form_submit_button("Zapisz produkt"):
            k_id = kat_df[kat_df['nazwa'] == wybrana_kat]['id'].values[0]
            conn.execute("INSERT INTO produkty (nazwa, liczba, cena, kategoria_id) VALUES (?, ?, ?, ?)", 
                         (n_prod, l_prod, c_prod, int(k_id)))
            conn.commit()
            st.success("Dodano produkt!")

# Główne okno - Wyświetlanie danych
st.header("Aktualny stan magazynu")
query = '''
    SELECT p.id, p.nazwa as Produkt, p.liczba as Ilość, p.cena as Cena, k.nazwa as Kategoria
    FROM produkty p
    LEFT JOIN kategoria k ON p.kategoria_id = k.id
'''
df = pd.read_sql_query(query, conn)
st.dataframe(df, use_container_width=True)

# Prosty wykres
if not df.empty:
    st.subheader("Wartość produktów w kategoriach")
    df['Wartość'] = df['Ilość'] * df['Cena']
    st.bar_chart(df, x="Kategoria", y="Wartość")
