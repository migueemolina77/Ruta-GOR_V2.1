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

# --- FUNCIONES ---

def proyectadas_a_latlon_colombia(este, norte):
    try:
        a, f = 6378137.0, 1 / 298.257222101
        b = a * (1 - f)
        e2 = (a**2 - b**2) / a**2

        lat0_deg, lon0_deg, k0, FE, FN = (
            (4.0, -73.0, 0.9992, 5000000.0, 2000000.0)
            if este > 4000000
            else (4.596200417, -71.077507917, 1.0, 1000000.0, 1000000.0)
        )

        lat0, lon0 = math.radians(lat0_deg), math.radians(lon0_deg)

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
        R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
        D = (este - FE) / (N1 * k0)

        lat = phi1 - (N1 * math.tan(phi1) / R1) * (D**2/2)
        lon = lon0 + D / math.cos(phi1)

        return math.degrees(lat), math.degrees(lon)

    except:
        return None, None


def obtener_ruta_osrm(p1, p2):
    url = f"http://router.project-osrm.org/route/v1/driving/{p1['lon']},{p1['lat']};{p2['lon']},{p2['lat']}?overview=full&geometries=geojson"
    
    try:
        r = requests.get(url, timeout=5).json()
        if r["code"] == "Ok":
            coords = [[lat, lon] for lon, lat in r["routes"][0]["geometry"]["coordinates"]]
            km = r["routes"][0]["distance"] / 1000
            return coords, km
    except:
        pass

    return [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]], 0


# ✅ CAMBIO CLAVE → ARCHIVO FIJO
@st.cache_data
def cargar_maestro():
    df = pd.read_excel("COORDENADAS_GOR_V2.xlsx")

    df.columns = [re.sub(r'[^a-zA-Z]', '', str(c)).upper() for c in df.columns]

    c_n = next(c for c in df.columns if any(k in c for k in ['POZO', 'NAME', 'CLUSTER']))
    c_e = next(c for c in df.columns if 'ESTE' in c)
    c_nt = next(c for c in df.columns if 'NORTE' in c)

    df = df[[c_n, c_e, c_nt]].dropna()
    df.columns = ['NAME', 'E', 'N']

    coords = df.apply(lambda r: proyectadas_a_latlon_colombia(r['E'], r['N']), axis=1)
    df['lat'] = [c[0] for c in coords]
    df['lon'] = [c[1] for c in coords]

    df['KEY'] = df['NAME'].str.replace(r'[^a-zA-Z0-9]', '', regex=True).str.upper()

    return df.dropna(subset=['lat'])


# --- UI ---
st.title("🦎 MAPA GOR")

db = cargar_maestro()

col_ui, col_map = st.columns([1.1, 3])

with col_ui:
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


with col_map:

    if len(puntos_validos) >= 2:

        rutas = []
        for i in range(len(puntos_validos)-1):
            rutas.append(obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1]))

        m = folium.Map(location=[puntos_validos[0]['lat'], puntos_validos[0]['lon']], zoom_start=12)

        # ✅ RUTAS SIMPLES (ESTABLE)
        for geom, _ in rutas:
            folium.PolyLine(geom, color="cyan", weight=5).add_to(m)

        # ✅ PINES BÁSICOS
        for p in puntos_validos:
            folium.Marker([p['lat'], p['lon']], tooltip=p['n']).add_to(m)

        st_folium(m, width="100%", height=700)
