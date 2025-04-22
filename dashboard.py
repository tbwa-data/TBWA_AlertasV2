import streamlit as st
from streamlit_autorefresh import st_autorefresh
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from collections import Counter
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# --- Inyecta estilos personalizados ---
st.markdown(
    """
    <style>
    .title {
        text-align: center;
        color: #002da0;
        font-size: 36px;
        font-weight: bold;
    }
    .section-header {
        font-size: 16px;
        color: #222222;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .stButton>button {
        background-color: #ff7800;
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Refresca la página cada 60 segundos
st_autorefresh(interval=60000, key="datarefresh")

# --- Conexión a Google Sheets ---
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

uploaded_file = st.file_uploader("🔐 Sube tus credenciales de Google (.json)", type="json")

if uploaded_file is None:
    st.warning("Por favor, sube tu archivo de credenciales para continuar.")
    st.stop()

try:
    import json
    credentials_dict = json.load(uploaded_file)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"Error en la autenticación con Google Sheets: {e}")
    st.stop()



try:
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"Error en la autenticación: {e}")
    st.stop()

try:
    # Cambia "alertas" y "data" por el nombre de tu Google Sheet y la hoja
    sheet = client.open("tbwa_alertas").worksheet("data")
except Exception as e:
    st.error(f"Error al abrir la hoja: {e}")
    st.stop()

try:
    # Influyentes
    sheet_influyente = client.open("ETL - Parametros").worksheet("influyentes")
except Exception as e:
    st.error(f"Error al abrir la hoja de influyentes: {e}")
    st.stop()



def get_data():
    return sheet.get_all_records()

def get_data_influyentes():
    return sheet_influyente.get_all_records()

data = get_data()
dataInfluyentes = get_data_influyentes()


# --- Procesamiento de Datos con Pandas ---
df = pd.DataFrame(data)
if "Fecha" not in df.columns:
    st.error("No se encontró la columna 'Fecha' en los datos.")
    st.stop()

dfInfluyentes = pd.DataFrame(dataInfluyentes)
if "username" not in dfInfluyentes.columns:
    st.error("No se encontró la columna 'Page' en los datos de influyentes.")
    st.stop()

df = pd.merge( df, dfInfluyentes, how='left', left_on='Page', right_on='username')
print(df.columns)
print(df.head())

print("Influentes sin coincidencias:")
df2 = df[df["username"].isna()]["Page"].drop_duplicates() 
print(df2.shape  )
print(df2.tail()) 
print("################################")

# Convertir la columna "Fecha" a datetime (ajusta el formato según tus datos)
df["Fecha_dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y %H:%M", errors="coerce")

# --- Título y Filtros ---
st.markdown("<div class='title'>Dashboard de Alertas</div>", unsafe_allow_html=True)

# Filtro de fecha (por defecto, el día de hoy)
today = datetime.today().date()
selected_date = st.date_input("Selecciona la fecha", value=today)
selected_date_dt = pd.to_datetime(selected_date)

# Filtro de Marca
def get_filter_options(df):
    marcas = sorted(set(df["Marca"].dropna().str.strip()))
    return ["TODOS"] + marcas

options = get_filter_options(df)
marca_filter = st.selectbox("Filtrar por Marca", options)

# Filtrar el DataFrame por fecha (registros del día seleccionado)
df_filtered = df[df["Fecha_dt"].dt.date == selected_date]
if marca_filter != "TODOS":
    df_filtered = df_filtered[df_filtered["Marca"].str.strip() == marca_filter]

# --- Métricas y Gráficos ---
st.metric("Total de registros", len(df_filtered))

# Gráfico Circular: Distribución por Red
st.markdown("<div class='section-header'>Distribución por Red</div>", unsafe_allow_html=True)
if "Red" in df_filtered.columns:
    custom_colors = ['#002da0', '#d2eefc', '#ece4fc', '#d2d5dc', '#002a8d', '#0a47f0']
    red_counts = df_filtered["Red"].dropna().str.strip().value_counts()
    if not red_counts.empty:
        fig_pie = px.pie(
            names=red_counts.index,
            values=red_counts.values,
            color_discrete_sequence=custom_colors
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.write("No hay datos para el gráfico circular de Red.")
else:
    st.write("Columna 'Red' no encontrada.")

# Gráfico de Barras: Distribución por Tema
st.markdown("<div class='section-header'>Distribución por Tema</div>", unsafe_allow_html=True)
if "Tema" in df_filtered.columns:
    custom_colors = ['#002da0','#002a8d', '#0a47f0']
    tema_counts = df_filtered["Tema"].dropna().str.strip().value_counts()
    if not tema_counts.empty:
        fig_bar = px.bar(
            x=tema_counts.index,
            y=tema_counts.values,
            labels={"x": "Tema", "y": "Cantidad"},
            color_discrete_sequence=custom_colors
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.write("No hay datos para el gráfico de barras de Tema.")
else:
    st.write("Columna 'Tema' no encontrada.")

# Gráfico de Barras: Avance de Alertas por Hora (Comparativo Hoy vs Ayer)
st.markdown("<div class='section-header'>Avance de Alertas por Hora</div>", unsafe_allow_html=True)

# Filtra datos para el día seleccionado y el día anterior
df_current = df[df["Fecha_dt"].dt.date == selected_date]
prev_date = selected_date - timedelta(days=1)
df_prev = df[df["Fecha_dt"].dt.date == prev_date]

def group_by_hour(dataframe):
    if dataframe.empty:
        return pd.DataFrame(columns=["Hour", "Cantidad"])
    dataframe = dataframe.copy()
    dataframe["Hour"] = dataframe["Fecha_dt"].dt.hour
    return dataframe.groupby("Hour").size().reset_index(name="Cantidad")

current_group = group_by_hour(df_current)
prev_group = group_by_hour(df_prev)

if not current_group.empty:
    current_group["Dia"] = "Hoy"
if not prev_group.empty:
    prev_group["Dia"] = "Ayer"

combined = pd.concat([current_group, prev_group], ignore_index=True)
combined = combined.sort_values("Hour")
if not combined.empty:
    fig_bar_hour = px.bar(
        combined,
        x="Hour",
        y="Cantidad",
        color="Dia",
        barmode="group"
    )
    st.plotly_chart(fig_bar_hour, use_container_width=True)
else:
    st.write("No hay datos para el gráfico de barras por hora.")

# Listado de Top Usuarios
st.markdown("<div class='section-header'>Top Usuarios</div>", unsafe_allow_html=True)

if "Usuario" in df_filtered.columns:
    top_users = df_filtered["Usuario"].dropna().str.strip().value_counts().head(20)
    
    if not top_users.empty:
        # Obtenemos el listado de usernames con contenido
        usuarios_con_username = df_filtered[df_filtered["username"].notna()]["Usuario"].str.strip().unique()

        # Asignamos color rojo si está en la lista de usuarios con username, sino azul
        colors = ["red" if user in usuarios_con_username else "skyblue" for user in top_users.index]

        # Configuramos la figura
        fig, ax = plt.subplots()
        ax.barh(top_users.index, top_users.values, color=colors)
        ax.set_xlabel('Número de Interacciones')
        ax.set_title('Top Usuarios')
        ax.invert_yaxis()  # Invertimos el eje Y para mostrar el top en la parte superior
        st.pyplot(fig)
    else:
        st.write("No hay datos para usuarios.")
else:
    st.write("Columna 'Usuario' no encontrada.")

# Listado de Top Usuarios
st.markdown("<div class='section-header'>Top Usuarios (Influyentes)</div>", unsafe_allow_html=True)

if "Usuario" in df_filtered.columns:
    # Nos quedamos solo con usuarios que tienen contenido en "username"
    influyentes = df_filtered[df_filtered["username"].notna()]["Usuario"].dropna().str.strip()

    if not influyentes.empty:
        # Contamos los más repetidos entre los influyentes
        top_users = influyentes.value_counts().head(10)

        # Configuramos la figura
        fig, ax = plt.subplots()
        ax.barh(top_users.index, top_users.values, color='red')  # rojo para influyentes
        ax.set_xlabel('Número de Interacciones')
        ax.set_title('Top Usuarios Influyentes')
        ax.invert_yaxis()
        st.pyplot(fig)
    else:
        st.write("No hay usuarios influyentes con datos hoy")
else:
    st.write("Columna 'Usuario' no encontrada.")



# Botón para refrescar manualmente los datos
if st.button("Refrescar datos"):
    st.experimental_rerun()
