import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import requests
import math
from folium.features import DivIcon

# --- CONFIG ---
st.set_page_config(page_title="MAPA GOR", layout="wide", page_icon="🦎")

# --- ESTILO ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES ---

def proyectadas_a_latlon_colombia(este, norte):
    try:
        a, f = 6378137.0, 1 / 298.257222101
        b = a * (1 - f)
        e2 = (a**2 - b**2) / a**2

        # ✅ SISTEMA HÍBRIDO (EL QUE SÍ FUNCIONA)
        if este > 4000000:
            lat0_deg, lon0_deg, k0, FE, FN = 4.0, -73.0, 0.9992, 5000000.0, 2000000.0
        else:
            lat0_deg, lon0_deg, k0, FE, FN = 4.596200417, -71.077507917, 1.0, 1000000.0, 1000000.0

        lat0 = math.radians(lat0_deg)
        lon0 = math.radians(lon0_deg)

        M0 = a * (
            (1 - e2/4 - 3*e2**2/64)*lat0
            - (3*e2/8 + 3*e2**2/32)*math.sin(2*lat0)
            + (15*e2**2/256)*math.sin(4*lat0)
        )

        M = M0 + (norte - FN) / k0
        mu = M / (a * (1 - e2/4 - 3*e2**2/64))

        e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

        phi1 = (
            mu
            + (3*e1/2 - 27*e1**3/32)*math.sin(2*mu)
            + (21*e1**2/16 - 55*e1**4/32)*math.sin(4*mu)
        )

        N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
        D = (este - FE) / (N1 * k0)

        lat = phi1 - (N1 * math.tan(phi1)) * (D**2 / 2)
        lon = lon0 + D / math.cos(phi1)

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

    except Exception as e:
        st.warning(f"Error OSRM: {e}")

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
    for i in range(len(puntos_validos)-1):
        rutas_cache.append(obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1]))

    m = folium.Map(
        location=[puntos_validos[0]['lat'], puntos_validos[0]['lon']],
        zoom_start=12,
        tiles=None
    )

    # ✅ TILE SATELITAL ESTABLE
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Satellite"
    ).add_to(m)

    colores = ["#00FFCC", "#FF007F", "#FFD700", "#00BFFF"]

    # ✅ RUTAS
    for i, (geom, _) in enumerate(rutas_cache):
        folium.PolyLine(
            geom,
            color=colores[i % len(colores)],
            weight=5
        ).add_to(m)

    # ✅ PINES PRO
    for p in puntos_validos:

        color = colores[(p['id']-1) % len(colores)]

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
