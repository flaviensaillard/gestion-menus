import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Gestionnaire de Menus", layout="wide")

# Initialisation de Supabase
url: str = st.secrets["SUPABASE_URL"]
key: str = st.secrets["SUPABASE_KEY"]

@st.cache_resource
def init_connection():
    return create_client(url, key)

supabase = init_connection()

st.title("🍽️ Mon Gestionnaire de Menus")

# Navigation par onglets
tab_ingredients, tab_recipes, tab_menus = st.tabs([
    "🥕 Ingrédients", 
    "📖 Recettes", 
    "📅 Menus & Courses"
])

# ==========================================
# ONGLET 1 : GESTION DES INGRÉDIENTS
# ==========================================
with tab_ingredients:
    st.header("Gestion de la base d'ingrédients")
    
    col1, col2 = st.columns([1, 2])
    
    # --- Formulaire d'ajout ---
    with col1:
        st.subheader("Ajouter un ingrédient")
        with st.form("form_add_ingredient", clear_on_submit=True):
            name = st.text_input("Nom de l'ingrédient *", placeholder="ex: Carotte, Lait, Œuf...")
            
            unit = st.selectbox(
                "Unité par défaut *",
                ["g", "kg", "ml", "cl", "l", "unité", "c. à soupe", "c. à café", "pincée", "sachet"]
            )
            
            category = st.selectbox(
                "Rayon / Catégorie",
                ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers", 
                 "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]
            )
            
            submitted = st.form_submit_button("➕ Ajouter l'ingrédient")
            
            if submitted:
                if not name.strip():
                    st.error("Le nom de l'ingrédient ne peut pas être vide.")
                else:
                    try:
                        # Insertion dans Supabase
                        data = {
                            "name": name.strip().capitalize(),
                            "unit": unit,
                            "category": category
                        }
                        supabase.table("ingredients").insert(data).execute()
                        st.success(f"Ingrédient '{name}' ajouté avec succès !")
                        st.rerun() # Recharge la page pour afficher le nouvel ingrédient
                    except Exception as e:
                        st.error(f"Erreur lors de l'ajout : {e}")

    # --- Liste et suppression des ingrédients ---
    with col2:
        st.subheader("Ingrédients enregistrés")
        
        try:
            # Récupération des ingrédients triés par nom
            response = supabase.table("ingredients").select("*").order("name").execute()
            ingredients_list = response.data
            
            if not ingredients_list:
                st.info("Aucun ingrédient enregistré pour le moment. Utilisez le formulaire à gauche.")
            else:
                # Affichage sous forme de tableau
                st.dataframe(
                    ingredients_list,
                    column_config={
                        "id": None, # Masquer la colonne ID
                        "name": "Nom",
                        "unit": "Unité",
                        "category": "Rayon"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Zone de suppression
                with st.expander("🗑️ Supprimer un ingrédient"):
                    ing_options = {f"{ing['name']} ({ing['unit']})": ing['id'] for ing in ingredients_list}
                    selected_ing_label = st.selectbox("Sélectionner l'ingrédient à supprimer", list(ing_options.keys()))
                    
                    if st.button("Supprimer définitivement"):
                        ing_id = ing_options[selected_ing_label]
                        supabase.table("ingredients").delete().eq("id", ing_id).execute()
                        st.warning("Ingrédient supprimé !")
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Impossible de charger la liste : {e}")

# ==========================================
# ONGLET 2 & 3 (À VENIR)
# ==========================================
with tab_recipes:
    st.info("L'onglet Recettes sera développé à l'étape suivante.")

with tab_menus:
    st.info("L'onglet Menus & Courses sera développé à l'étape suivante.")
