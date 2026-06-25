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


from pyproj import Transformer

transformer = Transformer.from_crs("EPSG:21897", "EPSG:4326", always_xy=True)


def proyectadas_a_latlon_colombia(este, norte):
    try:
        a, f = 6378137.0, 1 / 298.257222101
        b = a * (1 - f)
        e2 = (a**2 - b**2) / a**2

        # 🔥 DETECCIÓN INTELIGENTE (la clave de tu éxito)
        if este > 4000000:
            lat0_deg, lon0_deg, k0, FE, FN = 4.0, -73.0, 0.9992, 5000000.0, 2000000.0
        else:
            lat0_deg, lon0_deg, k0, FE, FN = 4.596200417, -71.077507917, 1.0, 1000000.0, 1000000.0

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
        r = requests.get(url, timeout=5)

        if r.status_code == 200:
            data = r.json()

            if data.get("code") == "Ok":
                coords = [[lat, lon] for lon, lat in data["routes"][0]["geometry"]["coordinates"]]
                km = data["routes"][0]["distance"] / 1000
                return coords, km

    except Exception as e:
        st.warning(f"⚠️ Error OSRM: {e}")

    return [[p1['lat'], p1['lon']], [p2['lat'], p2['lon']]], 0


# --- CARGA BASE ---
@st.cache_data
def cargar_maestro():

    ruta = "COORDENADAS_GOR_V2.xlsx"

    if not os.path.exists(ruta):
        st.error(f"No se encuentra el archivo: {ruta}")
        return pd.DataFrame()

    try:
        df = pd.read_excel(ruta, engine="openpyxl")

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

        return df.dropna(subset=['lat'])

    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return pd.DataFrame()


# --- UI ---
st.markdown("<h1 style='text-align:center;'>🦎 MAPA GOR V2.1</h1>", unsafe_allow_html=True)
st.divider()

db = cargar_maestro()

if db.empty:
    st.stop()

col_ui, col_map = st.columns([1.2, 3])

with col_ui:
    st.subheader("Plan de Ruta")

    entrada = st.text_area("Pozos:", height=180, placeholder="CASE-391\nRB-151")

    nombres = [n.strip().upper() for n in re.split(r'[\n,]+', entrada) if n.strip()]

    puntos_validos = []

    for i, n in enumerate(nombres):
        key = re.sub(r'[^a-zA-Z0-9]', '', n)

        match = db[db['KEY'] == key]
        if match.empty:
            match = db[db['KEY'].str.contains(key, case=False, na=False)]

        if not match.empty:
            fila = match.iloc[0]
            puntos_validos.append({
                'id': i+1,
                'n': fila['NAME'],
                'lat': fila['lat'],
                'lon': fila['lon']
            })

    if len(puntos_validos) >= 2:

        rutas_cache = []
        km_total = 0

        for i in range(len(puntos_validos)-1):
            geom, km = obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1])
            rutas_cache.append((geom, km))
            km_total += km

        for i in range(len(puntos_validos)-1):
            p1 = puntos_validos[i]
            p2 = puntos_validos[i+1]
            geom, km = rutas_cache[i]

            alerta_html = ""

            for com, coord in COMUNIDADES.items():
                if any(haversine(g[0], g[1], coord['lat'], coord['lon']) < 5 for g in geom[::10]):
                    alerta_html += f"<div class='alerta-box alerta-comunidad'>⚠️ {com}</div>"

            if km > 30:
                alerta_html += "<div class='alerta-box alerta-despine'>🚛 Despine requerido</div>"

            st.markdown(f"""
            <div class="tramo-card">
                <div class="tramo-header">TRAMO {i+1}</div>
                <div class="tramo-nombres">{p1['n']} ➔ {p2['n']}</div>
                <div class="tramo-distancia">{km:.2f} KM</div>
                {alerta_html}
            </div>
            """, unsafe_allow_html=True)

        st.metric("DISTANCIA TOTAL", f"{km_total:.2f} km")

with col_map:

    if len(puntos_validos) >= 2:

        m = folium.Map(location=[puntos_validos[0]['lat'], puntos_validos[0]['lon']], zoom_start=11)

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr='Google'
        ).add_to(m)

        for geom, _ in rutas_cache:
            folium.PolyLine(geom, color="cyan", weight=4).add_to(m)

        
rom folium.features import DivIcon

colores = ["#00FFCC", "#FF007F", "#FFD700", "#00BFFF", "#7CFC00"]

for p in puntos_validos:

    color = colores[(p['id']-1) % len(colores)]

    html = f"""
    <div style="text-align:center; font-family:Segoe UI;">
        
        <!-- CÍRCULO NUMERADO -->
        <div style="
            background:{color};
            color:black;
            border-radius:50%;
            width:24px;
            height:24px;
            line-height:24px;
            font-size:10pt;
            font-weight:bold;
            border:2px solid white;
            margin:auto;
        ">
            {p['id']}
        </div>

        <!-- ETIQUETA DEL POZO -->
        <div style="
            background:rgba(14,17,23,0.9);
            color:white;
            padding:4px 8px;
            border-radius:6px;
            font-size:9pt;
            margin-top:4px;
            border:1px solid {color};
            white-space:nowrap;
        ">
            ⛽ {p['n']}
        </div>

    </div>
    """

    folium.Marker(
        [p['lat'], p['lon']],
        icon=DivIcon(html=html)
    ).add_to(m)


        
