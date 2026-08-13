import streamlit as st
from supabase import create_client, Client

st.title("Mon gestionnaire de menus")

# Initialisation de la connexion Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_connection():
    return create_client(url, key)

try:
    supabase = init_connection()
    # Test de lecture simple sur la table ingredients
    response = supabase.table("ingredients").select("*").execute()
    st.success("Connexion à la base de données Supabase réussie !")
except Exception as e:
    st.error(f"Erreur de connexion : {e}")
