import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import requests
import math
import os
from folium.features import DivIcon

# --- CONFIG ---
st.set_page_config(page_title="MAPA GOR", layout="wide", page_icon="🦎")

# --- ESTILO ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; }

.tramo-card {
    margin-bottom: 12px;
    padding: 15px;
    background: #161b22;
    border-radius: 10px;
    border: 1px solid #30363d;
}
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---

def proyectadas_a_latlon_colombia(este, norte):
    try:
        a = 6378137.0

        if este > 4000000:
            FE, FN = 5000000.0, 2000000.0
            lon0 = math.radians(-73.0)
        else:
            FE, FN = 1000000.0, 1000000.0
            lon0 = math.radians(-71.0775)

        lat = (norte - FN) / a
        lon = lon0 + (este - FE) / a

        return math.degrees(lat), math.degrees(lon)

    except:
        return None, None


def obtener_ruta_osrm(p1, p2):
    url = f"http://router.project-osrm.org/route/v1/driving/{p1['lon']},{p1['lat']};{p2['lon']},{p2['lat']}?overview=full&geometries=geojson"

    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data.get("code") == "Ok":
                coords = [[lat, lon] for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
                km = data["routes"][0]["distance"] / 1000
                return coords, km
    except:
        pass

    return [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]], 0


@st.cache_data
def cargar_maestro():
    df = pd.read_excel("COORDENADAS_GOR_V2.xlsx")

    df.columns = [re.sub(r'[^a-zA-Z]', '', str(c)).upper() for c in df.columns]

    c_n = next(c for c in df.columns if any(k in c for k in ['POZO', 'NAME', 'CLUSTER']))
    c_e = next(c for c in df.columns if "ESTE" in c)
    c_nt = next(c for c in df.columns if "NORTE" in c)

    df = df[[c_n, c_e, c_nt]].dropna()
    df.columns = ['NAME', 'E', 'N']

    coords = df.apply(lambda r: proyectadas_a_latlon_colombia(r['E'], r['N']), axis=1)
    df['lat'] = [c[0] for c in coords]
    df['lon'] = [c[1] for c in coords]

    df['KEY'] = df['NAME'].str.replace(r'[^a-zA-Z0-9]', '', regex=True).str.upper()

    return df


# --- UI ---
st.markdown("<h1 style='text-align:center;'>🦎 MAPA GOR</h1>", unsafe_allow_html=True)

db = cargar_maestro()

entrada = st.text_area("Pozos (uno por línea)")

nombres = [n.strip().upper() for n in re.split(r'[\n,]+', entrada) if n.strip()]

puntos_validos = []

for i, n in enumerate(nombres):
    key = re.sub(r'[^a-zA-Z0-9]', '', n)
    match = db[db['KEY'].str.contains(key, case=False, na=False)]

    if not match.empty:
        fila = match.iloc[0]
        puntos_validos.append({
            'id': i+1,
            'n': fila['NAME'],
            'lat': fila['lat'],
            'lon': fila['lon']
        })

# --- MAPA ---
if len(puntos_validos) >= 2:

    rutas_cache = []
    for i in range(len(puntos_validos) - 1):
        rutas_cache.append(obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1]))

    m = folium.Map(
        location=[puntos_validos[0]['lat'], puntos_validos[0]['lon']],
        zoom_start=11,
        tiles=None   # 🔥 clave para evitar fondo negro
    )

    # ✅ TILE ESTABLE (nunca falla)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap"
    ).add_to(m)

    colores = ["#00FFCC", "#FF007F", "#FFD700", "#00BFFF"]

    # ✅ RUTAS
    for i, (geom, _) in enumerate(rutas_cache):
        folium.PolyLine(
            geom,
            color=colores[i % len(colores)],
            weight=5,
            opacity=0.9
        ).add_to(m)

    # ✅ PINES PRO
    for p in puntos_validos:

        color = colores[(p['id'] - 1) % len(colores)]

        html = f"""
        <div style="text-align:center;">
            <div style="
                background:{color};
                border-radius:50%;
                width:28px;
                height:28px;
                line-height:28px;
                font-weight:bold;
                color:black;
                border:2px solid white;">
                {p['id']}
            </div>
            <div style="
                background:black;
                color:white;
                padding:4px 8px;
                border-radius:6px;
                margin-top:4px;
                font-size:10px;">
                ⛽ {p['n']}
            </div>
        </div>
        """

        folium.Marker(
            [p['lat'], p['lon']],
            icon=DivIcon(html=html)
        ).add_to(m)

    # ✅ AUTO ZOOM
    coords_all = [coord for geom, _ in rutas_cache for coord in geom]

    if coords_all:
        sw = [min(c[0] for c in coords_all), min(c[1] for c in coords_all)]
        ne = [max(c[0] for c in coords_all), max(c[1] for c in coords_all)]
        m.fit_bounds([sw, ne])

    st_folium(m, height=700)
