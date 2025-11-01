# app.py
# Diario App - Streamlit mobile-first (Italiano)
# Modalità:
# - READ_ONLY: legge il Google Sheet pubblico via CSV (funziona se "Chiunque abbia il link" è Editor)
# - FULL_RW: lettura+scrittura usando service account (gspread)
#
# Requisiti:
# pip install streamlit pandas plotly gspread google-auth openpyxl xlsxwriter

import streamlit as st
import pandas as pd
import io, os, datetime
import plotly.express as px

# optional imports for google write access
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GS_AVAILABLE = True
except Exception:
    GS_AVAILABLE = False

st.set_page_config(page_title="Diario App", layout="centered", initial_sidebar_state="collapsed")

# ------------------ CONFIG ------------------
# Inserisci qui l'ID del Google Sheet (tra /d/ e /edit)
SHEET_ID = "1VhXmXBx6R-ulSaBNPgHmWTsCp2AHZiKYIMF3IoEyli4"

# URL CSV pubblicabile (read-only)
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

# Modalità di default: 'READ_ONLY' o 'FULL_RW'
MODE = 'READ_ONLY'  # default start: puoi passare a FULL_RW se configuri service-account

# ------------------ HELPERS ------------------
@st.cache_data(ttl=60)
def read_sheet_csv(csv_url):
    try:
        df = pd.read_csv(csv_url)
        return df
    except Exception as e:
        st.error("Errore nel leggere il foglio via CSV: " + str(e))
        return pd.DataFrame()

def safe_score_from_state(s):
    if pd.isna(s) or s=="":
        return None
    s = str(s).strip()
    if s == "✅": return 10
    if s == "⚠️": return 5
    if s == "❌": return 0
    return None

# ------------------ AUTH (opzionale) ------------------
def get_gspread_service(json_path):
    # restituisce client gspread autenticato se GS_AVAILABLE True
    if not GS_AVAILABLE:
        raise RuntimeError("gspread non installato o import fallito.")
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(json_path, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# ------------------ UI SIDEBAR ------------------
st.sidebar.markdown("**Diario App — Impostazioni**")
mode_select = st.sidebar.radio("Modalità operativa", options=["READ_ONLY", "FULL_RW"], index=0 if MODE=='READ_ONLY' else 1)
points_complete = st.sidebar.number_input("Punti per ✅", min_value=1, max_value=100, value=10)
points_partial  = st.sidebar.number_input("Punti per ⚠️", min_value=0, max_value=100, value=5)
points_missed   = st.sidebar.number_input("Punti per ❌", min_value=0, max_value=100, value=0)
st.sidebar.markdown("---")
st.sidebar.caption("Diario App — mobile-first. Apri in Safari e 'Aggiungi alla schermata Home' per esperienza app-like.")

# ------------------ LOAD DATA ------------------
mode = mode_select
if mode == "READ_ONLY":
    df_raw = read_sheet_csv(SHEET_CSV_URL)
else:
    # FULL_RW: user can upload service account JSON in sidebar or set STREAMLIT secrets
    st.sidebar.markdown("Modalità FULL_RW: carica il file JSON della Service Account o aggiungilo come secret 'GSA_JSON' su Streamlit Cloud.")
    gsa_file = st.sidebar.file_uploader("Carica service-account.json", type=['json'])
    if gsa_file is not None:
        # salva temporaneamente
        with open("service_account.json", "wb") as f:
            f.write(gsa_file.getbuffer())
        json_path = "service_account.json"
        try:
            client = get_gspread_service(json_path)
            sh = client.open_by_key(SHEET_ID)
            # legge il primo sheet come dataframe
            ws = sh.sheet1
            data = ws.get_all_records()
            df_raw = pd.DataFrame(data)
        except Exception as e:
            st.error("Errore autenticazione Google: " + str(e))
            df_raw = pd.DataFrame()
    else:
        st.info("Carica il JSON per abilitare scrittura. In alternativa puoi usare la modalità READ_ONLY.")
        df_raw = pd.DataFrame()

# ------------------ DATA NORMALIZATION ------------------
# Tentativi per normalizzare colonne standard del tuo template:
expected_cols = ["Data","Giorno","Ora","Attività","Materia","Tipo","Stato","Punteggio","Note"]
# If df_raw has different header names (es. italian variations), try to map common names
col_map = {}
for c in df_raw.columns if not df_raw.empty else []:
    lc = c.strip().lower()
    if "data" in lc: col_map[c] = "Data"
    elif "gior" in lc: col_map[c] = "Giorno"
    elif "ora" in lc: col_map[c] = "Ora"
    elif "attiv" in lc: col_map[c] = "Attività"
    elif "mater" in lc: col_map[c] = "Materia"
    elif "tipo" in lc: col_map[c] = "Tipo"
    elif "stat" in lc: col_map[c] = "Stato"
    elif "punt" in lc: col_map[c] = "Punteggio"
    elif "note" in lc: col_map[c] = "Note"
if col_map:
    df_raw = df_raw.rename(columns=col_map)

# Guarantee expected columns exist
for c in expected_cols:
    if c not in df_raw.columns:
        df_raw[c] = ""

# Compute punt. calcolato
df = df_raw.copy()
df["Punteggio_calcolato"] = df["Stato"].apply(lambda s: points_complete if str(s).strip()=="✅" else (points_partial if str(s).strip()=="⚠️" else (points_missed if str(s).strip()=="❌" else 0)))

# ------------------ LAYOUT MOBILE ------------------
st.markdown("<h1 style='text-align:center'>📔 Diario App</h1>", unsafe_allow_html=True)
st.markdown(f"**Visuale mobile per iPhone** — Foglio: _Diario Scuola_ (ID `{SHEET_ID}`)")

# Top summary
today = datetime.date.today()
st.markdown(f"**Oggi:** {today.strftime('%A %d %B %Y')}")
total_points = df["Punteggio_calcolato"].sum()
cols = st.columns(3)
cols[0].metric("Punti totali", int(total_points))
cols[1].metric("Ore segnate", int((df["Punteggio_calcolato"]>0).sum()))
cols[2].metric("Modalità", mode)

st.markdown("---")

# Pagina: Oggi -> mostra righe relative alla data odierna (se la colonna Data è data)
# Pagina: Oggi -> mostra righe relative alla data odierna (se la colonna Data è data)
try:
    df["Data_parsed"] = pd.to_datetime(df["Data"]).dt.date
except Exception:
    df["Data_parsed"] = df["Data"]

oggi_df = df[df["Data_parsed"] == today]
if oggi_df.empty:
    st.info("Nessuna riga per oggi trovata nel foglio. Puoi comunque esplorare il planner generale qui sotto.")
else:
    st.markdown("## ⏱️ Oggi — ora per ora")
    # Elenco compatto verticale stile card
    for i, row in oggi_df.reset_index().iterrows():
        with st.container():
            st.markdown(f"**{row['Ora']} — {row['Attività'] or '—'}**")
            st.markdown(f"Materia: *{row['Materia']}*  •  Tipo: `{row['Tipo']}`")
            st.caption(f"Note: {row['Note']}")
            cols = st.columns([1,1,1,2])
            state = row['Stato'] if row['Stato'] else ""
            new_state = cols[0].selectbox("Stato", options=["","✅","⚠️","❌"], index=0, key=f"st_{i}")
            if cols[1].button("Salva", key=f"save_{i}"):
                # Solo modalità FULL_RW con service account salva su Google
                if mode == "FULL_RW" and GS_AVAILABLE and os.path.exists("service_account.json"):
                    try:
                        client = get_gspread_service("service_account.json")
                        sh = client.open_by_key(SHEET_ID)
                        ws = sh.sheet1
                        # find row index in sheet via searching for Data+Ora matching (simple heuristic)
                        all_values = ws.get_all_records()
                        for r_idx, rec in enumerate(all_values, start=2):
                            if str(rec.get('Data','')) == str(row['Data']) and str(rec.get('Ora','')) == str(row['Ora']):
                                ws.update_cell(r_idx, list(df.columns).index("Stato")+1, new_state)
                                st.success("✅ Stato aggiornato su Google Sheet")
                                break
                        else:
                            st.warning("Non ho trovato la riga corrispondente per aggiornare.")
                    except Exception as e:
                        st.error("Errore scrittura Google: " + str(e))
                else:
                    st.warning("Per salvare su Google Sheet attiva FULL_RW e carica il JSON service account nella sidebar.")
            cols[2].markdown(f"**Punteggio:** {row['Punteggio_calcolato'] or 0}")
# Missioni: ricava da sheet le eventuali missioni (se esiste una tabella 'Missioni')
# For simplicity: cerca foglio missioni via CSV non è semplice; qui visualizziamo una sezione sintetica.
st.markdown("## 🎯 Missioni (sintesi)")
# If the sheet contains columns 'Tipo Missione' and 'Descrizione' show them
possible_mission_cols = [c for c in df_raw.columns if 'mission' in c.lower() or 'descr' in c.lower()]
if len(possible_mission_cols) >= 1:
    st.dataframe(df_raw[possible_mission_cols].head())
else:
    st.info("Missioni non trovate nel foglio. Le puoi gestire direttamente nella tab Missioni del Google Sheet.")

# Statistiche: grafico punti giornalieri
st.markdown("## 📈 Andamento punti giornalieri")
daily = df.groupby("Data_parsed")["Punteggio_calcolato"].sum().reset_index().sort_values("Data_parsed")
if not daily.empty:
    fig = px.line(daily, x="Data_parsed", y="Punteggio_calcolato", title="Punti giornalieri", markers=True)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nessun dato per grafico punti.")

# Export: scarica xlsx aggiornato (solo client-side)
st.markdown("---")
st.markdown("### ⬇️ Esporta")
to_export = st.button("Scarica snapshot Excel (.xlsx)")
if to_export:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter", datetime_format='yyyy-mm-dd') as writer:
        df_raw.to_excel(writer, sheet_name="Sheet1", index=False)
    bio.seek(0)
    st.download_button("Clicca per scaricare il file .xlsx", data=bio, file_name="DiarioApp_snapshot.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("— fine —")
