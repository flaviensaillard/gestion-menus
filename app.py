import streamlit as st
from supabase import create_client, Client
from fpdf import FPDF
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict

# ------------------------------
# CONFIGURATION DE LA PAGE
# ------------------------------
st.set_page_config(
    page_title="Gestionnaire de Menus",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ------------------------------
# CONSTANTES
# ------------------------------
UNITES = ["g", "kg", "ml", "cl", "l", "unité", "c. à soupe", "c. à café",
          "pincée", "sachet", "gousse", "tranche", "boîte"]
RAYONS = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers",
          "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
REPAS = ["Midi", "Soir"]

# ------------------------------
# CONNEXION SUPABASE
# ------------------------------
@st.cache_resource(ttl=3600)
def init_supabase() -> Optional[Client]:
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        client.table("ingredients").select("id").limit(1).execute()
        return client
    except Exception as e:
        st.error(f"❌ Connexion Supabase impossible : {e}")
        return None

supabase = init_supabase()

# ------------------------------
# CHARGEMENT DES DONNÉES
# ------------------------------
def load_data() -> Dict[str, List]:
    """Charge les données depuis Supabase."""
    if not supabase:
        return {}
    
    data = {}
    try:
        for table in ["ingredients", "recipes", "recipe_ingredients", "planned_meals"]:
            resp = supabase.table(table).select("*").execute()
            data[table] = resp.data if resp.data else []
    except Exception as e:
        st.error(f"Erreur de chargement : {e}")
    return data

def refresh_data():
    """Recharge les données et rafraîchit la page."""
    st.session_state.data = load_data()
    st.rerun()

# ------------------------------
# FONCTIONS UTILITAIRES
# ------------------------------
def clean_pdf_str(text: Any) -> str:
    """Nettoie les chaînes pour FPDF (supprime les emojis et caractères spéciaux)."""
    if not text:
        return ""
    # Remplacer les caractères problématiques
    replacements = {
        '✂️': '-',
        '🍽️': '',
        '📖': '',
        '📝': '',
        '🛒': '',
        '•': '-',
        'é': 'e',
        'è': 'e',
        'ê': 'e',
        'à': 'a',
        'ç': 'c',
        'ù': 'u',
        'ô': 'o',
        'î': 'i',
        'ï': 'i',
        'É': 'E',
        'È': 'E',
        'Ê': 'E',
        'À': 'A',
        'Ç': 'C',
        'Ù': 'U',
        'Ô': 'O',
        'Î': 'I',
        'Ï': 'I',
        '€': 'EUR',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
    }
    
    result = str(text)
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    # Encodage Latin-1 avec remplacement des caractères non supportés
    return result.encode('latin-1', 'replace').decode('latin-1')

def format_quantity(qty: float) -> str:
    """Formate les quantités proprement."""
    if isinstance(qty, float) and qty.is_integer():
        return str(int(qty))
    return f"{qty:.2f}".rstrip('0').rstrip('.')

# ------------------------------
# GÉNÉRATION PDF
# ------------------------------
def generate_pdf(planned_meals: List[Dict], aggregated_items: Dict,
                 recurrent_items: List[Dict], recipes_dict: Dict) -> bytes:
    """Génère un PDF A4 avec le menu et la liste de courses."""
    try:
        pdf = FPDF(format='A4', unit='mm')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # En-tête
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 15, clean_pdf_str('Menu de la Semaine'), ln=True, align='C')
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 5, clean_pdf_str(f'Généré le {datetime.now().strftime("%d/%m/%Y")}'), ln=True, align='C')
        pdf.ln(5)

        # Planning
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, '1. Planning des Repas', ln=True, fill=True)
        pdf.ln(3)

        schedule = {d: {"Midi": "-", "Soir": "-"} for d in JOURS}
        for pm in planned_meals:
            rec_name = recipes_dict.get(pm.get('recipe_id'), {}).get('name', 'Inconnu')
            serv = pm.get('servings', 1)
            d = pm.get('day')
            m = pm.get('meal_type')
            if d in schedule and m in schedule[d]:
                schedule[d][m] = f"{rec_name} ({serv}p)"

        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(30, 8, clean_pdf_str('Jour'), border=1, fill=True)
        pdf.cell(80, 8, clean_pdf_str('Midi'), border=1, fill=True)
        pdf.cell(80, 8, clean_pdf_str('Soir'), border=1, ln=True, fill=True)

        pdf.set_font('Helvetica', size=9)
        for i, day in enumerate(JOURS):
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 250)
            else:
                pdf.set_fill_color(240, 240, 240)
            pdf.cell(30, 7, clean_pdf_str(day), border=1, fill=True)
            pdf.cell(80, 7, clean_pdf_str(schedule[day]['Midi'])[:50], border=1, fill=True)
            pdf.cell(80, 7, clean_pdf_str(schedule[day]['Soir'])[:50], border=1, ln=True, fill=True)

        pdf.ln(8)
        # Ligne de découpe simple
        pdf.set_dash_pattern(dash=2, gap=2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.set_dash_pattern()
        pdf.set_font('Helvetica', 'I', 8)
        pdf.cell(0, 5, clean_pdf_str('- - - - - - - - - - Decouper ici - - - - - - - - - -'), ln=True, align='C')
        pdf.ln(8)

        # Liste de courses
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, '2. Liste de Courses', ln=True, fill=True)
        pdf.ln(3)

        by_cat = defaultdict(list)
        for item in aggregated_items.values():
            by_cat[item.get('category', 'Autre')].append(item)

        if not by_cat:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 5, 'Aucun article a acheter.', ln=True)
        else:
            for cat in RAYONS:
                if cat in by_cat:
                    pdf.set_font('Helvetica', 'B', 11)
                    pdf.set_fill_color(230, 230, 230)
                    pdf.cell(0, 7, clean_pdf_str(f'- {cat}'), ln=True, fill=True)
                    pdf.set_font('Helvetica', size=9)
                    for it in by_cat[cat]:
                        qty_str = format_quantity(it['qty'])
                        line = f"   [  ] {it['name']} : {qty_str} {it['unit']}"
                        pdf.cell(0, 5, clean_pdf_str(line), ln=True)
                    pdf.ln(2)

        # Produits récurrents
        if recurrent_items:
            pdf.ln(5)
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 10, '3. Produits recurrents', ln=True, fill=True)
            pdf.ln(3)
            pdf.set_font('Helvetica', size=9)
            col_width = 90
            for i, rec in enumerate(recurrent_items):
                txt = clean_pdf_str(f"[  ] {rec['name']} ({rec.get('category', 'Autre')})")
                pdf.cell(col_width, 5, txt)
                if (i + 1) % 2 == 0:
                    pdf.ln()
            if len(recurrent_items) % 2 != 0:
                pdf.ln()

        return bytes(pdf.output())
    
    except Exception as e:
        st.error(f"Erreur lors de la génération du PDF : {e}")
        return b""

# ------------------------------
# INTERFACE PRINCIPALE
# ------------------------------
def main():
    if not supabase:
        st.error("🚫 Application non fonctionnelle.")
        st.stop()

    st.title("🍽️ Mon Gestionnaire de Menus")
    st.markdown("---")

    # Chargement initial des données
    if 'data' not in st.session_state:
        st.session_state.data = load_data()

    tab_ingredients, tab_recettes, tab_menus = st.tabs([
        "🥕 Ingrédients", "📖 Recettes", "📅 Menus & Courses"
    ])

    # ============================
    # ONGLET INGRÉDIENTS
    # ============================
    with tab_ingredients:
        st.header("Ingrédients")

        # Bouton pour afficher le formulaire d'ajout
        if st.button("➕ Ajouter un ingrédient", key="btn_show_add_ing", use_container_width=True):
            st.session_state.show_add_ing = True

        # Formulaire d'ajout
        if st.session_state.get('show_add_ing', False):
            with st.form("add_ingredient_form"):
                st.subheader("Nouvel ingrédient")
                name = st.text_input("Nom *", key="new_ing_name")
                col1, col2 = st.columns(2)
                unit = col1.selectbox("Unité", UNITES, key="new_ing_unit")
                category = col2.selectbox("Rayon", RAYONS, key="new_ing_category")
                col3, col4 = st.columns(2)
                exclude = col3.checkbox("🚪 Fond de placard", key="new_ing_exclude")
                recurrent = col4.checkbox("🔁 Récurrent", key="new_ing_recurrent")
                
                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submitted = st.form_submit_button("Enregistrer", use_container_width=True)
                with col_cancel:
                    cancelled = st.form_submit_button("Annuler", use_container_width=True)
                
                if submitted:
                    if not name.strip():
                        st.error("Nom obligatoire")
                    else:
                        try:
                            supabase.table("ingredients").insert({
                                "name": name.strip().capitalize(),
                                "unit": unit,
                                "category": category,
                                "exclude_from_list": exclude,
                                "is_recurrent": recurrent
                            }).execute()
                            st.session_state.show_add_ing = False
                            refresh_data()
                        except Exception as e:
                            st.error(f"Erreur : {e}")
                
                if cancelled:
                    st.session_state.show_add_ing = False
                    st.rerun()

        # Affichage des ingrédients
        ingredients = st.session_state.data.get('ingredients', [])
        
        if ingredients:
            # Affichage en tableau
            df_display = pd.DataFrame(ingredients)[['name', 'unit', 'category', 'exclude_from_list', 'is_recurrent']]
            st.dataframe(
                df_display,
                column_config={
                    "name": "Nom",
                    "unit": "Unité",
                    "category": "Rayon",
                    "exclude_from_list": st.column_config.CheckboxColumn("Fond de placard"),
                    "is_recurrent": st.column_config.CheckboxColumn("Récurrent")
                },
                hide_index=True,
                use_container_width=True
            )
            
            # Modification d'un ingrédient
            with st.expander("✏️ Modifier un ingrédient"):
                ing_names = [i['name'] for i in ingredients]
                selected_ing_name = st.selectbox(
                    "Sélectionner", 
                    ing_names,
                    key="select_ing_to_edit"
                )
                selected_ing = next((i for i in ingredients if i['name'] == selected_ing_name), None)
                
                if selected_ing:
                    with st.form(f"edit_ing_form_{selected_ing['id']}"):
                        col1, col2 = st.columns(2)
                        new_unit = col1.selectbox(
                            "Unité", 
                            UNITES,
                            index=UNITES.index(selected_ing['unit']) if selected_ing['unit'] in UNITES else 0,
                            key=f"edit_unit_{selected_ing['id']}"
                        )
                        new_category = col2.selectbox(
                            "Rayon", 
                            RAYONS,
                            index=RAYONS.index(selected_ing['category']) if selected_ing['category'] in RAYONS else 0,
                            key=f"edit_cat_{selected_ing['id']}"
                        )
                        col3, col4 = st.columns(2)
                        new_exclude = col3.checkbox(
                            "🚪 Fond de placard", 
                            value=selected_ing.get('exclude_from_list', False),
                            key=f"edit_exclude_{selected_ing['id']}"
                        )
                        new_recurrent = col4.checkbox(
                            "🔁 Récurrent", 
                            value=selected_ing.get('is_recurrent', False),
                            key=f"edit_recurrent_{selected_ing['id']}"
                        )
                        
                        col_save, col_del = st.columns(2)
                        with col_save:
                            save_clicked = st.form_submit_button("💾 Sauvegarder", use_container_width=True)
                        with col_del:
                            delete_clicked = st.form_submit_button("🗑️ Supprimer", use_container_width=True)
                        
                        if save_clicked:
                            try:
                                supabase.table("ingredients").update({
                                    "unit": new_unit,
                                    "category": new_category,
                                    "exclude_from_list": new_exclude,
                                    "is_recurrent": new_recurrent
                                }).eq("id", selected_ing['id']).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                        
                        if delete_clicked:
                            try:
                                supabase.table("ingredients").delete().eq("id", selected_ing['id']).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
        else:
            st.info("Aucun ingrédient pour le moment.")

    # ============================
    # ONGLET RECETTES
    # ============================
    with tab_recettes:
        st.header("Recettes")

        # Données
        recipes = st.session_state.data.get('recipes', [])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = st.session_state.data.get('ingredients', [])

        # Bouton nouvelle recette
        if st.button("➕ Nouvelle recette", key="btn_show_add_recipe", use_container_width=True):
            st.session_state.show_add_recipe = True

        # Formulaire nouvelle recette
        if st.session_state.get('show_add_recipe', False):
            with st.form("add_recipe_form"):
                st.subheader("Créer une recette")
                name = st.text_input("Nom *", key="new_recipe_name")
                servings = st.number_input("Personnes", min_value=1, value=4, key="new_recipe_servings")
                instructions = st.text_area("Instructions", height=100, key="new_recipe_instructions")
                
                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submitted = st.form_submit_button("Créer", use_container_width=True)
                with col_cancel:
                    cancelled = st.form_submit_button("Annuler", use_container_width=True)
                
                if submitted:
                    if not name.strip():
                        st.error("Nom obligatoire")
                    else:
                        try:
                            supabase.table("recipes").insert({
                                "name": name.strip().capitalize(),
                                "base_servings": servings,
                                "instructions": instructions
                            }).execute()
                            st.session_state.show_add_recipe = False
                            refresh_data()
                        except Exception as e:
                            st.error(f"Erreur : {e}")
                
                if cancelled:
                    st.session_state.show_add_recipe = False
                    st.rerun()

        if not recipes:
            st.info("Aucune recette disponible.")
        else:
            # Sélection d'une recette
            recipe_names = [r['name'] for r in recipes]
            selected_name = st.selectbox(
                "Choisir une recette", 
                recipe_names,
                key="selected_recipe"
            )
            recipe = next((r for r in recipes if r['name'] == selected_name), None)

            if recipe:
                st.markdown("---")
                
                # En-tête avec actions
                col_info, col_actions = st.columns([3, 2])
                with col_info:
                    st.subheader(f"📖 {recipe['name']}")
                    base_servings = recipe.get('base_servings', 4)
                    target_servings = st.number_input(
                        "Personnes", 
                        min_value=1, 
                        max_value=50, 
                        value=base_servings,
                        key=f"servings_{recipe['id']}"
                    )
                    ratio = target_servings / base_servings
                
                with col_actions:
                    st.write("")
                    st.write("")
                    col_dup, col_del = st.columns(2)
                    with col_dup:
                        if st.button("📋 Dupliquer", key=f"dup_{recipe['id']}", use_container_width=True):
                            try:
                                new_name = f"{recipe['name']} (copie)"
                                new_rec = supabase.table("recipes").insert({
                                    "name": new_name,
                                    "base_servings": recipe['base_servings'],
                                    "instructions": recipe.get('instructions', '')
                                }).execute()
                                new_id = new_rec.data[0]['id']
                                
                                orig_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                                for ri in orig_ings:
                                    supabase.table("recipe_ingredients").insert({
                                        "recipe_id": new_id,
                                        "ingredient_id": ri['ingredient_id'],
                                        "quantity": ri['quantity']
                                    }).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                    with col_del:
                        if st.button("🗑️ Supprimer", key=f"del_{recipe['id']}", use_container_width=True):
                            try:
                                supabase.table("recipes").delete().eq("id", recipe['id']).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")

                # Ingrédients de la recette
                st.markdown("#### 🛒 Ingrédients")
                rec_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                
                if rec_ings:
                    for ri in rec_ings:
                        ing = next((i for i in ingredients if i['id'] == ri['ingredient_id']), None)
                        if ing:
                            qty = ri['quantity'] * ratio
                            qty_str = format_quantity(qty)
                            
                            col1, col2, col3 = st.columns([4, 2, 1])
                            col1.write(f"**{ing['name']}**")
                            col2.write(f"{qty_str} {ing['unit']}")
                            if col3.button("❌", key=f"del_ri_{ri['id']}", help="Retirer cet ingrédient"):
                                try:
                                    supabase.table("recipe_ingredients").delete().eq("id", ri['id']).execute()
                                    refresh_data()
                                except Exception as e:
                                    st.error(f"Erreur : {e}")
                else:
                    st.info("Aucun ingrédient ajouté.")

                # Ajout d'un ingrédient
                st.markdown("#### ➕ Ajouter un ingrédient")
                existing_ings = [ri['ingredient_id'] for ri in rec_ings]
                available_ings = [i for i in ingredients if i['id'] not in existing_ings]
                
                if available_ings:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        ing_options = {i['name']: i for i in available_ings}
                        selected_ing_name = st.selectbox(
                            "Ingrédient", 
                            list(ing_options.keys()),
                            key=f"select_add_ing_{recipe['id']}"
                        )
                    with col2:
                        qty = st.number_input(
                            "Quantité", 
                            min_value=0.1, 
                            value=100.0, 
                            step=10.0,
                            key=f"qty_add_ing_{recipe['id']}"
                        )
                    with col3:
                        st.write("")
                        st.write("")
                        if st.button("➕", key=f"btn_add_ing_{recipe['id']}", use_container_width=True):
                            try:
                                ing_obj = ing_options[selected_ing_name]
                                supabase.table("recipe_ingredients").insert({
                                    "recipe_id": recipe['id'],
                                    "ingredient_id": ing_obj['id'],
                                    "quantity": qty
                                }).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                else:
                    st.info("Tous les ingrédients sont déjà dans la recette.")

                # Instructions
                st.markdown("#### 📝 Instructions")
                if recipe.get('instructions'):
                    st.write(recipe['instructions'])
                else:
                    st.info("Aucune instruction.")

                # Modification
                with st.expander("✏️ Modifier la recette"):
                    with st.form(f"edit_recipe_form_{recipe['id']}"):
                        new_name = st.text_input("Nom", value=recipe['name'], key=f"edit_rname_{recipe['id']}")
                        new_servings = st.number_input(
                            "Personnes de base", 
                            min_value=1,
                            value=recipe.get('base_servings', 4),
                            key=f"edit_rservings_{recipe['id']}"
                        )
                        new_instructions = st.text_area(
                            "Instructions", 
                            value=recipe.get('instructions', ''),
                            height=150,
                            key=f"edit_rinstructions_{recipe['id']}"
                        )
                        if st.form_submit_button("💾 Sauvegarder", use_container_width=True):
                            try:
                                supabase.table("recipes").update({
                                    "name": new_name.strip().capitalize(),
                                    "base_servings": new_servings,
                                    "instructions": new_instructions
                                }).eq("id", recipe['id']).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")

    # ============================
    # ONGLET MENUS & COURSES
    # ============================
    with tab_menus:
        st.header("Menus & Liste de courses")

        planned_meals = st.session_state.data.get('planned_meals', [])
        recipes = st.session_state.data.get('recipes', [])
        recipes_dict = {r['id']: r for r in recipes}
        ingredients_dict = {i['id']: i for i in st.session_state.data.get('ingredients', [])}
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])

        col_plan, col_list = st.columns([1, 1])

        # --- PLANIFICATION ---
        with col_plan:
            st.subheader("📅 Planification")

            if not recipes:
                st.warning("Créez d'abord des recettes !")
            else:
                with st.form("add_meal_form"):
                    col_day, col_meal = st.columns(2)
                    day = col_day.selectbox("Jour", JOURS)
                    meal_type = col_meal.selectbox("Repas", REPAS)
                    
                    recipe_names = [r['name'] for r in recipes]
                    recipe_name = st.selectbox("Recette", recipe_names)
                    recipe = next((r for r in recipes if r['name'] == recipe_name), None)
                    
                    servings = st.number_input(
                        "Convives", 
                        min_value=1, 
                        value=recipe.get('base_servings', 4) if recipe else 4
                    )
                    
                    if st.form_submit_button("➕ Ajouter au planning", use_container_width=True):
                        if recipe:
                            try:
                                supabase.table("planned_meals").insert({
                                    "day": day,
                                    "meal_type": meal_type,
                                    "recipe_id": recipe['id'],
                                    "servings": servings
                                }).execute()
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")

            # Affichage du planning
            st.markdown("---")
            if not planned_meals:
                st.info("Aucun repas planifié.")
            else:
                by_day = defaultdict(list)
                for pm in planned_meals:
                    by_day[pm['day']].append(pm)

                for day in JOURS:
                    if day in by_day:
                        st.markdown(f"**{day}**")
                        for pm in by_day[day]:
                            rec_name = recipes_dict.get(pm['recipe_id'], {}).get('name', 'Inconnu')
                            col1, col2 = st.columns([5, 1])
                            col1.write(f"• {pm['meal_type']} : {rec_name} ({pm['servings']} pers.)")
                            if col2.button("❌", key=f"del_pm_{pm['id']}"):
                                try:
                                    supabase.table("planned_meals").delete().eq("id", pm['id']).execute()
                                    refresh_data()
                                except Exception as e:
                                    st.error(f"Erreur : {e}")

                if st.button("🗑️ Vider le planning", key="clear_planning", use_container_width=True):
                    try:
                        supabase.table("planned_meals").delete().neq("id", 0).execute()
                        refresh_data()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

        # --- LISTE DE COURSES ---
        with col_list:
            st.subheader("🛒 Liste de courses")

            # Agrégation
            aggregated = {}
            for pm in planned_meals:
                rec = recipes_dict.get(pm['recipe_id'])
                if not rec:
                    continue
                ratio = pm['servings'] / rec.get('base_servings', 1)
                for ri in recipe_ings:
                    if ri['recipe_id'] == pm['recipe_id']:
                        ing = ingredients_dict.get(ri['ingredient_id'])
                        if not ing or ing.get('exclude_from_list'):
                            continue
                        qty = ri['quantity'] * ratio
                        if ing['id'] not in aggregated:
                            aggregated[ing['id']] = {
                                "name": ing['name'],
                                "qty": 0,
                                "unit": ing['unit'],
                                "category": ing.get('category', 'Autre')
                            }
                        aggregated[ing['id']]['qty'] += qty

            if not aggregated:
                st.info("Ajoutez des repas pour générer la liste.")
            else:
                by_cat = defaultdict(list)
                for item in aggregated.values():
                    by_cat[item['category']].append(item)

                for rayon in RAYONS:
                    if rayon in by_cat:
                        st.markdown(f"**{rayon}**")
                        for item in by_cat[rayon]:
                            qty_str = format_quantity(item['qty'])
                            st.checkbox(
                                f"{item['name']} : {qty_str} {item['unit']}",
                                key=f"shop_{item['name']}_{rayon}"
                            )

            # Produits récurrents
            st.markdown("---")
            st.subheader("🔁 Produits récurrents")
            recurrent = [i for i in ingredients_dict.values() if i.get('is_recurrent')]
            if recurrent:
                for item in recurrent:
                    st.checkbox(
                        f"{item['name']} ({item.get('category', 'Autre')})",
                        key=f"rec_{item['id']}"
                    )
            else:
                st.caption("Aucun produit récurrent.")

            # Export PDF
            st.markdown("---")
            if st.button("📄 Générer le PDF", key="generate_pdf_btn", use_container_width=True):
                pdf_bytes = generate_pdf(planned_meals, aggregated, recurrent, recipes_dict)
                if pdf_bytes:
                    st.download_button(
                        "📥 Télécharger le PDF",
                        data=pdf_bytes,
                        file_name=f"menu_semaine_{datetime.now().strftime('%Y%m%d')}.pdf",
                        mime="application/pdf",
                        key="download_pdf_btn",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()
