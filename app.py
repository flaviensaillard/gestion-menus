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

# Navigation par onglets principaux
tab_ingredients, tab_recipes, tab_menus = st.tabs([
    "🥕 Ingrédients", 
    "📖 Recettes", 
    "📅 Menus & Courses"
])

UNITES = ["g", "kg", "ml", "cl", "l", "unité", "c. à soupe", "c. à café", "pincée", "sachet", "gousse", "tranche", "boîte"]
RAYONS = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers", 
          "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]

# ==========================================
# ONGLET 1 : GESTION DES INGRÉDIENTS
# ==========================================
with tab_ingredients:
    st.header("Gestion de la base d'ingrédients")
    col1, col2 = st.columns([1, 2])
    
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
                        data = {"name": name.strip().capitalize(), "unit": unit, "category": category}
                        supabase.table("ingredients").insert(data).execute()
                        st.success(f"Ingrédient '{name}' ajouté !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    with col2:
        st.subheader("📋 Ingrédients enregistrés")
        try:
            response = supabase.table("ingredients").select("*").order("name").execute()
            ingredients_list = response.data
            
            if not ingredients_list:
                st.info("Aucun ingrédient enregistré.")
            else:
                st.dataframe(
                    ingredients_list,
                    column_config={"id": None, "name": "Nom", "unit": "Unité", "category": "Rayon"},
                    use_container_width=True,
                    hide_index=True
                )
                
                with st.expander("✏️ Modifier un ingrédient existant"):
                    ing_dict = {f"{ing['name']} (actuellement: {ing['unit']})": ing for ing in ingredients_list}
                    selected_label = st.selectbox("Ingrédient à modifier", list(ing_dict.keys()), key="select_mod")
                    target_ing = ing_dict[selected_label]
                    
                    with st.form("form_edit_ingredient"):
                        new_name = st.text_input("Nom", value=target_ing["name"])
                        current_unit_idx = UNITES.index(target_ing["unit"]) if target_ing["unit"] in UNITES else 0
                        new_unit = st.selectbox("Unité par défaut", UNITES, index=current_unit_idx)
                        current_cat_idx = RAYONS.index(target_ing["category"]) if target_ing["category"] in RAYONS else 0
                        new_category = st.selectbox("Rayon / Catégorie", RAYONS, index=current_cat_idx)
                        
                        if st.form_submit_button("Enregistrer les modifications"):
                            supabase.table("ingredients").update({
                                "name": new_name.strip().capitalize(),
                                "unit": new_unit,
                                "category": new_category
                            }).eq("id", target_ing["id"]).execute()
                            st.success("Ingrédient mis à jour !")
                            st.rerun()

                with st.expander("🗑️ Supprimer un ingrédient"):
                    ing_del_dict = {f"{ing['name']} ({ing['unit']})": ing['id'] for ing in ingredients_list}
                    selected_del_label = st.selectbox("Ingrédient à supprimer", list(ing_del_dict.keys()), key="select_del")
                    
                    if st.button("Supprimer définitivement", type="primary"):
                        supabase.table("ingredients").delete().eq("id", ing_del_dict[selected_del_label]).execute()
                        st.warning("Ingrédient supprimé !")
                        st.rerun()
        except Exception as e:
            st.error(f"Erreur lors du chargement : {e}")

# ==========================================
# ONGLET 2 : GESTION DES RECETTES
# ==========================================
with tab_recipes:
    st.header("Gestion et consultation des recettes")
    
    subtab_view, subtab_edit = st.tabs(["🔍 Consulter une recette", "✏️ Créer / Éditer une recette"])
    
    # ------------------------------------------
    # SUBTAB 1 : CONSULTATION (PROPORTIONS)
    # ------------------------------------------
    with subtab_view:
        try:
            recipes_resp = supabase.table("recipes").select("*").order("name").execute()
            recipes_list = recipes_resp.data
            
            if not recipes_list:
                st.info("Aucune recette disponible. Allez dans l'onglet 'Créer / Éditer' pour en ajouter une.")
            else:
                recipe_options = {r["name"]: r for r in recipes_list}
                selected_recipe_name = st.selectbox("Choisir une recette à consulter", list(recipe_options.keys()))
                recipe = recipe_options[selected_recipe_name]
                
                st.markdown("---")
                col_rec_1, col_rec_2 = st.columns([1, 2])
                
                with col_rec_1:
                    st.subheader(f"📖 {recipe['name']}")
                    base_servings = recipe["base_servings"]
                    
                    target_servings = st.number_input(
                        "Nombre de personnes pour ce repas", 
                        min_value=1, 
                        max_value=50, 
                        value=base_servings,
                        step=1
                    )
                    
                    ratio = target_servings / base_servings
                    
                    if target_servings != base_servings:
                        st.caption(f"💡 Quantités ajustées pour {target_servings} pers. (Recette initiale prévue pour {base_servings} pers.)")
                
                with col_rec_2:
                    st.subheader("🛒 Ingrédients nécessaires")
                    
                    rec_ing_resp = supabase.table("recipe_ingredients")\
                        .select("quantity, ingredients(name, unit)")\
                        .eq("recipe_id", recipe["id"]).execute()
                    
                    rec_ingredients = rec_ing_resp.data
                    
                    if not rec_ingredients:
                        st.warning("Cette recette ne contient encore aucun ingrédient.")
                    else:
                        for item in rec_ingredients:
                            ing_info = item["ingredients"]
                            qty_calculated = round(item["quantity"] * ratio, 2)
                            qty_display = int(qty_calculated) if qty_calculated.is_integer() else qty_calculated
                            st.write(f"• **{ing_info['name']}** : {qty_display} {ing_info['unit']}")
                
                st.markdown("---")
                st.subheader("📝 Instructions de préparation")
                if recipe["instructions"]:
                    st.write(recipe["instructions"])
                else:
                    st.info("Aucune instruction renseignée pour cette recette.")
                    
        except Exception as e:
            st.error(f"Erreur de chargement des recettes : {e}")

    # ------------------------------------------
    # SUBTAB 2 : CRÉATION ET ÉDITION
    # ------------------------------------------
    with subtab_edit:
        col_create, col_manage = st.columns([1, 2])
        
        # --- NOUVELLE RECETTE ---
        with col_create:
            st.subheader("➕ Créer une nouvelle recette")
            with st.form("form_new_recipe", clear_on_submit=True):
                r_name = st.text_input("Nom de la recette *", placeholder="ex: Blanquette de veau")
                r_servings = st.number_input("Nombre de personnes de base *", min_value=1, value=4, step=1)
                r_instructions = st.text_area("Instructions de préparation", placeholder="Étape 1: ...")
                
                if st.form_submit_button("Créer la recette"):
                    if not r_name.strip():
                        st.error("Le nom de la recette est obligatoire.")
                    else:
                        try:
                            supabase.table("recipes").insert({
                                "name": r_name.strip().capitalize(),
                                "base_servings": r_servings,
                                "instructions": r_instructions
                            }).execute()
                            st.success(f"Recette '{r_name}' créée ! Ajoutez maintenant ses ingrédients à droite.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        # --- GÉRER LES INGRÉDIENTS D'UNE RECETTE EXISTANTE ---
        with col_manage:
            st.subheader("⚙️ Modifier / Dupliquer une recette")
            
            try:
                recipes_resp = supabase.table("recipes").select("*").order("name").execute()
                all_recipes = recipes_resp.data
                all_ing_resp = supabase.table("ingredients").select("*").order("name").execute()
                all_ingredients = all_ing_resp.data
                
                if not all_recipes:
                    st.info("Aucune recette à modifier. Créez-en une à gauche.")
                elif not all_ingredients:
                    st.warning("Attention : Aucun ingrédient dans la base. Veuillez en créer dans le 1er onglet !")
                else:
                    edit_recipe_options = {r["name"]: r for r in all_recipes}
                    selected_edit_name = st.selectbox("Sélectionner la recette à gérer", list(edit_recipe_options.keys()))
                    target_recipe = edit_recipe_options[selected_edit_name]
                    
                    # Formulaire de modification de l'en-tête de la recette
                    with st.expander("✏️ Modifier nom / personnes de base / instructions"):
                        with st.form("form_update_recipe"):
                            up_name = st.text_input("Nom", value=target_recipe["name"])
                            up_servings = st.number_input("Nombre de personnes de base", min_value=1, value=target_recipe["base_servings"])
                            up_instructions = st.text_area("Instructions", value=target_recipe["instructions"] or "")
                            
                            if st.form_submit_button("Sauvegarder l'en-tête"):
                                supabase.table("recipes").update({
                                    "name": up_name.strip().capitalize(),
                                    "base_servings": up_servings,
                                    "instructions": up_instructions
                                }).eq("id", target_recipe["id"]).execute()
                                st.success("En-tête de recette mis à jour !")
                                st.rerun()

                    # --- DUPLICATION DE RECETTE ---
                    with st.expander("📋 Dupliquer cette recette"):
                        dup_name = st.text_input("Nom de la copie", value=f"{target_recipe['name']} (Copie)")
                        if st.button("Dupliquer maintenant", key="btn_dup_recipe"):
                            if not dup_name.strip():
                                st.error("Le nom ne peut pas être vide.")
                            else:
                                try:
                                    # 1. Création de la recette
                                    new_rec_resp = supabase.table("recipes").insert({
                                        "name": dup_name.strip().capitalize(),
                                        "base_servings": target_recipe["base_servings"],
                                        "instructions": target_recipe["instructions"]
                                    }).execute()
                                    
                                    new_recipe_id = new_rec_resp.data[0]["id"]
                                    
                                    # 2. Récupération des ingrédients originaux
                                    orig_ing_resp = supabase.table("recipe_ingredients")\
                                        .select("ingredient_id, quantity")\
                                        .eq("recipe_id", target_recipe["id"]).execute()
                                    
                                    orig_ings = orig_ing_resp.data
                                    
                                    # 3. Copie des ingrédients vers la nouvelle recette
                                    if orig_ings:
                                        new_ings_data = [
                                            {
                                                "recipe_id": new_recipe_id,
                                                "ingredient_id": item["ingredient_id"],
                                                "quantity": item["quantity"]
                                            }
                                            for item in orig_ings
                                        ]
                                        supabase.table("recipe_ingredients").insert(new_ings_data).execute()
                                    
                                    st.success(f"Recette dupliquée sous le nom '{dup_name}' !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erreur lors de la duplication : {e}")

                    st.markdown("##### Ingrédients de la recette")
                    
                    curr_ing_resp = supabase.table("recipe_ingredients")\
                        .select("id, quantity, ingredient_id, ingredients(name, unit)")\
                        .eq("recipe_id", target_recipe["id"]).execute()
                    
                    curr_ingredients = curr_ing_resp.data
                    
                    if curr_ingredients:
                        for c_ing in curr_ingredients:
                            c_col1, c_col2, c_col3 = st.columns([3, 2, 1])
                            c_col1.write(f"• **{c_ing['ingredients']['name']}**")
                            c_col2.write(f"{c_ing['quantity']} {c_ing['ingredients']['unit']}")
                            if c_col3.button("❌", key=f"del_rel_{c_ing['id']}"):
                                supabase.table("recipe_ingredients").delete().eq("id", c_ing["id"]).execute()
                                st.rerun()
                    else:
                        st.caption("Cette recette n'a pas encore d'ingrédients.")

                    st.markdown("---")
                    st.markdown("**Ajouter un ingrédient à cette recette :**")
                    
                    ing_dropdown = {f"{i['name']} ({i['unit']})": i for i in all_ingredients}
                    col_add_1, col_add_2, col_add_3 = st.columns([2, 1, 1])
                    
                    sel_ing_label = col_add_1.selectbox("Ingrédient", list(ing_dropdown.keys()), key="select_ing_to_rec")
                    sel_ing_obj = ing_dropdown[sel_ing_label]
                    
                    add_qty = col_add_2.number_input(f"Quantité ({sel_ing_obj['unit']})", min_value=0.1, value=100.0, step=10.0)
                    
                    if col_add_3.button("➕ Ajouter"):
                        try:
                            supabase.table("recipe_ingredients").insert({
                                "recipe_id": target_recipe["id"],
                                "ingredient_id": sel_ing_obj["id"],
                                "quantity": add_qty
                            }).execute()
                            st.success("Ingrédient ajouté à la recette !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

                    with st.expander("🗑️ Supprimer toute la recette"):
                        if st.button("Supprimer cette recette définitivement", type="primary", key="btn_del_recipe"):
                            supabase.table("recipes").delete().eq("id", target_recipe["id"]).execute()
                            st.warning("Recette supprimée !")
                            st.rerun()

            except Exception as e:
                st.error(f"Erreur : {e}")

# ==========================================
# ONGLET 3 (À VENIR)
# ==========================================
with tab_menus:
    st.info("L'onglet Menus & Courses sera développé à l'étape suivante.")
