import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import re
import requests
import math
import os
from folium.features import DivIcon


# ======================================================
# CONFIGURACIÓN GENERAL
# ======================================================

st.set_page_config(
    page_title="LOGÍSTICA RUBIALES V7.5",
    layout="wide",
    page_icon="🦎"
)


# ======================================================
# ESTILO GENERAL
# ======================================================

st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
    }

    h1 {
        color: #ffffff;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 800;
        letter-spacing: -1px;
    }

    .stTextArea label {
        color: white !important;
        font-weight: bold;
    }

    .stMetric label {
        color: #8b949e !important;
    }

    .stMetric div {
        color: white !important;
    }
</style>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
""", unsafe_allow_html=True)


# ======================================================
# ARCHIVO MAESTRO LOCAL
# ======================================================

ARCHIVO_COORDENADAS = "COORDENADAS_GOR_V2.xlsx"


# ======================================================
# COORDENADAS DE REFERENCIA
# ======================================================

COMUNIDADES = {
    "EL OASIS": {"lat": 3.965, "lon": -71.895},
    "RUBIALITOS": {"lat": 3.910, "lon": -72.030}
}


# ======================================================
# FUNCIONES TÉCNICAS
# ======================================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Calcula distancia aproximada entre dos coordenadas geográficas en kilómetros.
    """

    R = 6371

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )

    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def proyectadas_a_latlon_colombia(este, norte):
    """
    Convierte coordenadas proyectadas a latitud/longitud.
    Mantiene la lógica original del aplicativo funcional.
    """

    try:
        este = float(este)
        norte = float(norte)

        a = 6378137.0
        f = 1 / 298.257222101
        b = a * (1 - f)
        e2 = (a ** 2 - b ** 2) / a ** 2

        if este > 4000000:
            lat0_deg = 4.0
            lon0_deg = -73.0
            k0 = 0.9992
            FE = 5000000.0
            FN = 2000000.0
        else:
            lat0_deg = 4.596200417
            lon0_deg = -71.077507917
            k0 = 1.0
            FE = 1000000.0
            FN = 1000000.0

        lat0 = math.radians(lat0_deg)
        lon0 = math.radians(lon0_deg)

        M0 = a * (
            (1 - e2 / 4 - 3 * e2 ** 2 / 64) * lat0
            - (3 * e2 / 8 + 3 * e2 ** 2 / 32) * math.sin(2 * lat0)
            + (15 * e2 ** 2 / 256) * math.sin(4 * lat0)
        )

        M = M0 + (norte - FN) / k0
        mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64))

        e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))

        phi1 = (
            mu
            + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
        )

        N1 = a / math.sqrt(1 - e2 * math.sin(phi1) ** 2)

        R1 = (
            a * (1 - e2)
            / (1 - e2 * math.sin(phi1) ** 2) ** 1.5
        )

        D = (este - FE) / (N1 * k0)

        lat = phi1 - (N1 * math.tan(phi1) / R1) * (
            D ** 2 / 2
            - (5 + 3 * math.tan(phi1) ** 2) * D ** 4 / 24
        )

        lon = lon0 + (
            D
            - (1 + 2 * math.tan(phi1) ** 2) * D ** 3 / 6
        ) / math.cos(phi1)

        return math.degrees(lat), math.degrees(lon)

    except Exception:
        return None, None


def obtener_ruta_osrm(p1, p2):
    """
    Consulta OSRM para obtener geometría y distancia de ruta.
    Si OSRM falla, retorna línea recta entre los dos puntos.
    """

    url = (
        "http://router.project-osrm.org/route/v1/driving/"
        f"{p1['lon']},{p1['lat']};{p2['lon']},{p2['lat']}"
        "?overview=full&geometries=geojson"
    )

    try:
        respuesta = requests.get(url, timeout=8)
        data = respuesta.json()

        if data.get("code") == "Ok":
            coords = [
                [lat, lon]
                for lon, lat in data["routes"][0]["geometry"]["coordinates"]
            ]

            distancia = data["routes"][0]["distance"] / 1000

            return coords, distancia

    except Exception:
        pass

    return [[p1["lat"], p1["lon"]], [p2["lat"], p2["lon"]]], 0


@st.cache_data
def cargar_maestro(ruta_archivo):
    """
    Carga el archivo maestro de coordenadas desde archivo local.
    El archivo debe estar en la misma carpeta del App.py.
    """

    try:
        if not os.path.exists(ruta_archivo):
            return pd.DataFrame()

        if ruta_archivo.lower().endswith(".xlsx"):
            df = pd.read_excel(ruta_archivo)
        else:
            df = pd.read_csv(
                ruta_archivo,
                encoding="latin-1",
                sep=None,
                engine="python"
            )

        df.columns = [
            re.sub(r"[^a-zA-Z]", "", str(c)).upper()
            for c in df.columns
        ]

        c_n = next(
            c for c in df.columns
            if any(k in c for k in ["POZO", "NAME", "CLUSTER"])
        )

        c_e = next(c for c in df.columns if "ESTE" in c)
        c_nt = next(c for c in df.columns if "NORTE" in c)

        df_f = df[[c_n, c_e, c_nt]].copy()
        df_f = df_f.dropna()

        df_f.columns = ["NAME", "E", "N"]

        coords = df_f.apply(
            lambda r: proyectadas_a_latlon_colombia(r["E"], r["N"]),
            axis=1
        )

        df_f["lat"] = [c[0] for c in coords]
        df_f["lon"] = [c[1] for c in coords]

        df_f["KEY"] = (
            df_f["NAME"]
            .astype(str)
            .str.replace(r"[^a-zA-Z0-9]", "", regex=True)
            .str.upper()
        )

        df_f = df_f.dropna(subset=["lat", "lon"])

        return df_f

    except Exception as e:
        st.error(f"Error cargando archivo maestro: {e}")
        return pd.DataFrame()


def buscar_punto(db, nombre):
    """
    Busca un pozo o cluster dentro del maestro.
    Usa coincidencia por KEY normalizada.
    """

    key = re.sub(r"[^a-zA-Z0-9]", "", nombre).upper()

    if key == "":
        return None

    match_exacto = db[db["KEY"] == key]

    if not match_exacto.empty:
        fila = match_exacto.iloc[0]
        return fila

    match_contiene = db[
        db["KEY"].str.contains(
            key,
            case=False,
            na=False,
            regex=False
        )
    ]

    if not match_contiene.empty:
        fila = match_contiene.iloc[0]
        return fila

    return None


# ======================================================
# INTERFAZ PRINCIPAL
# ======================================================

st.markdown(
    "<h1 style='text-align: center;'>🦎 MAPA GOR - ECOPETROL</h1>",
    unsafe_allow_html=True
)

st.divider()


# ======================================================
# CARGA INTERNA DEL ARCHIVO
# ======================================================

db = cargar_maestro(ARCHIVO_COORDENADAS)

if db.empty:
    st.error(
        f"❌ No se pudo cargar el archivo maestro interno: `{ARCHIVO_COORDENADAS}`"
    )

    st.warning(
        "Verifica que el archivo esté en la misma carpeta donde está `App.py`."
    )

    st.stop()


# ======================================================
# LAYOUT
# ======================================================

col_ui, col_map = st.columns([1.1, 3])


# ======================================================
# PANEL IZQUIERDO
# ======================================================

with col_ui:

    st.subheader("Plan de Ruta")

    entrada = st.text_area(
        "Lista de Pozos:",
        placeholder="Ejemplo:\nRB-91\nRB-158\nCASE-023",
        height=150
    )

    nombres = [
        n.strip().upper()
        for n in re.split(r"[\n,]+", entrada)
        if n.strip()
    ]

    puntos_validos = []
    nombres_no_encontrados = []

    for i, nombre in enumerate(nombres):

        fila = buscar_punto(db, nombre)

        if fila is not None:
            puntos_validos.append({
                "id": len(puntos_validos) + 1,
                "buscado": nombre,
                "n": fila["NAME"],
                "lat": float(fila["lat"]),
                "lon": float(fila["lon"])
            })
        else:
            nombres_no_encontrados.append(nombre)

    if nombres_no_encontrados:
        st.warning(
            "No encontrados: "
            + ", ".join(nombres_no_encontrados)
        )

    rutas_calculadas = []
    all_coords = []
    colores = ["#00FFCC", "#FF007F", "#FFD700", "#00BFFF", "#7CFC00"]

    if len(nombres) == 0:
        st.info("Ingrese mínimo dos pozos o clusters para calcular la ruta.")

    elif len(puntos_validos) < 2:
        st.info("Ingrese mínimo dos pozos o clusters válidos para calcular la ruta.")

    else:
        st.divider()

        km_totales = 0

        for i in range(len(puntos_validos) - 1):

            p_orig = puntos_validos[i]
            p_dest = puntos_validos[i + 1]

            geom, km = obtener_ruta_osrm(p_orig, p_dest)

            c = colores[i % len(colores)]

            rutas_calculadas.append({
                "tramo": i + 1,
                "origen": p_orig,
                "destino": p_dest,
                "geom": geom,
                "km": km,
                "color": c
            })

            km_totales += km
            all_coords.extend(geom)

            alertas = []

            # --------------------------------------------------
            # ALERTA DE COMUNIDADES
            # --------------------------------------------------

            for com, coord in COMUNIDADES.items():

                cerca_orig = (
                    haversine(
                        p_orig["lat"],
                        p_orig["lon"],
                        coord["lat"],
                        coord["lon"]
                    ) < 5.0
                )

                cerca_dest = (
                    haversine(
                        p_dest["lat"],
                        p_dest["lon"],
                        coord["lat"],
                        coord["lon"]
                    ) < 5.0
                )

                cerca_ruta = any(
                    haversine(
                        g[0],
                        g[1],
                        coord["lat"],
                        coord["lon"]
                    ) < 5.0
                    for g in geom
                )

                if cerca_orig or cerca_dest or cerca_ruta:
                    alertas.append(f"⚠️ ALERTA: Tránsito por {com}")

            # --------------------------------------------------
            # ALERTA DE DESPINE
            # --------------------------------------------------

            if km > 30:
                alertas.append("🚚 DESPINAR TORRE POR DISTANCIA")

            # --------------------------------------------------
            # TARJETA NATIVA STREAMLIT
            # --------------------------------------------------

            with st.container(border=True):

                st.caption(f"TRAMO {i + 1} ➜ {i + 2}")

                st.markdown(
                    f"**{p_orig['n']} ➜ {p_dest['n']}**"
                )

                st.markdown(
                    f"""
                    <h3 style="
                        color:{c};
                        margin-top:0px;
                        margin-bottom:8px;
                    ">
                        {km:.2f} KM
                    </h3>
                    """,
                    unsafe_allow_html=True
                )

                for alerta in alertas:
                    if "DESPINAR" in alerta:
                        st.error(alerta)
                    else:
                        st.warning(alerta)

        st.metric("DISTANCIA TOTAL", f"{km_totales:.2f} KM")


# ======================================================
# MAPA DERECHO
# ======================================================

with col_map:

    if len(puntos_validos) >= 2 and len(rutas_calculadas) > 0:

        m = folium.Map(
            tiles=None,
            zoom_control=True
        )

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google",
            name="Satélite"
        ).add_to(m)

        # --------------------------------------------------
        # RUTAS
        # --------------------------------------------------

        for ruta in rutas_calculadas:

            folium.PolyLine(
                ruta["geom"],
                color=ruta["color"],
                weight=5,
                opacity=0.85,
                tooltip=(
                    f"Tramo {ruta['tramo']}: "
                    f"{ruta['origen']['n']} ➜ {ruta['destino']['n']} "
                    f"({ruta['km']:.2f} KM)"
                )
            ).add_to(m)

        # --------------------------------------------------
        # MARCADORES DE POZOS / CLUSTERS
        # --------------------------------------------------

        for p in puntos_validos:

            c = colores[(p["id"] - 1) % len(colores)]

            label_html = f"""
            <div style="text-align:center;">
                <div style="
                    background:{c};
                    color:black;
                    border-radius:50%;
                    width:24px;
                    height:24px;
                    line-height:24px;
                    font-weight:bold;
                    border:2px solid white;
                    font-size:9pt;">
                    {p["id"]}
                </div>

                <div style="
                    background:rgba(14,17,23,0.90);
                    color:white;
                    padding:3px 8px;
                    border-radius:5px;
                    font-size:9pt;
                    margin-top:4px;
                    border:1px solid {c};
                    white-space:nowrap;">
                    {p["n"]}
                </div>
            </div>
            """

            folium.Marker(
                [p["lat"], p["lon"]],
                icon=DivIcon(
                    html=label_html,
                    icon_anchor=(12, 12)
                ),
                tooltip=p["n"]
            ).add_to(m)

        # --------------------------------------------------
        # COMUNIDADES
        # --------------------------------------------------

        for com, coord in COMUNIDADES.items():

            folium.Marker(
                [coord["lat"], coord["lon"]],
                icon=folium.Icon(
                    color="orange",
                    icon="home",
                    prefix="fa"
                ),
                tooltip=f"Comunidad: {com}"
            ).add_to(m)

            folium.Circle(
                [coord["lat"], coord["lon"]],
                radius=5000,
                color="orange",
                weight=1,
                fill=True,
                fill_opacity=0.10,
                opacity=0.40,
                tooltip=f"Radio de alerta 5 km - {com}"
            ).add_to(m)

        # --------------------------------------------------
        # AJUSTE DE ZOOM
        # --------------------------------------------------

        if all_coords:

            sw = [
                min(p[0] for p in all_coords),
                min(p[1] for p in all_coords)
            ]

            ne = [
                max(p[0] for p in all_coords),
                max(p[1] for p in all_coords)
            ]

            m.fit_bounds([sw, ne])

        st_folium(
            m,
            width="100%",
            height=700
        )

    else:
        st.info("Ingrese una ruta válida para visualizar el mapa.")
