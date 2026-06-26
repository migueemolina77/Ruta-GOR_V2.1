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
