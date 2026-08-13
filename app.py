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

# Unités et Rayons disponibles (réutilisables)
UNITES = ["g", "kg", "ml", "cl", "l", "unité", "c. à soupe", "c. à café", "pincée", "sachet", "gousse", "tranche", "boîte"]
RAYONS = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers", 
          "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]

# ==========================================
# ONGLET 1 : GESTION DES INGRÉDIENTS
# ==========================================
with tab_ingredients:
    st.header("Gestion de la base d'ingrédients")
    
    col1, col2 = st.columns([1, 2])
    
    # --- Formulaire d'ajout ---
    with col1:
        st.subheader("➕ Ajouter un ingrédient")
        with st.form("form_add_ingredient", clear_on_submit=True):
            name = st.text_input("Nom de l'ingrédient *", placeholder="ex: Carotte, Lait, Œuf...")
            unit = st.selectbox("Unité par défaut *", UNITES)
            category = st.selectbox("Rayon / Catégorie", RAYONS)
            
            submitted = st.form_submit_button("Ajouter l'ingrédient")
            
            if submitted:
                if not name.strip():
                    st.error("Le nom de l'ingrédient ne peut pas être vide.")
                else:
                    try:
                        data = {
                            "name": name.strip().capitalize(),
                            "unit": unit,
                            "category": category
                        }
                        supabase.table("ingredients").insert(data).execute()
                        st.success(f"Ingrédient '{name}' ajouté !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur lors de l'ajout : {e}")

    # --- Liste, Modification et Suppression ---
    with col2:
        st.subheader("📋 Ingrédients enregistrés")
        
        try:
            response = supabase.table("ingredients").select("*").order("name").execute()
            ingredients_list = response.data
            
            if not ingredients_list:
                st.info("Aucun ingrédient enregistré pour le moment.")
            else:
                # Affichage du tableau
                st.dataframe(
                    ingredients_list,
                    column_config={
                        "id": None, # Masquer l'ID
                        "name": "Nom",
                        "unit": "Unité",
                        "category": "Rayon"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # --- Bloc de Modification ---
                with st.expander("✏️ Modifier un ingrédient existant"):
                    ing_dict = {f"{ing['name']} (actuellement: {ing['unit']})": ing for ing in ingredients_list}
                    selected_label = st.selectbox("Sélectionne l'ingrédient à modifier", list(ing_dict.keys()), key="select_mod")
                    
                    target_ing = ing_dict[selected_label]
                    
                    with st.form("form_edit_ingredient"):
                        new_name = st.text_input("Nom", value=target_ing["name"])
                        
                        # Trouver l'index de l'unité actuelle pour pré-sélectionner
                        current_unit_idx = UNITES.index(target_ing["unit"]) if target_ing["unit"] in UNITES else 0
                        new_unit = st.selectbox("Unité par défaut", UNITES, index=current_unit_idx)
                        
                        # Trouver l'index du rayon actuel
                        current_cat_idx = RAYONS.index(target_ing["category"]) if target_ing["category"] in RAYONS else 0
                        new_category = st.selectbox("Rayon / Catégorie", RAYONS, index=current_cat_idx)
                        
                        update_submitted = st.form_submit_button("Enregistrer les modifications")
                        
                        if update_submitted:
                            try:
                                supabase.table("ingredients").update({
                                    "name": new_name.strip().capitalize(),
                                    "unit": new_unit,
                                    "category": new_category
                                }).eq("id", target_ing["id"]).execute()
                                
                                st.success("Ingrédient mis à jour avec succès !")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur lors de la mise à jour : {e}")

                # --- Bloc de Suppression ---
                with st.expander("🗑️ Supprimer un ingrédient"):
                    ing_del_dict = {f"{ing['name']} ({ing['unit']})": ing['id'] for ing in ingredients_list}
                    selected_del_label = st.selectbox("Sélectionne l'ingrédient à supprimer", list(ing_del_dict.keys()), key="select_del")
                    
                    if st.button("Supprimer définitivement", type="primary"):
                        try:
                            ing_id = ing_del_dict[selected_del_label]
                            supabase.table("ingredients").delete().eq("id", ing_id).execute()
                            st.warning("Ingrédient supprimé !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la suppression : {e}")
                        
        except Exception as e:
            st.error(f"Impossible de charger la liste : {e}")

# ==========================================
# ONGLET 2 & 3 (À VENIR)
# ==========================================
with tab_recipes:
    st.info("L'onglet Recettes sera développé à l'étape suivante.")

with tab_menus:
    st.info("L'onglet Menus & Courses sera développé à l'étape suivante.")
