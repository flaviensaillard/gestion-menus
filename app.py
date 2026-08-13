import streamlit as st
from supabase import create_client, Client
from fpdf import FPDF
import io

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
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
REPAS = ["Midi", "Soir"]

# ==========================================
# FONCTION DE GÉNÉRATION DU PDF A4
# ==========================================
def clean_pdf_str(text):
    """ Nettoie les chaînes de caractères pour FPDF (encodage Latin-1) """
    if not text:
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def generate_pdf(planned_meals, aggregated_items, recurrent_items, recipes_dict):
    pdf = FPDF(format='A4', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # En-tête principal
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, clean_pdf_str('Menu de la Semaine & Liste de Courses'), ln=True, align='C')
    pdf.ln(3)
    
    # --- SECTION 1 : PLANNING DE LA SEMAINE ---
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(0, 7, clean_pdf_str(' 1. Planning des Repas'), ln=True, fill=True)
    pdf.ln(2)
    
    # Préparation des données par jour
    schedule = {d: {"Midi": "-", "Soir": "-"} for d in JOURS}
    for pm in planned_meals:
        d = pm['day']
        m = pm['meal_type']
        rec_name = recipes_dict.get(pm['recipe_id'], {}).get('name', 'Inconnu')
        serv = pm['servings']
        if d in schedule and m in schedule[d]:
            schedule[d][m] = f"{rec_name} ({serv}p)"
            
    # Tableau du planning
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(30, 6, clean_pdf_str('Jour'), border=1)
    pdf.cell(80, 6, clean_pdf_str('Midi'), border=1)
    pdf.cell(80, 6, clean_pdf_str('Soir'), border=1, ln=True)
    
    pdf.set_font('Helvetica', size=8)
    for day in JOURS:
        midi_txt = clean_pdf_str(schedule[day]['Midi'])[:45]
        soir_txt = clean_pdf_str(schedule[day]['Soir'])[:45]
        pdf.cell(30, 5, clean_pdf_str(day), border=1)
        pdf.cell(80, 5, midi_txt, border=1)
        pdf.cell(80, 5, soir_txt, border=1, ln=True)
        
    pdf.ln(5)
    
    # Ligne de découpe pointillée
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 4, clean_pdf_str('- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - ( Découper ici ) - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -'), align='C', ln=True)
    pdf.ln(5)
    
    # --- SECTION 2 : LISTE DE COURSES ---
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 7, clean_pdf_str(' 2. Liste de Courses'), ln=True, fill=True)
    pdf.ln(2)
    
    by_cat = {}
    for item in aggregated_items.values():
        cat = item['category']
        by_cat.setdefault(cat, []).append(item)
        
    if not by_cat:
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, clean_pdf_str('Aucun article à acheter pour ces repas.'), ln=True)
    else:
        for cat in RAYONS:
            if cat in by_cat:
                pdf.set_font('Helvetica', 'B', 10)
                pdf.cell(0, 5, clean_pdf_str(f"• {cat}"), ln=True)
                pdf.set_font('Helvetica', size=9)
                for it in by_cat[cat]:
                    qty = round(it['qty'], 2)
                    qty_str = int(qty) if isinstance(qty, float) and qty.is_integer() else qty
                    line = f"   [  ] {it['name']} : {qty_str} {it['unit']}"
                    pdf.cell(0, 4.5, clean_pdf_str(line), ln=True)
                pdf.ln(1)
                
    pdf.ln(3)
    
    # --- SECTION 3 : PRODUITS RÉCURRENTS ---
    if recurrent_items:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 6, clean_pdf_str(' 3. Produits récurrents (à vérifier)'), ln=True, fill=True)
        pdf.ln(2)
        pdf.set_font('Helvetica', size=8)
        
        # Affichage sur 2 colonnes pour gagner de la place
        col_width = 90
        for i, rec in enumerate(recurrent_items):
            txt = clean_pdf_str(f"[  ] {rec['name']} ({rec['category']})")
            pdf.cell(col_width, 4.5, txt, border=0)
            if (i + 1) % 2 == 0:
                pdf.ln()
        if len(recurrent_items) % 2 != 0:
            pdf.ln()

    return bytes(pdf.output())


# ==========================================
# ONGLET 1 : GESTION DES INGRÉDIENTS
# ==========================================
with tab_ingredients:
    st.header("Gestion de la base d'ingrédients")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("➕ Ajouter un ingrédient")
        with st.form("form_add_ingredient", clear_on_submit=True):
            name = st.text_input("Nom de l'ingrédient *", placeholder="ex: Carotte, Lait, Huile d'olive...")
            unit = st.selectbox("Unité par défaut *", UNITES)
            category = st.selectbox("Rayon / Catégorie", RAYONS)
            
            st.markdown("---")
            exclude_from_list = st.checkbox("🚪 Fond de placard (ne jamais ajouter aux courses)")
            is_recurrent = st.checkbox("🔁 Produit récurrent (pense-bête permanent sur la liste)")
            
            submitted = st.form_submit_button("Ajouter l'ingrédient")
            
            if submitted:
                if not name.strip():
                    st.error("Le nom de l'ingrédient ne peut pas être vide.")
                else:
                    try:
                        data = {
                            "name": name.strip().capitalize(), 
                            "unit": unit, 
                            "category": category,
                            "exclude_from_list": exclude_from_list,
                            "is_recurrent": is_recurrent
                        }
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
                    column_config={
                        "id": None, 
                        "name": "Nom", 
                        "unit": "Unité", 
                        "category": "Rayon",
                        "exclude_from_list": st.column_config.CheckboxColumn(
                            "Fond de placard",
                            help="Si coché, cet ingrédient ne sera jamais ajouté à la liste de courses."
                        ),
                        "is_recurrent": st.column_config.CheckboxColumn(
                            "Récurrent",
                            help="Si coché, cet ingrédient sera toujours présent dans le bloc 'Produits récurrents'."
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                with st.expander("✏️ Modifier un ingrédient existant"):
                    ing_dict = {f"{ing['name']} ({ing['unit']})": ing for ing in ingredients_list}
                    selected_label = st.selectbox("Ingrédient à modifier", list(ing_dict.keys()), key="select_mod")
                    target_ing = ing_dict[selected_label]
                    
                    with st.form("form_edit_ingredient"):
                        new_name = st.text_input("Nom", value=target_ing["name"])
                        current_unit_idx = UNITES.index(target_ing["unit"]) if target_ing["unit"] in UNITES else 0
                        new_unit = st.selectbox("Unité par défaut", UNITES, index=current_unit_idx)
                        current_cat_idx = RAYONS.index(target_ing["category"]) if target_ing["category"] in RAYONS else 0
                        new_category = st.selectbox("Rayon / Catégorie", RAYONS, index=current_cat_idx)
                        
                        current_exclude = target_ing.get("exclude_from_list", False) or False
                        new_exclude = st.checkbox("🚪 Fond de placard (exclure de la liste de courses)", value=current_exclude)
                        
                        current_recurrent = target_ing.get("is_recurrent", False) or False
                        new_recurrent = st.checkbox("🔁 Produit récurrent (pense-bête permanent sur la liste)", value=current_recurrent)
                        
                        if st.form_submit_button("Enregistrer les modifications"):
                            supabase.table("ingredients").update({
                                "name": new_name.strip().capitalize(),
                                "unit": new_unit,
                                "category": new_category,
                                "exclude_from_list": new_exclude,
                                "is_recurrent": new_recurrent
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
                        .select("quantity, ingredients(name, unit, exclude_from_list, is_recurrent)")\
                        .eq("recipe_id", recipe["id"]).execute()
                    
                    rec_ingredients = rec_ing_resp.data
                    
                    if not rec_ingredients:
                        st.warning("Cette recette ne contient encore aucun ingrédient.")
                    else:
                        for item in rec_ingredients:
                            ing_info = item["ingredients"]
                            qty_calculated = round(item["quantity"] * ratio, 2)
                            qty_display = int(qty_calculated) if qty_calculated.is_integer() else qty_calculated
                            
                            tags = []
                            if ing_info.get("exclude_from_list"):
                                tags.append("Fond de placard")
                            if ing_info.get("is_recurrent"):
                                tags.append("Récurrent")
                            
                            tag_str = f" *({', '.join(tags)})*" if tags else ""
                            st.write(f"• **{ing_info['name']}** : {qty_display} {ing_info['unit']}{tag_str}")
                
                st.markdown("---")
                st.subheader("📝 Instructions de préparation")
                if recipe["instructions"]:
                    st.write(recipe["instructions"])
                else:
                    st.info("Aucune instruction renseignée pour cette recette.")
                    
        except Exception as e:
            st.error(f"Erreur de chargement des recettes : {e}")

    with subtab_edit:
        col_create, col_manage = st.columns([1, 2])
        
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

                    with st.expander("📋 Dupliquer cette recette"):
                        dup_name = st.text_input("Nom de la copie", value=f"{target_recipe['name']} (Copie)")
                        if st.button("Dupliquer maintenant", key="btn_dup_recipe"):
                            if not dup_name.strip():
                                st.error("Le nom ne peut pas être vide.")
                            else:
                                try:
                                    new_rec_resp = supabase.table("recipes").insert({
                                        "name": dup_name.strip().capitalize(),
                                        "base_servings": target_recipe["base_servings"],
                                        "instructions": target_recipe["instructions"]
                                    }).execute()
                                    
                                    new_recipe_id = new_rec_resp.data[0]["id"]
                                    
                                    orig_ing_resp = supabase.table("recipe_ingredients")\
                                        .select("ingredient_id, quantity")\
                                        .eq("recipe_id", target_recipe["id"]).execute()
                                    
                                    orig_ings = orig_ing_resp.data
                                    
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
                        .select("id, quantity, ingredient_id, ingredients(name, unit, exclude_from_list, is_recurrent)")\
                        .eq("recipe_id", target_recipe["id"]).execute()
                    
                    curr_ingredients = curr_ing_resp.data
                    
                    if curr_ingredients:
                        for c_ing in curr_ingredients:
                            c_col1, c_col2, c_col3 = st.columns([3, 2, 1])
                            
                            tags = []
                            if c_ing['ingredients'].get('exclude_from_list'):
                                tags.append("Fond de placard")
                            if c_ing['ingredients'].get('is_recurrent'):
                                tags.append("Récurrent")
                            
                            tag_str = f" *({', '.join(tags)})*" if tags else ""
                            c_col1.write(f"• **{c_ing['ingredients']['name']}**{tag_str}")
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
# ONGLET 3 : MENUS ET LISTE DE COURSES
# ==========================================
with tab_menus:
    st.header("Planification des repas & Liste de courses")
    
    col_plan, col_list = st.columns([1, 1])
    
    # --- COLONNE GAUCHE : PLANIFICATION ---
    with col_plan:
        st.subheader("📅 Planifier un repas")
        
        try:
            recipes_resp = supabase.table("recipes").select("*").order("name").execute()
            all_recipes = recipes_resp.data
            
            if not all_recipes:
                st.warning("Veuillez d'abord créer des recettes dans l'onglet 'Recettes'.")
            else:
                recipe_map = {r["name"]: r for r in all_recipes}
                
                with st.form("form_add_meal"):
                    p_day = st.selectbox("Jour de la semaine", JOURS)
                    p_meal = st.selectbox("Repas", REPAS)
                    p_recipe_name = st.selectbox("Recette", list(recipe_map.keys()))
                    selected_rec = recipe_map[p_recipe_name]
                    p_servings = st.number_input("Nombre de convives", min_value=1, value=selected_rec["base_servings"], step=1)
                    
                    if st.form_submit_button("➕ Ajouter au planning"):
                        supabase.table("planned_meals").insert({
                            "day": p_day,
                            "meal_type": p_meal,
                            "recipe_id": selected_rec["id"],
                            "servings": p_servings
                        }).execute()
                        st.success(f"Repas ajouté pour le {p_day} ({p_meal}) !")
                        st.rerun()

        except Exception as e:
            st.error(f"Erreur lors du chargement : {e}")
            
        st.markdown("---")
        st.subheader("📋 Planning actuel de la semaine")
        
        try:
            planned_resp = supabase.table("planned_meals").select("*").execute()
            planned_meals = planned_resp.data or []
            
            recipes_dict = {r["id"]: r for r in (all_recipes if 'all_recipes' in locals() else [])}
            
            if not planned_meals:
                st.info("Aucun repas planifié pour le moment.")
            else:
                for pm in planned_meals:
                    rec_name = recipes_dict.get(pm["recipe_id"], {}).get("name", "Recette inconnue")
                    p_col1, p_col2 = st.columns([4, 1])
                    p_col1.write(f"• **{pm['day']} ({pm['meal_type']})** : {rec_name} *({pm['servings']} pers.)*")
                    if p_col2.button("❌", key=f"del_pm_{pm['id']}"):
                        supabase.table("planned_meals").delete().eq("id", pm["id"]).execute()
                        st.rerun()
                        
                st.markdown(" ")
                if st.button("🗑️ Vider tout le planning de la semaine", type="primary"):
                    supabase.table("planned_meals").delete().neq("id", 0).execute()
                    st.success("Planning réinitialisé !")
                    st.rerun()
                    
        except Exception as e:
            st.error(f"Erreur : {e}")

    # --- COLONNE DROITE : LISTE DE COURSES AUTOMATIQUE ---
    with col_list:
        st.subheader("🛒 Liste de courses agrégée")
        
        try:
            # Récupération de tous les ingrédients & jointures
            all_ing_resp = supabase.table("ingredients").select("*").execute()
            ingredients_dict = {i["id"]: i for i in (all_ing_resp.data or [])}
            
            rec_ing_resp = supabase.table("recipe_ingredients").select("*").execute()
            recipe_ingredients_list = rec_ing_resp.data or []
            
            # Calcul de l'agrégation
            aggregated = {}
            for pm in planned_meals:
                rec_id = pm["recipe_id"]
                p_servings = pm["servings"]
                rec = recipes_dict.get(rec_id)
                if not rec:
                    continue
                
                base_servings = rec["base_servings"]
                ratio = p_servings / base_servings if base_servings > 0 else 1.0
                
                # Ingrédients de cette recette
                matching_ings = [ri for ri in recipe_ingredients_list if ri["recipe_id"] == rec_id]
                
                for ri in matching_ings:
                    ing_id = ri["ingredient_id"]
                    ing_info = ingredients_dict.get(ing_id)
                    
                    if not ing_info:
                        continue
                    # Filtre : exclure les fonds de placard
                    if ing_info.get("exclude_from_list"):
                        continue
                        
                    qty = ri["quantity"] * ratio
                    
                    if ing_id not in aggregated:
                        aggregated[ing_id] = {
                            "name": ing_info["name"],
                            "qty": 0.0,
                            "unit": ing_info["unit"],
                            "category": ing_info.get("category") or "Autre"
                        }
                    aggregated[ing_id]["qty"] += qty

            # Produits récurrents
            recurrent_items = [ing for ing in ingredients_dict.values() if ing.get("is_recurrent")]

            # Affichage de la liste de courses par rayon
            if not aggregated:
                st.info("Ajoutez des repas au planning pour générer la liste de courses.")
            else:
                # Regroupement par rayon
                by_category = {}
                for item in aggregated.values():
                    cat = item["category"]
                    by_category.setdefault(cat, []).append(item)
                    
                for rayon in RAYONS:
                    if rayon in by_category:
                        st.markdown(f"##### 🏷️ {rayon}")
                        for item in by_category[rayon]:
                            qty = round(item["qty"], 2)
                            qty_disp = int(qty) if isinstance(qty, float) and qty.is_integer() else qty
                            st.checkbox(f"**{item['name']}** : {qty_disp} {item['unit']}", key=f"chk_agg_{item['name']}")

            # Bloc Produits récurrents
            st.markdown("---")
            st.subheader("🔁 Produits récurrents à vérifier")
            if not recurrent_items:
                st.caption("Aucun produit récurrent configuré. (Cochez 'Produit récurrent' dans le 1er onglet).")
            else:
                for rec_item in recurrent_items:
                    st.checkbox(f"{rec_item['name']} *({rec_item['category']})*", key=f"chk_rec_{rec_item['id']}")

            # Bouton d'export PDF A4
            st.markdown("---")
            st.subheader("📄 Export de la fiche A4")
            
            if st.button("🚀 Générer la fiche A4 (Menu + Liste + Produits récurrents)"):
                pdf_bytes = generate_pdf(planned_meals, aggregated, recurrent_items, recipes_dict)
                st.download_button(
                    label="📥 Télécharger le PDF A4 Imprimable",
                    data=pdf_bytes,
                    file_name="Menu_et_Liste_de_Courses.pdf",
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Erreur lors du calcul de la liste : {e}")
