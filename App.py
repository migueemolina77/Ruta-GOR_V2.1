import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import requests
import math
import os

# --- CONFIG ---
st.set_page_config(page_title="LOGÍSTICA RUBIALES V2.1", layout="wide", page_icon="🦎")

# --- ESTILO ---
st.markdown("""
<style>
.stApp { background-color: #0e1117; }
h1 { color: #ffffff; font-weight: 800; }

.tramo-card {
    margin-bottom: 12px; padding: 15px; background: #161b22; 
    border-radius: 10px; border-left: 6px solid; border: 1px solid #30363d;
}
.tramo-header { color: #8b949e; font-size: 0.75rem; font-weight: bold; }
.tramo-nombres { color: #ffffff; font-size: 1rem; font-weight: 600; }
.tramo-distancia { font-size: 1.3rem; font-weight: 800; }

.alerta-box {
    padding: 10px; border-radius: 8px; font-size: 0.8rem;
    margin-top: 10px; font-weight: bold;
}
.alerta-despine { background: rgba(255,75,75,0.2); color: #ff4b4b; }
.alerta-comunidad { background: rgba(255,184,0,0.2); color: #ffb800; }
</style>
""", unsafe_allow_html=True)

# --- COMUNIDADES ---
COMUNIDADES = {
    "EL OASIS": {"lat": 3.965, "lon": -71.895},
    "RUBIALITOS": {"lat": 3.910, "lon": -72.030}
}

# --- FUNCIONES ---

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dlambda = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def proyectadas_a_latlon_colombia(este, norte):
    try:
        a, f = 6378137.0, 1 / 298.257222101
        b = a * (1 - f)
        e2 = (a**2 - b**2) / a**2

        lat0_deg, lon0_deg, k0 = 4.0, -73.0, 0.9992
        FE, FN = 5000000.0, 2000000.0

        lat0 = math.radians(lat0_deg)
        lon0 = math.radians(lon0_deg)

        M = (norte - FN) / k0
        mu = M / (a * (1 - e2/4 - 3*e2**2/64))

        e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

        phi1 = (mu
            + (3*e1/2 - 27*e1**3/32)*math.sin(2*mu)
            + (21*e1**2/16)*math.sin(4*mu)
        )

        N1 = a / math.sqrt(1 - e2 * math.sin(phi1)**2)
        R1 = a * (1 - e2) / (1 - e2 * math.sin(phi1)**2)**1.5
        D = (este - FE) / (N1 * k0)

        lat = phi1 - (N1 * math.tan(phi1) / R1) * (D**2 / 2)
        lon = lon0 + D / math.cos(phi1)

        return math.degrees(lat), math.degrees(lon)

    except:
        return None, None


def obtener_ruta_osrm(p1, p2):
    url = f"http://router.project-osrm.org/route/v1/driving/{p1['lon']},{p1['lat']};{p2['lon']},{p2['lat']}?overview=full&geometries=geojson"
    
    try:
        r = requests.get(url, timeout=5).json()

        if r['code'] == 'Ok':
            coords = [[lat, lon] for lon, lat in r['routes'][0]['geometry']['coordinates']]
            km = r['routes'][0]['distance'] / 1000
            return coords, km

    except Exception as e:
        st.warning(f"⚠️ OSRM error: {e}")

    return [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]], 0


# --- CARGA BASE ---
@st.cache_data
def cargar_maestro():
    try:
        ruta = "COORDENADAS_GOR_V2.xlsx"
        df = pd.read_excel(ruta, engine="openpyxl")

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

    except Exception as e:
        st.error(f"Error cargando base: {e}")
        return pd.DataFrame()
