import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import requests
import math
from folium.features import DivIcon

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="LOGÍSTICA RUBIALES V7.4", layout="wide", page_icon="🦎")

st.markdown("""
<style>
.stApp { background-color: #0e1117; }
.tramo-card {
    margin-bottom: 12px;
    padding: 15px;
    background: #161b22;
    border-radius: 10px;
    border-left: 6px solid;
    border: 1px solid #30363d;
}
.tramo-header { color: #8b949e; font-size: 0.75rem; font-weight: bold; }
.tramo-nombres { color: white; font-weight: 600; }
.tramo-distancia { font-size: 1.2rem; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>🦎 MAPA GOR</h1>", unsafe_allow_html=True)
st.divider()

# --- COMUNIDADES ---
COMUNIDADES = {
    "EL OASIS": {"lat": 3.965, "lon": -71.895},
    "RUBIALITOS": {"lat": 3.910, "lon": -72.030}
}

# --- FUNCIONES ---
def obtener_ruta_osrm(p1, p2):
    url = f"http://router.project-osrm.org/route/v1/driving/{p1['lon']},{p1['lat']};{p2['lon']},{p2['lat']}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=5).json()
        coords = [[lat, lon] for lon, lat in r['routes'][0]['geometry']['coordinates']]
        km = r['routes'][0]['distance']/1000
        return coords, km
    except:
        return [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]], 0

@st.cache_data
def cargar_maestro(file):
    df = pd.read_excel(file)
    df.columns = [re.sub(r'[^a-zA-Z]', '', str(c)).upper() for c in df.columns]

    c_n = next(c for c in df.columns if 'POZO' in c or 'NAME' in c)
    c_e = next(c for c in df.columns if 'ESTE' in c)
    c_norte = next(c for c in df.columns if 'NORTE' in c)

    df = df[[c_n, c_e, c_norte]].dropna()
    df.columns = ['NAME', 'E', 'N']

    df['lat'] = df['N']
    df['lon'] = df['E']

    df['KEY'] = df['NAME'].str.replace(r'[^a-zA-Z0-9]', '', regex=True).str.upper()
    return df

# ✅ VARIABLES GLOBALES
puntos_validos = []
all_coords = []
colores = ["#00FFCC", "#FF007F", "#FFD700"]

# ✅ CARGA LOCAL
db = cargar_maestro(open("COORDENADAS_GOR_V2.xlsx", "rb"))

# ✅ COLUMNAS
col_ui, col_map = st.columns([1.1, 3])

# ---------------- UI ----------------
with col_ui:
    st.subheader("Plan de Ruta")

    entrada = st.text_area("Lista de Pozos")

    if entrada:
        nombres = [n.strip().upper() for n in re.split(r'[\n,]+', entrada) if n.strip()]

        puntos_validos = []

        for i, n in enumerate(nombres):
            key = re.sub(r'[^a-zA-Z0-9]', '', n)
            match = db[db['KEY'].str.contains(key)]

            if not match.empty:
                fila = match.iloc[0]
                puntos_validos.append({
                    'id': i+1,
                    'n': fila['NAME'],
                    'lat': fila['lat'],
                    'lon': fila['lon']
                })

        if len(puntos_validos) >= 2:

            st.divider()
            km_total = 0

            for i in range(len(puntos_validos)-1):
                p1 = puntos_validos[i]
                p2 = puntos_validos[i+1]

                geom, km = obtener_ruta_osrm(p1, p2)

                km_total += km
                all_coords.extend(geom)

                c = colores[i % len(colores)]

                st.markdown(f"""
                <div class="tramo-card" style="border-left-color:{c};">
                    <div class="tramo-header">TRAMO {i+1}</div>
                    <div class="tramo-nombres">{p1['n']} → {p2['n']}</div>
                    <div class="tramo-distancia" style="color:{c};">{km:.2f} KM</div>
                </div>
                """, unsafe_allow_html=True)

            st.metric("DISTANCIA TOTAL", f"{km_total:.2f} KM")

# ---------------- MAPA ----------------
with col_map:
    if len(puntos_validos) >= 2:

        m = folium.Map(tiles=None)

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google"
        ).add_to(m)

        # Rutas
        for i in range(len(puntos_validos)-1):
            geom, _ = obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1])
            c = colores[i % len(colores)]

            folium.PolyLine(geom, color=c, weight=5).add_to(m)

        # Pins
        for p in puntos_validos:
            folium.Marker([p['lat'], p['lon']], tooltip=p['n']).add_to(m)

        # Fit bounds
        if all_coords:
            sw = [min(p[0] for p in all_coords), min(p[1] for p in all_coords)]
            ne = [max(p[0] for p in all_coords), max(p[1] for p in all_coords)]
            m.fit_bounds([sw, ne])

        st_folium(m, height=600)
``
