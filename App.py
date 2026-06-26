# ✅ Cargar columnas
col_ui, col_map = st.columns([1.1, 3])

# -----------------------------
# UI - PLAN DE RUTA
# -----------------------------
with col_ui:
    st.subheader("Plan de Ruta")

    entrada = st.text_area("Lista de Pozos:")

    if entrada:

        nombres = [n.strip().upper() for n in re.split(r'[\n,]+', entrada) if n.strip()]
        puntos_validos = []

        for i, n in enumerate(nombres):
            key = re.sub(r'[^a-zA-Z0-9]', '', n)

            match = db[db['KEY'].str.contains(key, case=False, na=False)]

            if not match.empty:
                puntos_validos.append({
                    'id': i+1,
                    'n': match.iloc[0]['NAME'],
                    'lat': match.iloc[0]['lat'],
                    'lon': match.iloc[0]['lon']
                })

        if len(puntos_validos) >= 2:

            st.divider()

            km_totales = 0
            all_coords = []
            colores = ["#00FFCC", "#FF007F", "#FFD700", "#00BFFF"]

            for i in range(len(puntos_validos)-1):
                p_orig = puntos_validos[i]
                p_dest = puntos_validos[i+1]

                geom, km = obtener_ruta_osrm(p_orig, p_dest)

                km_totales += km
                all_coords.extend(geom)

                c = colores[i % len(colores)]

                # ✅ ALERTAS DENTRO DEL LOOP
                alerta_html = ""

                for com, coord in COMUNIDADES.items():
                    cerca_orig = haversine(p_orig['lat'], p_orig['lon'], coord['lat'], coord['lon']) < 5.0
                    cerca_dest = haversine(p_dest['lat'], p_dest['lon'], coord['lat'], coord['lon']) < 5.0
                    cerca_ruta = any(haversine(g[0], g[1], coord['lat'], coord['lon']) < 5.0 for g in geom)

                    if cerca_orig or cerca_dest or cerca_ruta:
                        alerta_html += f'<div class="alerta-box alerta-comunidad">⚠ TRÁNSITO POR {com}</div>'

                if km > 30:
                    alerta_html += '<div class="alerta-box alerta-despine">🚛 DESPINAR TORRE</div>'

                st.markdown(f"""
                <div class="tramo-card" style="border-left-color: {c};">
                    <div class="tramo-header">Tramo {i+1} ➔ {i+2}</div>
                    <div class="tramo-nombres"><b>{p_orig['n']}</b> ➔ <b>{p_dest['n']}</b></div>
                    <span class="tramo-distancia" style="color:{c};">{km:.2f} KM</span>
                    {alerta_html}
                </div>
                """, unsafe_allow_html=True)

            st.metric("DISTANCIA TOTAL", f"{km_totales:.2f} KM")

# -----------------------------
# MAPA
# -----------------------------
with col_map:
    if entrada and len(puntos_validos) >= 2:

        m = folium.Map(tiles=None)

        folium.TileLayer(
            tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            attr="Google",
            name="Satélite"
        ).add_to(m)

        # Rutas
        for i in range(len(puntos_validos)-1):
            geom, _ = obtener_ruta_osrm(puntos_validos[i], puntos_validos[i+1])
            c = colores[i % len(colores)]

            folium.PolyLine(
                geom,
                color=c,
                weight=5,
                opacity=0.8
            ).add_to(m)

        # Pins PRO
        for p in puntos_validos:
            c = colores[(p['id']-1) % len(colores)]

            label_html = f"""
            <div style="text-align:center;">
                <div style="
                    background:{c};
                    color:black;
                    border-radius:50%;
                    width:28px;
                    height:28px;
                    line-height:28px;
                    font-weight:bold;
                    border:2px solid white;
                ">
                    {p['id']}
                </div>
                <div style="
                    background:rgba(14,17,23,0.9);
                    color:white;
                    padding:4px 8px;
                    border-radius:6px;
                    font-size:10px;
                    margin-top:4px;
                    border:1px solid {c};
                    white-space:nowrap;
                ">
                    ⛽ {p['n']}
                </div>
            </div>
            """

            folium.Marker(
                [p['lat'], p['lon']],
                icon=DivIcon(html=label_html, icon_anchor=(11, 11))
            ).add_to(m)

        # Comunidades
        for com, coord in COMUNIDADES.items():
            folium.Marker(
                [coord['lat'], coord['lon']],
                icon=folium.Icon(color='orange', icon='home'),
                tooltip=f"Comunidad: {com}"
            ).add_to(m)

        # Auto zoom
        if all_coords:
            sw = [min(p[0] for p in all_coords), min(p[1] for p in all_coords)]
            ne = [max(p[0] for p in all_coords), max(p[1] for p in all_coords)]
            m.fit_bounds([sw, ne])

        st_folium(m, width="100%", height=700)
