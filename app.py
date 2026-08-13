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

def get_display_name(recipe: Dict) -> str:
    """Retourne le nom d'affichage d'une recette (sans le préfixe [Ing])."""
    name = recipe.get('name', '')
    if name.startswith('[Ing] '):
        return name[6:]
    return name

# ------------------------------
# GÉNÉRATION PDF
# ------------------------------
def generate_pdf(planned_meals: List[Dict], aggregated_items: Dict,
                 recurrent_items: List[Dict], recipes_dict: Dict, 
                 start_date: date = None) -> bytes:
    """Génère un PDF A4 avec le menu et la liste de courses."""
    try:
        pdf = FPDF(format='A4', unit='mm')
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        
        # Dimensions
        page_width = 210
        page_height = 297
        margin = 10
        left_width = 115
        right_width = 68
        gap = 5
        
        # Couleurs personnalisées
        green_bg = (200, 230, 200)
        orange_bg = (255, 220, 180)
        gray_bg = (240, 240, 240)
        white_bg = (255, 255, 255)
        light_gray_bg = (248, 248, 248)
        border_gray = (180, 180, 180)
        
        # ==================== EN-TÊTE COMPACT ====================
        pdf.set_font('Helvetica', 'B', 18)
        pdf.cell(0, 10, clean_pdf_str('Menus de la semaine'), ln=True, align='C')
        
        if start_date:
            end_date = start_date + timedelta(days=6)
            pdf.set_font('Helvetica', '', 11)
            pdf.cell(0, 6, clean_pdf_str(f'Du {start_date.strftime("%d/%m/%Y")} au {end_date.strftime("%d/%m/%Y")}'), ln=True, align='C')
        
        pdf.ln(2)
        
        y_start = pdf.get_y()
        left_x = margin
        right_x = margin + left_width + gap
        
        # Hauteur disponible
        available_height = page_height - margin - y_start
        
        # ==================== LIGNE POINTILLÉE DE DÉCOUPE ====================
        pdf.set_draw_color(150, 150, 150)
        pdf.set_dash_pattern(dash=1, gap=2)
        pdf.line(right_x - gap/2, y_start - 2, right_x - gap/2, page_height - margin)
        pdf.set_dash_pattern()
        
        # ==================== GÉNÉRER LES JOURS ====================
        if start_date:
            week_days = []
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                english_day = current_date.strftime('%A')
                french_day = JOURS_FR.get(english_day, english_day)
                week_days.append({
                    'day_name': french_day,
                    'day_number': current_date.strftime('%d/%m')
                })
        else:
            week_days = [{'day_name': d, 'day_number': ''} for d in JOURS]
        
        # Regrouper les repas
        schedule = {}
        for day_info in week_days:
            day_name = day_info['day_name']
            schedule[day_name] = {"Midi": [], "Soir": []}
            
            for pm in planned_meals:
                if pm.get('day') == day_name:
                    rec = recipes_dict.get(pm.get('recipe_id'))
                    if rec:
                        rec_name = get_display_name(rec)
                    else:
                        rec_name = 'Inconnu'
                    
                    meal_type = pm.get('meal_type')
                    if meal_type in schedule[day_name]:
                        schedule[day_name][meal_type].append(rec_name)
        
        # Calculer la hauteur totale nécessaire pour le planning
        total_planning_height = 0
        for day_info in week_days:
            day_name = day_info['day_name']
            midi_count = len(schedule[day_name]['Midi'])
            soir_count = len(schedule[day_name]['Soir'])
            
            # Hauteur pour ce jour : en-tête + déjeuner + dîner + espacement
            day_height = 6  # En-tête du jour
            day_height += 4 + (midi_count * 3.5) if midi_count > 0 else 7
            day_height += 4 + (soir_count * 3.5) if soir_count > 0 else 7
            day_height += 2  # Espacement
            total_planning_height += day_height
        
        # Hauteur du titre "Planning des Repas"
        title_height = 8
        
        # Hauteur disponible pour les jours
        days_available_height = available_height - title_height - 5
        
        # Facteur d'échelle si nécessaire
        if total_planning_height > days_available_height:
            scale_factor = days_available_height / total_planning_height
        else:
            scale_factor = 1.0
        
        # ==================== COLONNE GAUCHE : PLANNING ====================
        # Cadre vert pastel
        pdf.set_fill_color(*green_bg)
        pdf.set_xy(left_x, y_start)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(left_width, title_height, 'Planning des Repas', ln=True, fill=True, align='C')
        
        y = pdf.get_y() + 2
        
        # Affichage des jours avec hauteur adaptative
        for i, day_info in enumerate(week_days):
            day_name = day_info['day_name']
            day_number = day_info['day_number']
            
            midi_items = schedule[day_name]['Midi']
            soir_items = schedule[day_name]['Soir']
            
            # Calculer la hauteur réelle du bloc jour (avec échelle)
            base_height = 6  # En-tête du jour
            midi_height = 4 + (len(midi_items) * 3.5) if midi_items else 7
            soir_height = 4 + (len(soir_items) * 3.5) if soir_items else 7
            spacing = 2
            
            actual_height = (base_height + midi_height + soir_height + spacing) * scale_factor
            
            # Vérifier si on a assez de place
            if y + actual_height > page_height - margin:
                break
            
            # Fond du jour (alternance)
            if i % 2 == 0:
                pdf.set_fill_color(*white_bg)
            else:
                pdf.set_fill_color(*light_gray_bg)
            
            # Dessiner le fond du jour
            pdf.rect(left_x, y, left_width, actual_height - 1, 'F')
            
            # En-tête du jour
            pdf.set_xy(left_x + 3, y + 1)
            pdf.set_font('Helvetica', 'B', 10)
            if day_number:
                day_label = f"{day_name} {day_number}"
            else:
                day_label = day_name
            pdf.cell(left_width - 6, 4, clean_pdf_str(day_label), border=0)
            
            y += 5 * scale_factor + 1
            
            # Déjeuner
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_xy(left_x + 5, y)
            pdf.cell(25, 3.5, 'Déjeuner :', border=0)
            
            if midi_items:
                pdf.set_font('Helvetica', '', 9)
                for idx, item in enumerate(midi_items):
                    pdf.set_xy(left_x + 30, y)
                    pdf.cell(left_width - 35, 3.5, clean_pdf_str(item)[:55], border=0, ln=True)
                    y += 3.5 * scale_factor
            else:
                pdf.set_font('Helvetica', 'I', 9)
                pdf.set_xy(left_x + 30, y)
                pdf.cell(left_width - 35, 3.5, '-', border=0, ln=True)
                y += 3.5 * scale_factor
            
            y += 0.5 * scale_factor
            
            # Dîner
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_xy(left_x + 5, y)
            pdf.cell(25, 3.5, 'Dîner :', border=0)
            
            if soir_items:
                pdf.set_font('Helvetica', '', 9)
                for idx, item in enumerate(soir_items):
                    pdf.set_xy(left_x + 30, y)
                    pdf.cell(left_width - 35, 3.5, clean_pdf_str(item)[:55], border=0, ln=True)
                    y += 3.5 * scale_factor
            else:
                pdf.set_font('Helvetica', 'I', 9)
                pdf.set_xy(left_x + 30, y)
                pdf.cell(left_width - 35, 3.5, '-', border=0, ln=True)
                y += 3.5 * scale_factor
            
            y += 2 * scale_factor
        
        # ==================== COLONNE DROITE : LISTE DE COURSES ====================
        y_right = y_start
        
        # Cadre orange pastel
        pdf.set_fill_color(*orange_bg)
        pdf.set_xy(right_x, y_right)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(right_width, title_height, 'Liste de Courses', ln=True, fill=True, align='C')
        
        y_right += title_height + 2
        
        by_cat = defaultdict(list)
        for item in aggregated_items.values():
            by_cat[item.get('category', 'Autre')].append(item)
        
        # Hauteur disponible pour la liste de courses
        courses_available_height = available_height - title_height - 40  # Garder de la place pour produits récurrents
        
        y_courses_start = y_right
        y_courses_end = y_courses_start + courses_available_height
        
        if not by_cat:
            pdf.set_xy(right_x + 3, y_right)
            pdf.set_font('Helvetica', 'I', 9)
            pdf.cell(right_width - 6, 5, 'Aucun article', ln=True)
            y_right += 5
        else:
            for cat in RAYONS:
                if cat in by_cat:
                    if y_right > y_courses_end:
                        break
                    
                    # Fond de la catégorie
                    pdf.set_fill_color(255, 240, 220)
                    pdf.set_xy(right_x, y_right)
                    pdf.set_font('Helvetica', 'B', 9)
                    pdf.cell(right_width, 5, clean_pdf_str(cat), ln=True, fill=True)
                    y_right += 5
                    
                    pdf.set_font('Helvetica', '', 8)
                    for it in by_cat[cat]:
                        if y_right > y_courses_end:
                            break
                        
                        qty_str = format_quantity(it['qty'])
                        
                        # Case à cocher
                        pdf.set_draw_color(100, 100, 100)
                        pdf.rect(right_x + 3, y_right, 2.5, 2.5, 'D')
                        
                        # Texte de l'item
                        line = f"{it['name']} : {qty_str} {it['unit']}"
                        pdf.set_xy(right_x + 7, y_right - 0.5)
                        pdf.cell(right_width - 10, 3.5, clean_pdf_str(line), ln=True)
                        y_right += 3.5
                    
                    y_right += 1
        
        # ==================== PRODUITS RÉCURRENTS ====================
        if recurrent_items:
            y_right = max(y_right + 3, page_height - margin - 30)
            
            if y_right < page_height - margin - 15:
                # Cadre gris très clair
                pdf.set_fill_color(*gray_bg)
                pdf.set_xy(right_x, y_right)
                pdf.set_font('Helvetica', 'B', 10)
                pdf.cell(right_width, 7, 'Produits récurrents', ln=True, fill=True, align='C')
                y_right += 9
                
                pdf.set_font('Helvetica', '', 8)
                for rec in recurrent_items:
                    if y_right > page_height - margin - 2:
                        break
                    
                    # Case à cocher
                    pdf.set_draw_color(100, 100, 100)
                    pdf.rect(right_x + 3, y_right, 2.5, 2.5, 'D')
                    
                    # Texte
                    pdf.set_xy(right_x + 7, y_right - 0.5)
                    pdf.cell(right_width - 10, 3.5, clean_pdf_str(rec['name']), ln=True)
                    y_right += 3.5

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

    # Navigation par onglets
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
        all_recipes = st.session_state.data.get('recipes', [])
        recipes_dict = {r['id']: r for r in all_recipes}
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))
        
        # Recettes normales
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ')])
        
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
            
            # Génération des 7 jours
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
                                
                                servings_list = [meal.get('servings', 1) for meal in meals]
                                servings = max(servings_list) if servings_list else 1
                                
                                st.markdown(f"**{label} ({servings}p) :**")
                                
                                for meal in meals:
                                    rec = recipes_dict.get(meal.get('recipe_id'))
                                    if rec:
                                        item_name = get_display_name(rec)
                                    else:
                                        item_name = 'Inconnu'
                                    
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
                    
                    # Ajout d'un repas
                    with st.expander(f"➕ Ajouter", expanded=False):
                        col_type, col_meal_type = st.columns([1, 1])
                        with col_type:
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
                                if recipes:
                                    recipe_names = [r['name'] for r in recipes]
                                    selected_item = st.selectbox(
                                        "Recette",
                                        recipe_names,
                                        key=f"recipe_{day_info['day_name']}_{day_info['day_number']}"
                                    )
                                    selected_recipe = next((r for r in recipes if r['name'] == selected_item), None)
                                    default_servings = selected_recipe.get('base_servings', 4) if selected_recipe else 4
                                else:
                                    st.warning("Aucune recette disponible")
                                    selected_recipe = None
                                    default_servings = 4
                            else:
                                if ingredients:
                                    ingredient_names = [i['name'] for i in ingredients]
                                    selected_item = st.selectbox(
                                        "Ingrédient",
                                        ingredient_names,
                                        key=f"ingredient_{day_info['day_name']}_{day_info['day_number']}"
                                    )
                                    selected_recipe = None
                                    default_servings = 1
                                else:
                                    st.warning("Aucun ingrédient disponible")
                                    selected_recipe = None
                                    default_servings = 1
                        
                        with col_servings:
                            if item_type == "Recette":
                                servings = st.number_input(
                                    "Convives",
                                    min_value=1,
                                    value=default_servings,
                                    key=f"servings_{day_info['day_name']}_{day_info['day_number']}"
                                )
                            else:
                                servings = st.number_input(
                                    "Quantité",
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
                                elif item_type == "Ingrédient":
                                    ing_obj = next((i for i in ingredients if i['name'] == selected_item), None)
                                    if ing_obj:
                                        existing_ing_recipe = next(
                                            (r for r in all_recipes if r['name'] == f"[Ing] {ing_obj['name']}"),
                                            None
                                        )
                                        
                                        if existing_ing_recipe:
                                            ing_recipe_id = existing_ing_recipe['id']
                                        else:
                                            temp_recipe = supabase.table("recipes").insert({
                                                "name": f"[Ing] {ing_obj['name']}",
                                                "base_servings": 1,
                                                "instructions": ""
                                            }).execute()
                                            
                                            if temp_recipe.data:
                                                ing_recipe_id = temp_recipe.data[0]['id']
                                                
                                                supabase.table("recipe_ingredients").insert({
                                                    "recipe_id": ing_recipe_id,
                                                    "ingredient_id": ing_obj['id'],
                                                    "quantity": 1
                                                }).execute()
                                            else:
                                                st.error("Erreur lors de la création")
                                                st.stop()
                                        
                                        supabase.table("planned_meals").insert({
                                            "day": day_info['day_name'],
                                            "meal_type": meal_type,
                                            "recipe_id": ing_recipe_id,
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
                    ingredients_dict = {i['id']: i for i in st.session_state.data.get('ingredients', [])}
                    recipe_ings = st.session_state.data.get('recipe_ingredients', [])
                    
                    aggregated = {}
                    for pm in planned_meals:
                        rec = recipes_dict.get(pm['recipe_id'])
                        if not rec:
                            continue
                        
                        if rec['name'].startswith('[Ing] '):
                            ing_name = get_display_name(rec)
                            ing = next((i for i in ingredients_dict.values() if i['name'] == ing_name), None)
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
                        else:
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
                    
                    recurrent = [i for i in ingredients_dict.values() if i.get('is_recurrent')]
                    
                    pdf_bytes = generate_pdf(
                        planned_meals, 
                        aggregated, 
                        recurrent, 
                        recipes_dict,
                        start_date=start_date
                    )
                    if pdf_bytes:
                        st.download_button(
                            "📥 Télécharger le PDF",
                            data=pdf_bytes,
                            file_name=f"menus_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf",
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
        
        all_recipes = st.session_state.data.get('recipes', [])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = st.session_state.data.get('ingredients', [])
        
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ')])
        
        if not recipes:
            st.info("Aucune recette disponible. Créez-en une dans l'onglet 'Créer / Éditer'.")
        else:
            recipe_names = [r['name'] for r in recipes]
            selected_name = st.selectbox(
                "Choisir une recette", 
                recipe_names,
                key="consult_recipe_select"
            )
            recipe = next((r for r in recipes if r['name'] == selected_name), None)
            
            if recipe:
                st.markdown("---")
                
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
                
                ratio = target_servings / base_servings if base_servings > 0 else 1
                
                st.markdown("### 🛒 Ingrédients")
                
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

        all_recipes = st.session_state.data.get('recipes', [])
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ')])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))

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
