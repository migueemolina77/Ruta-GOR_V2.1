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
# CONFIGURACION GENERAL
# ======================================================

st.set_page_config(
    page_title="LOGISTICA RUBIALES V7.7 - ALERTAS AUTOMATICAS",
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
# PUNTOS CRITICOS VALIDADOS
# ======================================================

PUNTOS_CRITICOS_VALIDACION = {
    # ==================================================
    # COMUNIDADES
    # ==================================================

    "OASIS": {
        "lat": 3.775392,
        "lon": -71.658505,
        "tipo": "COMUNIDAD",
        "alerta": "RESTRICCION NOCTURNA FIJA",
        "radio_km": 1.0
    },
    "SANTA HELENA": {
        "lat": 3.899376,
        "lon": -71.490427,
        "tipo": "COMUNIDAD",
        "alerta": "RESTRICCION NOCTURNA PROBABLE",
        "radio_km": 1.0
    },
    "BUENOS AIRES - RUBIALITO": {
        "lat": 3.793411,
        "lon": -71.384503,
        "tipo": "COMUNIDAD",
        "alerta": "RESTRICCION NOCTURNA PROBABLE",
        "radio_km": 1.0
    },
    "EL PORVENIR": {
        "lat": 3.765052,
        "lon": -71.363584,
        "tipo": "COMUNIDAD",
        "alerta": "RESTRICCION NOCTURNA PROBABLE",
        "radio_km": 1.0
    },

    # ==================================================
    # PUENTES / CAÑOS - PUNTOS DE DESPINE
    # ==================================================
    "PUENTE CPF 1": {
        "lat": 3.813599,
        "lon": -71.433355,
        "tipo": "PUENTE",
        "alerta": "DESPINADO",
        "radio_km": 1.0
    },
    "PUENTE CAÑO MASIFERIANO": {
        "lat": 3.799900,
        "lon": -71.472938,
        "tipo": "PUENTE",
        "alerta": "DESPINADO",
        "radio_km": 1.0
    },
    "CAÑO FELICIANO": {
        "lat": 3.852608,
        "lon": -71.420776,
        "tipo": "PUENTE",
        "alerta": "DESPINADO",
        "radio_km": 1.0
    },

    # ==================================================
    # FINCAS / RELACIONAMIENTO
    # ==================================================
    "LA PALOMA": {
        "lat": 3.726750,
        "lon": -71.421637,
        "tipo": "FINCA",
        "alerta": "RELACIONAMIENTO ENTORNO / TIERRAS",
        "radio_km": 1.0
    },
    "LINCON": {
        "lat": 3.723330,
        "lon": -71.530597,
        "tipo": "FINCA",
        "alerta": "RELACIONAMIENTO ENTORNO / TIERRAS",
        "radio_km": 1.0
    },
    "TIYABA": {
        "lat": 3.809906,
        "lon": -71.595794,
        "tipo": "FINCA",
        "alerta": "RELACIONAMIENTO ENTORNO / TIERRAS",
        "radio_km": 1.0
    }
}

# ======================================================
# AEROPUERTO MORELIA
# ======================================================
# Se maneja por separado porque tiene dos radios:
# 2 km = alerta critica
# 5 km = alerta preventiva

AEROPUERTO_MORELIA = {
    "nombre": "AEROPUERTO MORELIA",
    "lat": 3.750656,
    "lon": -71.455936,
    "radio_critico_km": 2.0,
    "radio_preventivo_km": 5.0
}


# ======================================================
# FUNCIONES TECNICAS
# ======================================================

def haversine(lat1, lon1, lat2, lon2):
    """
    Calcula distancia aproximada entre dos coordenadas geograficas en kilometros.
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


def distancia_punto_a_segmento_km(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon):
    """
    Calcula la distancia minima aproximada entre un punto critico y un segmento de ruta.
    Usa proyeccion local en km, suficiente para distancias cortas dentro del campo.
    """

    lat_ref = math.radians(p_lat)

    km_por_grado_lat = 110.574
    km_por_grado_lon = 111.320 * math.cos(lat_ref)

    ax = (a_lon - p_lon) * km_por_grado_lon
    ay = (a_lat - p_lat) * km_por_grado_lat

    bx = (b_lon - p_lon) * km_por_grado_lon
    by = (b_lat - p_lat) * km_por_grado_lat

    dx = bx - ax
    dy = by - ay

    if dx == 0 and dy == 0:
        return math.sqrt(ax ** 2 + ay ** 2)

    t = -((ax * dx) + (ay * dy)) / (dx ** 2 + dy ** 2)
    t = max(0, min(1, t))

    punto_cercano_x = ax + t * dx
    punto_cercano_y = ay + t * dy

    distancia = math.sqrt(
        punto_cercano_x ** 2 +
        punto_cercano_y ** 2
    )

    return distancia


def distancia_minima_a_ruta_km(lat, lon, geom):
    """
    Calcula la distancia minima entre un punto critico y toda la geometria de la ruta.
    geom debe venir como lista: [[lat, lon], [lat, lon], ...]
    """

    if not geom or len(geom) == 0:
        return None

    if len(geom) == 1:
        return haversine(lat, lon, geom[0][0], geom[0][1])

    distancias = []

    for i in range(len(geom) - 1):
        a_lat, a_lon = geom[i]
        b_lat, b_lon = geom[i + 1]

        d = distancia_punto_a_segmento_km(
            lat,
            lon,
            a_lat,
            a_lon,
            b_lat,
            b_lon
        )

        distancias.append(d)

    return min(distancias)


def evaluar_alertas_puntos_criticos(geom):
    """
    Evalua si la ruta pasa dentro del radio de algun punto critico:
    - Comunidad
    - Puente / Caño
    - Finca
    """

    alertas_detectadas = []

    for nombre, punto in PUNTOS_CRITICOS_VALIDACION.items():

        tipo = punto["tipo"]
        radio_km = punto.get("radio_km", 1.0)

        distancia_min = distancia_minima_a_ruta_km(
            punto["lat"],
            punto["lon"],
            geom
        )

        if distancia_min is None:
            continue

        if distancia_min <= radio_km:

            if tipo == "COMUNIDAD":
                mensaje = (
                    f"⚠️ {punto['alerta']}: ruta cercana a {nombre} "
                    f"({distancia_min:.2f} km | radio {radio_km:.1f} km)"
                )

            elif tipo == "PUENTE":
                mensaje = (
                    f"🚧 DESPINAR TORRE: cruce cercano a {nombre} "
                    f"({distancia_min:.2f} km | radio {radio_km:.1f} km)"
                )

            elif tipo == "FINCA":
                mensaje = (
                    f"🤝 {punto['alerta']}: ruta cercana a {nombre} "
                    f"({distancia_min:.2f} km | radio {radio_km:.1f} km)"
                )

            else:
                mensaje = (
                    f"ℹ️ Punto critico cercano: {nombre} "
                    f"({distancia_min:.2f} km | radio {radio_km:.1f} km)"
                )

            alertas_detectadas.append({
                "tipo": tipo,
                "nombre": nombre,
                "mensaje": mensaje,
                "distancia_km": distancia_min,
                "radio_km": radio_km
            })

    return alertas_detectadas


def proyectadas_a_latlon_colombia(este, norte):
    """
    Convierte coordenadas proyectadas a latitud/longitud.
    Mantiene la logica original del aplicativo funcional.
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
    Consulta OSRM para obtener geometria y distancia de ruta.
    Si OSRM falla, retorna linea recta entre los dos puntos.
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
    Usa coincidencia exacta primero y luego coincidencia parcial.
    """

    key = re.sub(r"[^a-zA-Z0-9]", "", nombre).upper()

    if key == "":
        return None

    match_exacto = db[db["KEY"] == key]

    if not match_exacto.empty:
        return match_exacto.iloc[0]

    match_contiene = db[
        db["KEY"].str.contains(
            key,
            case=False,
            na=False,
            regex=False
        )
    ]

    if not match_contiene.empty:
        return match_contiene.iloc[0]

    return None


# ======================================================
# INTERFAZ PRINCIPAL
# ======================================================

st.markdown(
    "<h1 style='text-align: center;'>🦎 MAPA GOR - ECOPETROL</h1>",
    unsafe_allow_html=True
)

st.caption("Version V7.7 - Alertas automaticas por comunidades, puentes/canos y fincas")

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

    for nombre in nombres:

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

            # --------------------------------------------------
            # ALERTAS AUTOMATICAS POR PUNTOS CRITICOS
            # --------------------------------------------------

            alertas = []

            alertas_puntos = evaluar_alertas_puntos_criticos(geom)
            alertas.extend(alertas_puntos)

            # --------------------------------------------------
            # ALERTA POR DISTANCIA MAYOR A 30 KM
            # --------------------------------------------------

            if km > 30:
                alertas.append({
                    "tipo": "DISTANCIA",
                    "nombre": "DISTANCIA MAYOR A 30 KM",
                    "mensaje": "🚚 DESPINAR TORRE POR DISTANCIA MAYOR A 30 KM",
                    "distancia_km": km,
                    "radio_km": None
                })

            # --------------------------------------------------
            # TARJETA NATIVA STREAMLIT
            # --------------------------------------------------

            with st.container(border=True):

                st.caption(f"TRAMO {i + 1} ➜ {i + 2}")

                st.markdown(
                    f"**{p_orig['n']} ➜ {p_dest['n']}**"
                )

                distancia_html = (
                    f"<h3 style='color:{c}; margin-top:0px; margin-bottom:8px;'>"
                    f"{km:.2f} KM"
                    f"</h3>"
                )

                st.markdown(distancia_html, unsafe_allow_html=True)

                if len(alertas) == 0:
                    st.success("✅ Sin alertas críticas detectadas en este tramo.")

                for alerta in alertas:

                    if alerta["tipo"] in ["PUENTE", "DISTANCIA"]:
                        st.error(alerta["mensaje"])

                    elif alerta["tipo"] == "COMUNIDAD":
                        st.warning(alerta["mensaje"])

                    elif alerta["tipo"] == "FINCA":
                        st.info(alerta["mensaje"])

                    else:
                        st.info(alerta["mensaje"])

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
        # PUNTOS CRITICOS EN MAPA
        # --------------------------------------------------

        for nombre, punto in PUNTOS_CRITICOS_VALIDACION.items():

            tipo = punto["tipo"]
            radio_km = punto.get("radio_km", 1.0)

            if tipo == "COMUNIDAD":
                color = "orange"
                icono = "users"
            elif tipo == "PUENTE":
                color = "red"
                icono = "road"
            elif tipo == "FINCA":
                color = "blue"
                icono = "home"
            else:
                color = "gray"
                icono = "info-sign"

            folium.Marker(
                [punto["lat"], punto["lon"]],
                icon=folium.Icon(
                    color=color,
                    icon=icono,
                    prefix="fa"
                ),
                tooltip=f"{tipo}: {nombre} - {punto['alerta']}"
            ).add_to(m)

            folium.Circle(
                [punto["lat"], punto["lon"]],
                radius=radio_km * 1000,
                color=color,
                weight=2,
                fill=True,
                fill_opacity=0.10,
                opacity=0.50,
                tooltip=f"{nombre} | Radio {radio_km} km | {punto['alerta']}"
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
