import streamlit as st
from supabase import create_client, Client
from fpdf import FPDF
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import re

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

# Mapping des jours en français
JOURS_FR = {
    'Monday': 'Lundi',
    'Tuesday': 'Mardi',
    'Wednesday': 'Mercredi',
    'Thursday': 'Jeudi',
    'Friday': 'Vendredi',
    'Saturday': 'Samedi',
    'Sunday': 'Dimanche'
}

# Mapping des repas
REPAS_LABELS = {
    'Midi': 'Déjeuner',
    'Soir': 'Dîner'
}

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
    
    replacements = {
        '✂️': '-', '🍽️': '', '📖': '', '📝': '', '🛒': '', '•': '-',
        'é': 'e', 'è': 'e', 'ê': 'e', 'à': 'a', 'ç': 'c', 'ù': 'u',
        'ô': 'o', 'î': 'i', 'ï': 'i', 'É': 'E', 'È': 'E', 'Ê': 'E',
        'À': 'A', 'Ç': 'C', 'Ù': 'U', 'Ô': 'O', 'Î': 'I', 'Ï': 'I',
        '€': 'EUR', '"': '"', '"': '"', ''': "'", ''': "'",
    }
    
    result = str(text)
    for old, new in replacements.items():
        result = result.replace(old, new)
    
    return result.encode('latin-1', 'replace').decode('latin-1')

def format_quantity(qty: float) -> str:
    """Formate les quantités proprement."""
    if isinstance(qty, float) and qty.is_integer():
        return str(int(qty))
    return f"{qty:.2f}".rstrip('0').rstrip('.')

def instructions_to_text(instructions_list: List[str]) -> str:
    """Convertit une liste d'instructions en texte avec numérotation."""
    if not instructions_list:
        return ""
    return "\n".join([f"{i+1}. {instr}" for i, instr in enumerate(instructions_list) if instr.strip()])

def text_to_instructions(text: str) -> List[str]:
    """Convertit un texte numéroté en liste d'instructions."""
    if not text:
        return [""]
    
    lines = text.split('\n')
    instructions = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+\.\s*', line)
        if match:
            instructions.append(line[match.end():])
        else:
            instructions.append(line)
    
    return instructions if instructions else [""]

def sort_list_by_name(items: List[Dict]) -> List[Dict]:
    """Trie une liste de dictionnaires par le champ 'name'."""
    return sorted(items, key=lambda x: x.get('name', '').lower())

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
            rec_name = recipes_dict.get(pm.get('recipe_id'), {}).get('name', pm.get('item_name', 'Inconnu'))
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

    # Navigation par onglets (nouvel ordre)
    tab_menus, tab_consulter, tab_editer, tab_ingredients = st.tabs([
        "📅 Menus", 
        "🔍 Consulter", 
        "✏️ Créer / Éditer", 
        "🥕 Ingrédients"
    ])

    # ============================
    # ONGLET 1 : MENUS
    # ============================
    with tab_menus:
        st.header("Planification des menus")
        
        # Données
        planned_meals = st.session_state.data.get('planned_meals', [])
        recipes = sort_list_by_name(st.session_state.data.get('recipes', []))
        recipes_dict = {r['id']: r for r in recipes}
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))
        
        if not recipes and not ingredients:
            st.warning("Créez d'abord des recettes ou des ingrédients !")
        else:
            # Sélection de la date de début
            col_calendar, col_info = st.columns([1, 3])
            with col_calendar:
                start_date = st.date_input(
                    "Date de début",
                    value=date.today(),
                    key="week_start_date"
                )
            with col_info:
                end_date = start_date + timedelta(days=6)
                st.info(f"📅 Semaine du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}")
            
            st.markdown("---")
            
            # Génération des 7 jours à partir de la date sélectionnée
            week_days = []
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                english_day = current_date.strftime('%A')
                french_day = JOURS_FR.get(english_day, english_day)
                week_days.append({
                    'date': current_date,
                    'day_name': french_day,
                    'day_number': current_date.strftime('%d/%m'),
                    'is_today': current_date == date.today()
                })
            
            # Affichage de la semaine
            for day_info in week_days:
                with st.container():
                    # En-tête du jour
                    if day_info['is_today']:
                        st.markdown(f"### 📍 {day_info['day_name']} {day_info['day_number']} (Aujourd'hui)")
                    else:
                        st.markdown(f"### 📅 {day_info['day_name']} {day_info['day_number']}")
                    
                    # Récupération des repas pour ce jour
                    day_meals = [pm for pm in planned_meals if pm['day'] == day_info['day_name']]
                    
                    # Regrouper les repas par type
                    meals_by_type = defaultdict(list)
                    for meal in day_meals:
                        meals_by_type[meal['meal_type']].append(meal)
                    
                    # Affichage des repas regroupés
                    if day_meals:
                        for meal_type in REPAS:
                            if meal_type in meals_by_type:
                                meals = meals_by_type[meal_type]
                                label = REPAS_LABELS.get(meal_type, meal_type)
                                
                                # Calculer le nombre de personnes
                                servings_list = [meal['servings'] for meal in meals]
                                servings = max(servings_list) if servings_list else 1
                                
                                # Afficher l'en-tête du type de repas
                                st.markdown(f"**{label} ({servings}p) :**")
                                
                                # Afficher chaque item collé
                                for meal in meals:
                                    # Récupérer le nom (recette ou ingrédient)
                                    if meal.get('recipe_id'):
                                        item_name = recipes_dict.get(meal['recipe_id'], {}).get('name', 'Inconnu')
                                    else:
                                        item_name = meal.get('item_name', 'Inconnu')
                                    
                                    col_item, col_del = st.columns([10, 1])
                                    with col_item:
                                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• {item_name}")
                                    with col_del:
                                        if st.button("❌", key=f"del_meal_{meal['id']}", help="Supprimer"):
                                            try:
                                                supabase.table("planned_meals").delete().eq("id", meal['id']).execute()
                                                refresh_data()
                                            except Exception as e:
                                                st.error(f"Erreur : {e}")
                    else:
                        st.caption("Aucun repas planifié")
                    
                    # Ajout d'un repas pour ce jour
                    with st.expander(f"➕ Ajouter", expanded=False):
                        col_type, col_meal_type = st.columns([1, 1])
                        with col_type:
                            # Choix du type d'item
                            item_type = st.radio(
                                "Type",
                                ["Recette", "Ingrédient"],
                                horizontal=True,
                                key=f"item_type_{day_info['day_name']}_{day_info['day_number']}"
                            )
                        with col_meal_type:
                            meal_type = st.selectbox(
                                "Repas",
                                REPAS,
                                format_func=lambda x: REPAS_LABELS.get(x, x),
                                key=f"meal_type_{day_info['day_name']}_{day_info['day_number']}"
                            )
                        
                        col_item, col_servings = st.columns([2, 1])
                        with col_item:
                            if item_type == "Recette":
                                recipe_names = [r['name'] for r in recipes]
                                selected_item = st.selectbox(
                                    "Recette",
                                    recipe_names,
                                    key=f"recipe_{day_info['day_name']}_{day_info['day_number']}"
                                )
                                selected_recipe = next((r for r in recipes if r['name'] == selected_item), None)
                                default_servings = selected_recipe.get('base_servings', 4) if selected_recipe else 4
                            else:
                                ingredient_names = [i['name'] for i in ingredients]
                                selected_item = st.selectbox(
                                    "Ingrédient",
                                    ingredient_names,
                                    key=f"ingredient_{day_info['day_name']}_{day_info['day_number']}"
                                )
                                selected_recipe = None
                                default_servings = 4
                        
                        with col_servings:
                            servings = st.number_input(
                                "Convives",
                                min_value=1,
                                value=default_servings,
                                key=f"servings_{day_info['day_name']}_{day_info['day_number']}"
                            )
                        
                        if st.button("➕ Ajouter", key=f"add_meal_{day_info['day_name']}_{day_info['day_number']}", use_container_width=True):
                            try:
                                if item_type == "Recette" and selected_recipe:
                                    supabase.table("planned_meals").insert({
                                        "day": day_info['day_name'],
                                        "meal_type": meal_type,
                                        "recipe_id": selected_recipe['id'],
                                        "servings": servings
                                    }).execute()
                                else:
                                    supabase.table("planned_meals").insert({
                                        "day": day_info['day_name'],
                                        "meal_type": meal_type,
                                        "item_name": selected_item,
                                        "servings": servings
                                    }).execute()
                                st.success(f"✅ Ajouté pour {day_info['day_name']} !")
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                    
                    st.markdown("---")
            
            # Actions en bas
            st.markdown("---")
            col_export, col_clear = st.columns(2)
            
            with col_export:
                if st.button("📄 Générer la fiche PDF", key="generate_pdf_btn", use_container_width=True):
                    # Calcul de la liste de courses pour le PDF
                    ingredients_dict = {i['id']: i for i in st.session_state.data.get('ingredients', [])}
                    recipe_ings = st.session_state.data.get('recipe_ingredients', [])
                    
                    # Agrégation des ingrédients
                    aggregated = {}
                    for pm in planned_meals:
                        if pm.get('recipe_id'):
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
                        else:
                            # C'est un ingrédient direct
                            item_name = pm.get('item_name')
                            if item_name:
                                ing = next((i for i in ingredients_dict.values() if i['name'] == item_name), None)
                                if ing and not ing.get('exclude_from_list'):
                                    if ing['id'] not in aggregated:
                                        aggregated[ing['id']] = {
                                            "name": ing['name'],
                                            "qty": pm['servings'],
                                            "unit": ing['unit'],
                                            "category": ing.get('category', 'Autre')
                                        }
                                    else:
                                        aggregated[ing['id']]['qty'] += pm['servings']
                    
                    # Produits récurrents
                    recurrent = [i for i in ingredients_dict.values() if i.get('is_recurrent')]
                    
                    pdf_bytes = generate_pdf(planned_meals, aggregated, recurrent, recipes_dict)
                    if pdf_bytes:
                        st.download_button(
                            "📥 Télécharger le PDF",
                            data=pdf_bytes,
                            file_name=f"menu_semaine_{start_date.strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            key="download_pdf_btn",
                            use_container_width=True
                        )
            
            with col_clear:
                if st.button("🗑️ Vider toute la semaine", key="clear_week", use_container_width=True):
                    try:
                        days_to_clear = [d['day_name'] for d in week_days]
                        for day_name in days_to_clear:
                            meals_to_delete = [pm for pm in planned_meals if pm['day'] == day_name]
                            for meal in meals_to_delete:
                                supabase.table("planned_meals").delete().eq("id", meal['id']).execute()
                        st.success("✅ Semaine vidée !")
                        refresh_data()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    # ============================
    # ONGLET 2 : CONSULTER UNE RECETTE
    # ============================
    with tab_consulter:
        st.header("Consulter une recette")
        
        recipes = sort_list_by_name(st.session_state.data.get('recipes', []))
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = st.session_state.data.get('ingredients', [])
        
        if not recipes:
            st.info("Aucune recette disponible. Créez-en une dans l'onglet 'Créer / Éditer'.")
        else:
            # Sélection de la recette
            recipe_names = [r['name'] for r in recipes]
            selected_name = st.selectbox(
                "Choisir une recette", 
                recipe_names,
                key="consult_recipe_select"
            )
            recipe = next((r for r in recipes if r['name'] == selected_name), None)
            
            if recipe:
                st.markdown("---")
                
                # Affichage du nom et sélection du nombre de personnes
                col_title, col_servings = st.columns([2, 1])
                with col_title:
                    st.subheader(f"📖 {recipe['name']}")
                with col_servings:
                    base_servings = recipe.get('base_servings', 4)
                    target_servings = st.number_input(
                        "Nombre de personnes",
                        min_value=1,
                        max_value=50,
                        value=base_servings,
                        step=1,
                        key=f"consult_servings_{recipe['id']}"
                    )
                
                # Calcul du ratio
                ratio = target_servings / base_servings if base_servings > 0 else 1
                
                # Affichage des ingrédients avec quantités ajustées
                st.markdown("### 🛒 Ingrédients")
                
                # Récupération des ingrédients de la recette
                rec_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                
                if rec_ings:
                    for ri in rec_ings:
                        ing = next((i for i in ingredients if i['id'] == ri['ingredient_id']), None)
                        if ing:
                            qty_adjusted = ri['quantity'] * ratio
                            qty_display = format_quantity(qty_adjusted)
                            
                            col1, col2, col3 = st.columns([3, 2, 2])
                            with col1:
                                st.markdown(f"**{ing['name']}**")
                            with col2:
                                st.markdown(f"{qty_display} {ing['unit']}")
                            with col3:
                                st.markdown(f"*{ing.get('category', 'Autre')}*")
                else:
                    st.info("Aucun ingrédient pour cette recette.")
                
                # Affichage des instructions numérotées
                st.markdown("### 📝 Instructions")
                if recipe.get('instructions'):
                    instructions_list = text_to_instructions(recipe['instructions'])
                    for i, instruction in enumerate(instructions_list, 1):
                        if instruction.strip():
                            st.markdown(f"**{i}.** {instruction}")
                else:
                    st.info("Aucune instruction pour cette recette.")

    # ============================
    # ONGLET 3 : CRÉER / ÉDITER UNE RECETTE
    # ============================
    with tab_editer:
        st.header("Créer / Éditer une recette")

        # Données
        recipes = sort_list_by_name(st.session_state.data.get('recipes', []))
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))

        # Mode création ou édition
        mode = st.radio(
            "Mode",
            ["➕ Créer une nouvelle recette", "✏️ Éditer une recette existante"],
            horizontal=True,
            key="recipe_mode"
        )

        st.markdown("---")

        # ==================== MODE CRÉATION ====================
        if mode == "➕ Créer une nouvelle recette":
            col_left, col_right = st.columns([1, 1])
            
            with col_left:
                st.markdown("### 📝 Informations de base")
                
                name = st.text_input("Nom de la recette *", placeholder="ex: Blanquette de veau", key="create_recipe_name")
                servings = st.number_input(
                    "Nombre de personnes", 
                    min_value=1, 
                    value=4,
                    help="Nombre de personnes pour lequel la recette est prévue",
                    key="create_recipe_servings"
                )
                
                st.markdown("### 📝 Instructions")
                
                if 'new_recipe_instructions' not in st.session_state:
                    st.session_state.new_recipe_instructions = [""]
                
                for idx, instruction in enumerate(st.session_state.new_recipe_instructions):
                    col_instr, col_del_instr = st.columns([5, 1])
                    with col_instr:
                        st.text_input(
                            f"Instruction {idx + 1}",
                            value=instruction,
                            key=f"create_instruction_{idx}",
                            placeholder=f"Étape {idx + 1}..."
                        )
                        st.session_state.new_recipe_instructions[idx] = st.session_state[f"create_instruction_{idx}"]
                    with col_del_instr:
                        if len(st.session_state.new_recipe_instructions) > 1:
                            if st.button("❌", key=f"del_create_instruction_{idx}", help="Supprimer cette instruction"):
                                st.session_state.new_recipe_instructions.pop(idx)
                                st.rerun()
                
                if st.button("➕ Nouvelle instruction", key="add_create_instruction", use_container_width=True):
                    st.session_state.new_recipe_instructions.append("")
                    st.rerun()
            
            with col_right:
                st.markdown("### 🛒 Ingrédients de la recette")
                
                if 'new_recipe_ings' not in st.session_state:
                    st.session_state.new_recipe_ings = [
                        {"ingredient": None, "quantity": 100.0, "unit": "g"}
                    ]
                
                if not ingredients:
                    st.warning("Aucun ingrédient disponible. Créez d'abord des ingrédients !")
                else:
                    for idx, row in enumerate(st.session_state.new_recipe_ings):
                        col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 0.5])
                        
                        with col1:
                            ing_names = [i['name'] for i in ingredients]
                            already_selected = [
                                r['ingredient'] for i, r in enumerate(st.session_state.new_recipe_ings) 
                                if i != idx and r['ingredient']
                            ]
                            available_for_this_row = [n for n in ing_names if n not in already_selected]
                            
                            if row['ingredient'] and row['ingredient'] in available_for_this_row:
                                current_index = available_for_this_row.index(row['ingredient'])
                            elif row['ingredient']:
                                available_for_this_row.insert(0, row['ingredient'])
                                current_index = 0
                            else:
                                current_index = 0
                            
                            selected_ing = st.selectbox(
                                "Ingrédient",
                                available_for_this_row,
                                index=current_index,
                                key=f"create_ing_select_{idx}",
                                label_visibility="collapsed"
                            )
                            st.session_state.new_recipe_ings[idx]['ingredient'] = selected_ing
                        
                        with col2:
                            qty = st.number_input(
                                "Quantité",
                                min_value=0.1,
                                value=float(row['quantity']),
                                step=10.0,
                                key=f"create_ing_qty_{idx}",
                                label_visibility="collapsed"
                            )
                            st.session_state.new_recipe_ings[idx]['quantity'] = qty
                        
                        with col3:
                            if selected_ing:
                                ing_obj = next((i for i in ingredients if i['name'] == selected_ing), None)
                                default_unit = ing_obj['unit'] if ing_obj else "g"
                            else:
                                default_unit = row.get('unit', 'g')
                            
                            unit_index = UNITES.index(default_unit) if default_unit in UNITES else 0
                            selected_unit = st.selectbox(
                                "Unité",
                                UNITES,
                                index=unit_index,
                                key=f"create_ing_unit_{idx}",
                                label_visibility="collapsed"
                            )
                            st.session_state.new_recipe_ings[idx]['unit'] = selected_unit
                        
                        with col4:
                            if len(st.session_state.new_recipe_ings) > 1:
                                if st.button("❌", key=f"remove_create_ing_{idx}", help="Supprimer cette ligne"):
                                    st.session_state.new_recipe_ings.pop(idx)
                                    st.rerun()
                    
                    if st.button("➕ Nouvelle ligne", key="add_create_ing_row", use_container_width=True):
                        st.session_state.new_recipe_ings.append(
                            {"ingredient": None, "quantity": 100.0, "unit": "g"}
                        )
                        st.rerun()
            
            st.markdown("---")
            if st.button("✅ Créer la recette", key="create_recipe_btn", use_container_width=True, type="primary"):
                if not name.strip():
                    st.error("Le nom est obligatoire")
                else:
                    try:
                        instructions_text = instructions_to_text(st.session_state.new_recipe_instructions)
                        
                        result = supabase.table("recipes").insert({
                            "name": name.strip().capitalize(),
                            "base_servings": servings,
                            "instructions": instructions_text
                        }).execute()
                        
                        if result.data:
                            new_recipe_id = result.data[0]['id']
                            
                            added_count = 0
                            for new_ing in st.session_state.new_recipe_ings:
                                if new_ing['ingredient']:
                                    ing_obj = next(
                                        (i for i in ingredients if i['name'] == new_ing['ingredient']),
                                        None
                                    )
                                    if ing_obj:
                                        supabase.table("recipe_ingredients").insert({
                                            "recipe_id": new_recipe_id,
                                            "ingredient_id": ing_obj['id'],
                                            "quantity": new_ing['quantity']
                                        }).execute()
                                        added_count += 1
                            
                            success_msg = f"✅ Recette '{name}' créée avec {added_count} ingrédient(s) !"
                            if added_count == 0:
                                success_msg += "\n💡 Vous pourrez ajouter des ingrédients plus tard dans le mode 'Éditer'."
                            st.success(success_msg)
                            
                            st.session_state.new_recipe_ings = [
                                {"ingredient": None, "quantity": 100.0, "unit": "g"}
                            ]
                            st.session_state.new_recipe_instructions = [""]
                            refresh_data()
                        else:
                            st.error("Erreur lors de la création")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

        # ==================== MODE ÉDITION ====================
        else:
            if not recipes:
                st.info("Aucune recette à éditer. Créez-en une d'abord !")
            else:
                recipe_names = [r['name'] for r in recipes]
                selected_name = st.selectbox(
                    "Recette à modifier", 
                    recipe_names,
                    key="edit_recipe_select"
                )
                recipe = next((r for r in recipes if r['name'] == selected_name), None)
                
                if recipe:
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
                                st.success("✅ Recette dupliquée !")
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                    
                    with col_del:
                        if st.button("🗑️ Supprimer", key=f"del_{recipe['id']}", use_container_width=True):
                            try:
                                supabase.table("recipes").delete().eq("id", recipe['id']).execute()
                                st.success("✅ Recette supprimée !")
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")

                    st.markdown("---")
                    
                    col_left, col_right = st.columns([1, 1])
                    
                    with col_left:
                        st.markdown("### 📝 Informations")
                        
                        if f'edit_instructions_{recipe["id"]}' not in st.session_state:
                            st.session_state[f'edit_instructions_{recipe["id"]}'] = text_to_instructions(
                                recipe.get('instructions', '')
                            )
                        
                        new_name = st.text_input(
                            "Nom", 
                            value=recipe['name'],
                            key=f"edit_rname_{recipe['id']}"
                        )
                        new_servings = st.number_input(
                            "Personnes de base", 
                            min_value=1,
                            value=recipe.get('base_servings', 4),
                            key=f"edit_rservings_{recipe['id']}"
                        )
                        
                        st.markdown("**Instructions :**")
                        for idx, instruction in enumerate(st.session_state[f'edit_instructions_{recipe["id"]}']):
                            col_instr, col_del_instr = st.columns([5, 1])
                            with col_instr:
                                st.text_input(
                                    f"Instruction {idx + 1}",
                                    value=instruction,
                                    key=f"edit_instruction_{recipe['id']}_{idx}",
                                    placeholder=f"Étape {idx + 1}..."
                                )
                                st.session_state[f'edit_instructions_{recipe["id"]}'][idx] = st.session_state[f"edit_instruction_{recipe['id']}_{idx}"]
                            with col_del_instr:
                                if len(st.session_state[f'edit_instructions_{recipe["id"]}']) > 1:
                                    if st.button("❌", key=f"del_edit_instruction_{recipe['id']}_{idx}", help="Supprimer cette instruction"):
                                        st.session_state[f'edit_instructions_{recipe["id"]}'].pop(idx)
                                        st.rerun()
                        
                        if st.button("➕ Nouvelle instruction", key=f"add_edit_instruction_{recipe['id']}", use_container_width=True):
                            st.session_state[f'edit_instructions_{recipe["id"]}'].append("")
                            st.rerun()
                        
                        st.markdown("---")
                        if st.button("💾 Sauvegarder les modifications", key=f"save_recipe_{recipe['id']}", use_container_width=True, type="primary"):
                            try:
                                instructions_text = instructions_to_text(st.session_state[f'edit_instructions_{recipe["id"]}'])
                                supabase.table("recipes").update({
                                    "name": new_name.strip().capitalize(),
                                    "base_servings": new_servings,
                                    "instructions": instructions_text
                                }).eq("id", recipe['id']).execute()
                                st.success("✅ Modifications enregistrées !")
                                del st.session_state[f'edit_instructions_{recipe["id"]}']
                                refresh_data()
                            except Exception as e:
                                st.error(f"Erreur : {e}")
                    
                    with col_right:
                        st.markdown("### 🛒 Ingrédients")
                        
                        rec_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                        
                        if rec_ings:
                            for ri in rec_ings:
                                ing = next((i for i in ingredients if i['id'] == ri['ingredient_id']), None)
                                if ing:
                                    col1, col2, col3 = st.columns([4, 2, 1])
                                    col1.markdown(f"**{ing['name']}**")
                                    col2.markdown(f"{format_quantity(ri['quantity'])} {ing['unit']}")
                                    if col3.button("❌", key=f"del_ri_{ri['id']}", help="Retirer"):
                                        try:
                                            supabase.table("recipe_ingredients").delete().eq("id", ri['id']).execute()
                                            refresh_data()
                                        except Exception as e:
                                            st.error(f"Erreur : {e}")
                        else:
                            st.info("Aucun ingrédient pour l'instant")
                        
                        st.markdown("---")
                        
                        st.markdown("**Ajouter des ingrédients :**")
                        
                        existing_ings = [ri['ingredient_id'] for ri in rec_ings]
                        available_ings = [i for i in ingredients if i['id'] not in existing_ings]
                        
                        if available_ings:
                            if f'new_ings_{recipe["id"]}' not in st.session_state:
                                st.session_state[f'new_ings_{recipe["id"]}'] = [
                                    {"ingredient": None, "quantity": 100.0, "unit": "g"}
                                ]
                            
                            for idx, row in enumerate(st.session_state[f'new_ings_{recipe["id"]}']):
                                col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 0.5])
                                
                                with col1:
                                    ing_names = [i['name'] for i in available_ings]
                                    already_selected = [
                                        r['ingredient'] for i, r in enumerate(st.session_state[f'new_ings_{recipe["id"]}']) 
                                        if i != idx and r['ingredient']
                                    ]
                                    available_for_this_row = [n for n in ing_names if n not in already_selected]
                                    
                                    if row['ingredient'] and row['ingredient'] in available_for_this_row:
                                        current_index = available_for_this_row.index(row['ingredient'])
                                    elif row['ingredient']:
                                        available_for_this_row.insert(0, row['ingredient'])
                                        current_index = 0
                                    else:
                                        current_index = 0
                                    
                                    selected_ing = st.selectbox(
                                        "Ingrédient",
                                        available_for_this_row,
                                        index=current_index,
                                        key=f"new_ing_select_{recipe['id']}_{idx}",
                                        label_visibility="collapsed"
                                    )
                                    st.session_state[f'new_ings_{recipe["id"]}'][idx]['ingredient'] = selected_ing
                                
                                with col2:
                                    qty = st.number_input(
                                        "Quantité",
                                        min_value=0.1,
                                        value=float(row['quantity']),
                                        step=10.0,
                                        key=f"new_ing_qty_{recipe['id']}_{idx}",
                                        label_visibility="collapsed"
                                    )
                                    st.session_state[f'new_ings_{recipe["id"]}'][idx]['quantity'] = qty
                                
                                with col3:
                                    if selected_ing:
                                        ing_obj = next((i for i in available_ings if i['name'] == selected_ing), None)
                                        default_unit = ing_obj['unit'] if ing_obj else "g"
                                    else:
                                        default_unit = row.get('unit', 'g')
                                    
                                    unit_index = UNITES.index(default_unit) if default_unit in UNITES else 0
                                    selected_unit = st.selectbox(
                                        "Unité",
                                        UNITES,
                                        index=unit_index,
                                        key=f"new_ing_unit_{recipe['id']}_{idx}",
                                        label_visibility="collapsed"
                                    )
                                    st.session_state[f'new_ings_{recipe["id"]}'][idx]['unit'] = selected_unit
                                
                                with col4:
                                    if len(st.session_state[f'new_ings_{recipe["id"]}']) > 1:
                                        if st.button("❌", key=f"remove_new_ing_{recipe['id']}_{idx}", help="Supprimer cette ligne"):
                                            st.session_state[f'new_ings_{recipe["id"]}'].pop(idx)
                                            st.rerun()
                            
                            col_add_row, col_save_all = st.columns(2)
                            
                            with col_add_row:
                                if st.button("➕ Nouvelle ligne", key=f"add_row_{recipe['id']}", use_container_width=True):
                                    st.session_state[f'new_ings_{recipe["id"]}'].append(
                                        {"ingredient": None, "quantity": 100.0, "unit": "g"}
                                    )
                                    st.rerun()
                            
                            with col_save_all:
                                if st.button("💾 Ajouter tous", key=f"save_all_ings_{recipe['id']}", use_container_width=True, type="primary"):
                                    try:
                                        added_count = 0
                                        for new_ing in st.session_state[f'new_ings_{recipe["id"]}']:
                                            if new_ing['ingredient']:
                                                ing_obj = next(
                                                    (i for i in available_ings if i['name'] == new_ing['ingredient']),
                                                    None
                                                )
                                                if ing_obj:
                                                    supabase.table("recipe_ingredients").insert({
                                                        "recipe_id": recipe['id'],
                                                        "ingredient_id": ing_obj['id'],
                                                        "quantity": new_ing['quantity']
                                                    }).execute()
                                                    added_count += 1
                                        
                                        if added_count > 0:
                                            st.success(f"✅ {added_count} ingrédient(s) ajouté(s) !")
                                            st.session_state[f'new_ings_{recipe["id"]}'] = [
                                                {"ingredient": None, "quantity": 100.0, "unit": "g"}
                                            ]
                                            refresh_data()
                                        else:
                                            st.warning("Sélectionnez au moins un ingrédient")
                                    except Exception as e:
                                        st.error(f"Erreur : {e}")
                        else:
                            st.info("Tous les ingrédients disponibles sont déjà dans cette recette")

    # ============================
    # ONGLET 4 : INGRÉDIENTS
    # ============================
    with tab_ingredients:
        st.header("Ingrédients")

        if st.button("➕ Ajouter un ingrédient", key="btn_show_add_ing", use_container_width=True):
            st.session_state.show_add_ing = True

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

        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))
        
        if ingredients:
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

if __name__ == "__main__":
    main()
