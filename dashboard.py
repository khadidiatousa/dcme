import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
from io import StringIO
import altair as alt
from datetime import datetime

st.set_page_config(page_title="DHIS2 Dashboard DSDM + Vaccins", layout="wide")
API_BASE = "https://senegal.dhis2.org/dhis/api"

# -------------------- LOGIN --------------------
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

if not st.session_state.auth_ok:
    st.markdown("### 🔐 Connexion à DHIS2")
    with st.form("login_form"):
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")
        if submitted:
            try:
                r = requests.get(f"{API_BASE}/me", auth=HTTPBasicAuth(username, password))
                r.raise_for_status()
                st.session_state.auth_ok = True
                st.session_state.username = username
                st.session_state.password = password
                st.success("Connexion réussie !")
                st.rerun()
            except:
                st.error("❌ Identifiants incorrects")
    st.stop()

username = st.session_state.username
password = st.session_state.password

# -------------------- RÉCUPÉRER LES DATASETS VACCINS --------------------
target_vaccins = [
    "Hepatite B ≤ 24h",
    "Hexa 1 administrer",
    "Hexa 2 administrer",
    "Hexa 3 administrer",
    "Fievre jaune administrer",
    "Rougeole Rubeole (RR)1 administrer",
    "Rougeole Rubeole (RR)2 administrer"
]

try:
    r = requests.get(f"{API_BASE}/dataSets.json?fields=id,displayName", auth=HTTPBasicAuth(username, password))
    r.raise_for_status()
    all_datasets = pd.DataFrame(r.json()['dataSets'])
    df_vaccins = all_datasets[all_datasets['displayName'].isin(target_vaccins)]
except Exception as e:
    st.error(f"Erreur lors du chargement des datasets vaccinaux : {e}")
    st.stop()

vaccin_ids = ";".join(df_vaccins['id'].tolist())

# -------------------- IDs DSDM + NOUVEAUX IDs --------------------
dsdm_ids = (
    "UmQB5h2wJGO;"
    "gFl0FNNjkY7;"
    "jN7UPIAzCA2;"
    "M90WNdPMkqo;"
    "fNFVDVn3PpU;"
    "y5w8wXfFm9J;"
    "cHfpseqWX25;"
    "Ib4KlGkSD2B;"
    "dNXggFN08Xh;"
    "IGL1zE0NY8z;"
    "LJW3MSkmTXA;"
    "UUHtLaRq5dk;"
    "TtnaxPPEDVG;"

)

all_ids = dsdm_ids
if vaccin_ids:
    all_ids += ";" + vaccin_ids

# -------------------- CHARGEMENT DES DONNÉES --------------------
current_year = datetime.now().year

csv_url = (
    f"{API_BASE}/analytics.csv?"
    f"dimension=dx:{all_ids}&"
    f"dimension=ou:Lf9Lz9VATXY&children=true&"
    f"dimension=pe:{current_year}&aggregationType=SUM&"
    f"displayProperty=NAME&outputIdScheme=NAME"
)

try:
    r = requests.get(csv_url, auth=HTTPBasicAuth(username, password))
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text)).dropna(axis=1, how='all')
except requests.exceptions.HTTPError as e:
    if r.status_code == 409:
        st.error("⚠ Conflit dans la requête DHIS2 (HTTP 409). Vérifiez vos IDs dx et la période.")
    else:
        st.error(f"Erreur HTTP: {e}")
    st.stop()
except Exception as e:
    st.error(f"Erreur lors du chargement du CSV DSDM + Vaccins : {e}")
    st.stop()

# -------------------- FILTRAGE --------------------
st.sidebar.header("Filtres DSDM + Vaccins")
filters = {}
for col in df.select_dtypes(exclude='number').columns:
    options = df[col].dropna().unique().tolist()
    selected = st.sidebar.multiselect(f"Filtrer par {col}", options, default=options)
    filters[col] = selected

df_filtered = df.copy()
for col, selected in filters.items():
    df_filtered = df_filtered[df_filtered[col].isin(selected)]

# -------------------- TOTAL PAR POSTE --------------------
numeric_cols = df_filtered.select_dtypes(include='number')
if not numeric_cols.empty and 'Organisation unit' in df_filtered.columns:
    st.markdown("### 📌 Totaux DSDM + Vaccins par Poste / Case de Santé")
    total_par_poste = df_filtered.groupby('Organisation unit')[numeric_cols.columns.tolist()].sum().reset_index()
    st.dataframe(total_par_poste)

# -------------------- TABLEAU FILTRÉ --------------------
st.markdown("## 📊 Tableau filtré DSDM + Vaccins")
st.dataframe(df_filtered)

# -------------------- TÉLÉCHARGEMENT --------------------
csv_buffer = df_filtered.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Télécharger les données filtrées en CSV",
    data=csv_buffer,
    file_name="dsdm_vaccins_filtered_data.csv",
    mime="text/csv"
)

# -------------------- GRAPHIQUES --------------------
st.markdown("## 📈 Graphiques DSDM + Vaccins par Poste / Case de Santé")
if not numeric_cols.empty:
    indicateurs = st.multiselect(
        "Sélectionner les indicateurs à visualiser",
        numeric_cols.columns.tolist(),
        default=numeric_cols.columns.tolist()
    )

    if indicateurs:
        df_melt = df_filtered.melt(
            id_vars=['Organisation unit'] if 'Organisation unit' in df_filtered.columns else [],
            value_vars=indicateurs,
            var_name='Indicateur',
            value_name='Valeur'
        )

        chart = alt.Chart(df_melt).mark_bar().encode(
            x=alt.X('Organisation unit:N', title='Poste / Case de Santé'),
            y=alt.Y('Valeur:Q', title='Valeur'),
            color='Indicateur:N',
            tooltip=['Organisation unit', 'Indicateur', 'Valeur']
        ).properties(width='container')

        st.altair_chart(chart, use_container_width=True)
