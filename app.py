import streamlit as st
from supabase import create_client, Client
from fpdf import FPDF
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import re
import base64
import streamlit.components.v1 as components

# ------------------------------
# CONFIGURATION DE LA PAGE
# ------------------------------
st.set_page_config(
    page_title="Gestionnaire de Menus",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ------------------------------
# CONSTANTES
# ------------------------------
UNITES = ["g", "kg", "ml", "cl", "l", "unité", "pièce", "tranche", "gousse", 
          "sachet", "boîte", "barquette", "c. à soupe", "c. à café", "pincée"]

RAYONS = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers",
          "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
REPAS = ["Midi", "Soir"]

JOURS_FR = {
    'Monday': 'Lundi',
    'Tuesday': 'Mardi',
    'Wednesday': 'Mercredi',
    'Thursday': 'Jeudi',
    'Friday': 'Vendredi',
    'Saturday': 'Samedi',
    'Sunday': 'Dimanche'
}

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
    st.session_state.data = load_data()
    st.rerun()

# ------------------------------
# FONCTIONS UTILITAIRES
# ------------------------------
def clean_pdf_str(text: Any) -> str:
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
    if isinstance(qty, float) and qty.is_integer():
        return str(int(qty))
    return f"{qty:.2f}".rstrip('0').rstrip('.')

def format_servings(servings: float) -> str:
    if servings == int(servings):
        return str(int(servings))
    return str(servings)

def format_liste_quantity(qty: float, unit: str) -> tuple:
    if unit in ['g', 'gramme', 'grammes'] and qty >= 1000:
        return qty / 1000, 'kg'
    elif unit in ['ml', 'millilitre'] and qty >= 1000:
        return qty / 1000, 'l'
    else:
        return qty, unit

def instructions_to_text(instructions_list: List[str]) -> str:
    if not instructions_list:
        return ""
    return "\n".join([f"{i+1}. {instr}" for i, instr in enumerate(instructions_list) if instr.strip()])

def text_to_instructions(text: str) -> List[str]:
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
    return sorted(items, key=lambda x: x.get('name', '').lower())

def get_display_name(recipe: Dict) -> str:
    name = recipe.get('name', '')
    if name.startswith('[Ing] '):
        return name[6:]
    if name.startswith('[Txt] '):
        return name[6:]
    return name

def open_pdf_button(pdf_bytes: bytes):
    b64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
    
    html_component = f"""
    <button id="open-pdf-btn" style="
        width: 100%;
        padding: 12px 20px;
        color: white;
        background-color: #4CAF50;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        font-size: 16px;
        cursor: pointer;
        margin-bottom: 10px;">
        📄 Ouvrir le PDF dans un nouvel onglet
    </button>
    <script>
    document.getElementById("open-pdf-btn").addEventListener("click", function() {{
        const b64Data = "{b64_pdf}";
        const byteCharacters = atob(b64Data);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {{
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }}
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], {{ type: "application/pdf" }});
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
        
        setTimeout(() => {{
            URL.revokeObjectURL(url);
        }}, 60000);
    }});
    </script>
    """
    
    components.html(html_component, height=60)

def convert_to_unit(quantity: float, unit_source: str, unit_cible: str, poids_piece_g: float = None) -> float:
    unit_source = unit_source.lower().strip() if unit_source else ""
    unit_cible = unit_cible.lower().strip() if unit_cible else ""
    
    if unit_source in ['g', 'gramme', 'grammes']:
        qty_kg = quantity / 1000
    elif unit_source in ['kg', 'kilo', 'kilos']:
        qty_kg = quantity
    elif unit_source in ['ml', 'millilitre']:
        qty_kg = quantity / 1000
    elif unit_source in ['cl', 'centilitre']:
        qty_kg = quantity / 100
    elif unit_source in ['l', 'litre']:
        qty_kg = quantity
    elif unit_source in ['c. à soupe', 'cuillère à soupe']:
        qty_kg = quantity * 0.015
    elif unit_source in ['c. à café', 'cuillère à café']:
        qty_kg = quantity * 0.005
    elif unit_source in ['unité', 'pièce', 'tranche', 'gousse', 'sachet', 'boîte', 'barquette']:
        if poids_piece_g is not None and poids_piece_g > 0:
            qty_kg = (quantity * poids_piece_g) / 1000
        else:
            qty_kg = quantity
    else:
        qty_kg = quantity
    
    if unit_cible in ['g', 'gramme', 'grammes']:
        return qty_kg * 1000
    elif unit_cible in ['kg', 'kilo', 'kilos']:
        return qty_kg
    elif unit_cible in ['ml', 'millilitre']:
        return qty_kg * 1000
    elif unit_cible in ['cl', 'centilitre']:
        return qty_kg * 100
    elif unit_cible in ['l', 'litre']:
        return qty_kg
    elif unit_cible in ['unité', 'pièce', 'tranche', 'gousse', 'sachet', 'boîte', 'barquette']:
        if poids_piece_g is not None and poids_piece_g > 0:
            return qty_kg * 1000 / poids_piece_g
        else:
            return qty_kg
    else:
        return qty_kg

# ------------------------------
# GÉNÉRATION PDF
# ------------------------------
def generate_pdf(planned_meals: List[Dict], aggregated_items: Dict,
                 recurrent_items: List[Dict], recipes_dict: Dict, 
                 ingredients_dict: Dict = None,
                 start_date: date = None) -> bytes:
    try:
        pdf = FPDF(format='A4', unit='mm')
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
        
        page_width = 210
        page_height = 297
        margin = 10
        left_width = 115
        right_width = 68
        gap = 5
        day_block_width = 15
        
        green_bg = (200, 230, 200)
        orange_bg = (255, 220, 180)
        gray_bg = (240, 240, 240)
        midi_bg = (255, 250, 240)
        soir_bg = (240, 245, 255)
        day_bg = (245, 245, 220)
        
        title_font_size = 28
        period_font_size = 20
        day_font_size = 13
        meal_font_size = 11
        courses_font_size = 10
        courses_line_height = 4.5
        
        left_x = margin
        right_x = margin + left_width + gap
        
        pdf.set_draw_color(150, 150, 150)
        pdf.set_dash_pattern(dash=1, gap=2)
        pdf.line(right_x - gap/2, margin, right_x - gap/2, page_height - margin)
        pdf.set_dash_pattern()
        
        if start_date:
            week_days = []
            for i in range(7):
                current_date = start_date + timedelta(days=i)
                english_day = current_date.strftime('%A')
                french_day = JOURS_FR.get(english_day, english_day)
                week_days.append({'day_name': french_day, 'date': current_date})
        else:
            week_days = [{'day_name': d, 'date': None} for d in JOURS]
        
        schedule = {}
        for day_info in week_days:
            day_name = day_info['day_name']
            day_date = day_info['date']
            schedule[day_name] = {"Midi": [], "Soir": []}
            
            for pm in planned_meals:
                if day_date and pm.get('date_menu'):
                    if pm.get('date_menu') != day_date.isoformat():
                        continue
                elif pm.get('day') != day_name:
                    continue
                
                rec = recipes_dict.get(pm.get('recipe_id'))
                if rec:
                    rec_name = get_display_name(rec)
                    is_ingredient = rec['name'].startswith('[Ing] ')
                    ingredient_qty = pm.get('ingredient_qty')
                    
                    if is_ingredient and ingredient_qty:
                        ing_unit = None
                        if ingredients_dict:
                            for ing in ingredients_dict.values():
                                if ing['name'] == rec_name:
                                    ing_unit = ing['unit']
                                    break
                        if ing_unit:
                            rec_name = f"{rec_name} ({format_quantity(ingredient_qty)} {ing_unit})"
                        else:
                            rec_name = f"{rec_name} ({format_quantity(ingredient_qty)})"
                else:
                    rec_name = 'Inconnu'
                
                meal_type = pm.get('meal_type')
                if meal_type in schedule[day_name]:
                    schedule[day_name][meal_type].append({
                        'name': rec_name,
                        'servings': pm.get('servings', 1),
                        'has_recipe': pm.get('recipe_id') is not None
                    })
        
        pdf.set_font('Helvetica', 'B', title_font_size)
        pdf.set_xy(left_x, margin)
        pdf.cell(left_width, 12, clean_pdf_str('Menus de la semaine'), align='C')
        
        if start_date:
            end_date = start_date + timedelta(days=6)
            pdf.set_font('Helvetica', '', period_font_size)
            pdf.set_xy(left_x, margin + 12)
            pdf.cell(left_width, 8, clean_pdf_str(f'Du {start_date.strftime("%d/%m/%Y")} au {end_date.strftime("%d/%m/%Y")}'), align='C')
        
        y_start = margin + 22
        
        planning_title_height = 7
        pdf.set_fill_color(*green_bg)
        pdf.set_xy(left_x, y_start)
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(left_width, planning_title_height, 'Planning des Repas', ln=True, fill=True, align='C')
        
        planning_right_edge = left_x + left_width
        content_y_start = y_start + planning_title_height + 2
        
        total_available = page_height - margin - content_y_start
        day_gap = 1.5
        days_available = total_available - (len(week_days) - 1) * day_gap
        day_height = days_available / len(week_days)
        
        pdf.set_font('Helvetica', 'B', day_font_size)
        dimanche_width = pdf.get_string_width('Dimanche')
        min_height = dimanche_width + 6
        
        if day_height < min_height:
            day_height = min_height
            total_needed = day_height * len(week_days) + (len(week_days) - 1) * day_gap
            if total_needed > total_available:
                day_height = (total_available - (len(week_days) - 1) * day_gap) / len(week_days)
        
        inner_height = day_height - 1
        title_space = 4
        food_space = max(inner_height - title_space, 2)
        
        max_lines_per_day = 0
        for day_info in week_days:
            day_name = day_info['day_name']
            midi_count = max(len(schedule[day_name]['Midi']), 1)
            soir_count = max(len(schedule[day_name]['Soir']), 1)
            max_lines_per_day = max(max_lines_per_day, midi_count + soir_count)
        
        if max_lines_per_day > 0:
            meal_line_height = food_space / max_lines_per_day
            meal_line_height = max(2.5, min(meal_line_height, 5))
        else:
            meal_line_height = 4
        
        meal_spacing = 0.5
        y = content_y_start
        
        for i, day_info in enumerate(week_days):
            day_name = day_info['day_name']
            midi_items = schedule[day_name]['Midi']
            soir_items = schedule[day_name]['Soir']
            
            content_x = left_x + day_block_width + 2
            content_width = planning_right_edge - content_x
            
            total_inner_height = day_height - 0.5
            interline = 1
            remaining_height = total_inner_height - interline
            
            midi_lines = max(len(midi_items), 1)
            soir_lines = max(len(soir_items), 1)
            total_lines = midi_lines + soir_lines
            
            if total_lines > 0:
                midi_height = (remaining_height * midi_lines / total_lines)
                soir_height = remaining_height - midi_height
            else:
                midi_height = remaining_height / 2
                soir_height = remaining_height / 2
            
            pdf.set_fill_color(*day_bg)
            pdf.rect(left_x, y, day_block_width, total_inner_height, 'F')
            pdf.set_draw_color(200, 200, 200)
            pdf.rect(left_x, y, day_block_width, total_inner_height, 'D')
            
            pdf.set_font('Helvetica', 'B', day_font_size)
            text_margin = 2
            with pdf.rotation(90, left_x + day_block_width/2, y + total_inner_height/2):
                text_width = total_inner_height - (text_margin * 2)
                text_height = day_block_width - 2
                pdf.set_xy(left_x + day_block_width/2 - text_width/2, y + total_inner_height/2 - text_height/2)
                pdf.cell(text_width, text_height, clean_pdf_str(day_name), align='C')
            
            pdf.set_fill_color(*midi_bg)
            pdf.rect(content_x, y, content_width, midi_height, 'F')
            pdf.set_draw_color(220, 220, 220)
            pdf.rect(content_x, y, content_width, midi_height, 'D')
            
            has_midi_content = any(item['has_recipe'] for item in midi_items)
            
            if has_midi_content:
                midi_servings = max([item['servings'] for item in midi_items if item['has_recipe']], default=1)
                midi_servings_str = format_servings(midi_servings)
                midi_label = f'Déjeuner ({midi_servings_str}) :'
            else:
                midi_label = 'Déjeuner :'
            
            pdf.set_xy(content_x + 3, y + 0.5)
            pdf.set_font('Helvetica', 'B', meal_font_size)
            pdf.cell(38, meal_line_height, clean_pdf_str(midi_label), border=0)
            
            if midi_items:
                pdf.set_font('Helvetica', '', meal_font_size)
                pdf.set_xy(content_x + 41, y + 0.5)
                pdf.cell(content_width - 46, meal_line_height, clean_pdf_str(midi_items[0]['name'])[:45], border=0, ln=True)
                y_content = y + 0.5 + meal_line_height + meal_spacing
                
                for item in midi_items[1:]:
                    if y_content + meal_line_height > y + midi_height - 0.5:
                        break
                    pdf.set_xy(content_x + 41, y_content)
                    pdf.cell(content_width - 46, meal_line_height, clean_pdf_str(item['name'])[:45], border=0, ln=True)
                    y_content += meal_line_height + meal_spacing
            else:
                pdf.set_font('Helvetica', 'I', meal_font_size)
                pdf.set_xy(content_x + 41, y + 0.5)
                pdf.cell(content_width - 46, meal_line_height, '-', border=0, ln=True)
            
            y_diner = y + midi_height + interline
            
            pdf.set_fill_color(*soir_bg)
            pdf.rect(content_x, y_diner, content_width, soir_height, 'F')
            pdf.set_draw_color(220, 220, 220)
            pdf.rect(content_x, y_diner, content_width, soir_height, 'D')
            
            has_soir_content = any(item['has_recipe'] for item in soir_items)
            
            if has_soir_content:
                soir_servings = max([item['servings'] for item in soir_items if item['has_recipe']], default=1)
                soir_servings_str = format_servings(soir_servings)
                soir_label = f'Dîner ({soir_servings_str}) :'
            else:
                soir_label = 'Dîner :'
            
            pdf.set_xy(content_x + 3, y_diner + 0.5)
            pdf.set_font('Helvetica', 'B', meal_font_size)
            pdf.cell(38, meal_line_height, clean_pdf_str(soir_label), border=0)
            
            if soir_items:
                pdf.set_font('Helvetica', '', meal_font_size)
                pdf.set_xy(content_x + 41, y_diner + 0.5)
                pdf.cell(content_width - 46, meal_line_height, clean_pdf_str(soir_items[0]['name'])[:45], border=0, ln=True)
                y_content = y_diner + 0.5 + meal_line_height + meal_spacing
                
                for item in soir_items[1:]:
                    if y_content + meal_line_height > y_diner + soir_height - 0.5:
                        break
                    pdf.set_xy(content_x + 41, y_content)
                    pdf.cell(content_width - 46, meal_line_height, clean_pdf_str(item['name'])[:45], border=0, ln=True)
                    y_content += meal_line_height + meal_spacing
            else:
                pdf.set_font('Helvetica', 'I', meal_font_size)
                pdf.set_xy(content_x + 41, y_diner + 0.5)
                pdf.cell(content_width - 46, meal_line_height, '-', border=0, ln=True)
            
            y += day_height + day_gap
        
        y_right = margin
        
        pdf.set_fill_color(*orange_bg)
        pdf.set_xy(right_x, y_right)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(right_width, 8, 'Liste de Courses', ln=True, fill=True, align='C')
        
        y_right += 10
        
        by_cat = defaultdict(list)
        for item in aggregated_items.values():
            by_cat[item.get('category', 'Autre')].append(item)
        
        if not by_cat:
            pdf.set_xy(right_x + 3, y_right)
            pdf.set_font('Helvetica', 'I', courses_font_size)
            pdf.cell(right_width - 6, 5, 'Aucun article', ln=True)
            y_right += 5
        else:
            for cat in RAYONS:
                if cat in by_cat:
                    pdf.set_fill_color(255, 240, 220)
                    pdf.set_xy(right_x, y_right)
                    pdf.set_font('Helvetica', 'B', courses_font_size)
                    pdf.cell(right_width, courses_line_height + 1, clean_pdf_str(cat), ln=True, fill=True)
                    y_right += courses_line_height + 1
                    
                    pdf.set_font('Helvetica', '', courses_font_size)
                    for it in by_cat[cat]:
                        qty = it['qty']
                        unit = it.get('unit', '')
                        
                        qty_display, unit_display = format_liste_quantity(qty, unit)
                        qty_str = format_quantity(qty_display)
                        
                        checkbox_size = 2.5
                        pdf.set_draw_color(100, 100, 100)
                        pdf.rect(right_x + 3, y_right + 1, checkbox_size, checkbox_size, 'D')
                        
                        line = f"{it['name']} : {qty_str} {unit_display}"
                        pdf.set_xy(right_x + 7, y_right)
                        pdf.cell(right_width - 10, courses_line_height, clean_pdf_str(line), ln=True)
                        y_right += courses_line_height
                    
                    y_right += 1
        
        if recurrent_items:
            y_right += 3
            
            pdf.set_fill_color(*gray_bg)
            pdf.set_xy(right_x, y_right)
            pdf.set_font('Helvetica', 'B', courses_font_size)
            pdf.cell(right_width, 7, 'Produits récurrents', ln=True, fill=True, align='C')
            y_right += 9
            
            col_width = (right_width - 10) / 2
            pdf.set_font('Helvetica', '', courses_font_size)
            
            for idx, rec in enumerate(recurrent_items):
                if y_right > page_height - margin - 2:
                    break
                
                if idx % 2 == 0:
                    x_pos = right_x + 3
                else:
                    x_pos = right_x + 5 + col_width
                
                checkbox_size = 2.5
                pdf.set_draw_color(100, 100, 100)
                pdf.rect(x_pos, y_right + 1, checkbox_size, checkbox_size, 'D')
                
                pdf.set_xy(x_pos + 4, y_right)
                pdf.cell(col_width - 4, courses_line_height, clean_pdf_str(rec['name']), ln=False)
                
                if idx % 2 == 1:
                    y_right += courses_line_height
            
            if len(recurrent_items) % 2 != 0:
                y_right += courses_line_height

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

    if 'data' not in st.session_state:
        st.session_state.data = load_data()

    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = "📅 Menus du jour"

    # Navigation dans la sidebar
    with st.sidebar:
        st.markdown("### 📱 Navigation")
        page_choisie = st.radio(
            "Aller vers :",
            ["📅 Menus du jour", "📅 Menus", "🔍 Consulter", "✏️ Créer / Éditer", "🥕 Ingrédients"],
            key="sidebar_nav"
        )
        st.session_state.active_tab = page_choisie
        
        st.markdown("---")
        if st.button("🔄 Recharger", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.markdown("---")

    # ============================
    # MENUS DU JOUR
    # ============================
    if st.session_state.active_tab == "📅 Menus du jour":
        st.header("Menus du jour")
        
        planned_meals = st.session_state.data.get('planned_meals', [])
        all_recipes = st.session_state.data.get('recipes', [])
        recipes_dict = {r['id']: r for r in all_recipes}
        ingredients = st.session_state.data.get('ingredients', [])
        
        col_date, col_info = st.columns([1, 2])
        with col_date:
            selected_date = st.date_input("Date", value=date.today(), key="menu_jour_date")
        with col_info:
            day_name_fr = JOURS_FR.get(selected_date.strftime('%A'), selected_date.strftime('%A'))
            st.info(f"📅 {day_name_fr} {selected_date.strftime('%d/%m/%Y')}")
        
        st.markdown("---")
        
        date_str = selected_date.isoformat()
        day_meals = [
            pm for pm in planned_meals 
            if pm.get('date_menu') == date_str
            or (pm.get('date_menu') is None and pm.get('day') == day_name_fr)
        ]
        
        meals_by_type = defaultdict(list)
        for meal in day_meals:
            meals_by_type[meal['meal_type']].append(meal)
        
        if not day_meals:
            st.info("Aucun repas planifié pour ce jour.")
        else:
            st.markdown(f"### 🍳 Déjeuner")
            if 'Midi' in meals_by_type:
                meals = meals_by_type['Midi']
                servings_list = [meal.get('servings', 1) for meal in meals if meal.get('recipe_id')]
                servings = max(servings_list) if servings_list else None
                if servings:
                    st.markdown(f"**({format_servings(servings)} personnes)**")
                for meal in meals:
                    if meal.get('recipe_id'):
                        rec = recipes_dict.get(meal.get('recipe_id'))
                        if rec:
                            item_name = get_display_name(rec)
                            if rec['name'].startswith('[Ing] '):
                                ing_obj = next((i for i in ingredients if i['name'] == item_name), None)
                                if ing_obj:
                                    qty = meal.get('ingredient_qty') or meal.get('servings', 1)
                                    st.markdown(f"• {item_name} : {format_quantity(qty)} {ing_obj['unit']}")
                                else:
                                    st.markdown(f"• {item_name}")
                            elif rec['name'].startswith('[Txt] '):
                                st.markdown(f"• {item_name}")
                            else:
                                if st.button(f"🔗 {item_name}", key=f"link_midi_{meal['id']}", help="Voir la recette"):
                                    st.session_state.selected_recipe_for_consult = rec['id']
                                    st.session_state.active_tab = "🔍 Consulter"
                                    st.rerun()
                    else:
                        st.markdown(f"• -")
            else:
                st.markdown("*Aucun déjeuner planifié*")
            
            st.markdown("---")
            
            st.markdown(f"### 🌙 Dîner")
            if 'Soir' in meals_by_type:
                meals = meals_by_type['Soir']
                servings_list = [meal.get('servings', 1) for meal in meals if meal.get('recipe_id')]
                servings = max(servings_list) if servings_list else None
                if servings:
                    st.markdown(f"**({format_servings(servings)} personnes)**")
                for meal in meals:
                    if meal.get('recipe_id'):
                        rec = recipes_dict.get(meal.get('recipe_id'))
                        if rec:
                            item_name = get_display_name(rec)
                            if rec['name'].startswith('[Ing] '):
                                ing_obj = next((i for i in ingredients if i['name'] == item_name), None)
                                if ing_obj:
                                    qty = meal.get('ingredient_qty') or meal.get('servings', 1)
                                    st.markdown(f"• {item_name} : {format_quantity(qty)} {ing_obj['unit']}")
                                else:
                                    st.markdown(f"• {item_name}")
                            elif rec['name'].startswith('[Txt] '):
                                st.markdown(f"• {item_name}")
                            else:
                                if st.button(f"🔗 {item_name}", key=f"link_soir_{meal['id']}", help="Voir la recette"):
                                    st.session_state.selected_recipe_for_consult = rec['id']
                                    st.session_state.active_tab = "🔍 Consulter"
                                    st.rerun()
                    else:
                        st.markdown(f"• -")
            else:
                st.markdown("*Aucun dîner planifié*")

    # ============================
    # MENUS (PLANIFICATION)
    # ============================
    elif st.session_state.active_tab == "📅 Menus":
        st.header("Planification des menus")
        
        planned_meals = st.session_state.data.get('planned_meals', [])
        all_recipes = st.session_state.data.get('recipes', [])
        recipes_dict = {r['id']: r for r in all_recipes}
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))
        ingredients_dict = {i['id']: i for i in st.session_state.data.get('ingredients', [])}
        
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ') and not r['name'].startswith('[Txt] ')])
        
        if not recipes and not ingredients:
            st.warning("Créez d'abord des recettes ou des ingrédients !")
        else:
            if 'selected_start_date' not in st.session_state:
                st.session_state.selected_start_date = date.today()
            
            col_calendar, col_info, col_clear_btn = st.columns([1, 2, 1])
            with col_calendar:
                start_date = st.date_input("Date de début", value=st.session_state.selected_start_date, key="week_start_date_input")
                st.session_state.selected_start_date = start_date
            with col_info:
                end_date = start_date + timedelta(days=6)
                st.info(f"📅 Semaine du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}")
            with col_clear_btn:
                st.write("")
                if st.button("🗑️ Vider toute la semaine", key="clear_week_top", use_container_width=True):
                    week_dates_clear = [(start_date + timedelta(days=i)).isoformat() for i in range(7)]
                    for date_str in week_dates_clear:
                        meals_to_delete = [pm for pm in planned_meals if pm.get('date_menu') == date_str]
                        for meal in meals_to_delete:
                            supabase.table("planned_meals").delete().eq("id", meal['id']).execute()
                    st.success("✅ Semaine vidée !")
                    refresh_data()
            
            st.markdown("---")
            
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
            
            for day_info in week_days:
                with st.container():
                    if day_info['is_today']:
                        st.markdown(f"### 📍 **{day_info['day_name']} {day_info['day_number']}** (Aujourd'hui)")
                    else:
                        st.markdown(f"### 📅 {day_info['day_name']} {day_info['day_number']}")
                    
                    day_date_str = day_info['date'].isoformat()
                    day_meals = [
                        pm for pm in planned_meals 
                        if pm.get('date_menu') == day_date_str
                        or (pm.get('date_menu') is None and pm.get('day') == day_info['day_name'])
                    ]
                    
                    meals_by_type = defaultdict(list)
                    for meal in day_meals:
                        meals_by_type[meal['meal_type']].append(meal)
                    
                    if day_meals:
                        for meal_type in REPAS:
                            if meal_type in meals_by_type:
                                meals = meals_by_type[meal_type]
                                label = REPAS_LABELS.get(meal_type, meal_type)
                                
                                has_content = any(meal.get('recipe_id') is not None for meal in meals)
                                
                                if has_content:
                                    servings_list = [meal.get('servings', 1) for meal in meals if meal.get('recipe_id')]
                                    servings = max(servings_list) if servings_list else 1
                                    st.markdown(f"**{label} ({format_servings(servings)}) :**")
                                else:
                                    st.markdown(f"**{label} :**")
                                
                                for meal in meals:
                                    if meal.get('recipe_id'):
                                        rec = recipes_dict.get(meal.get('recipe_id'))
                                        if rec:
                                            item_name = get_display_name(rec)
                                            if rec['name'].startswith('[Ing] '):
                                                ing_obj = next((i for i in ingredients if i['name'] == item_name), None)
                                                if ing_obj:
                                                    qty = meal.get('ingredient_qty') or meal.get('servings', 1)
                                                    item_name = f"{item_name} ({format_quantity(qty)} {ing_obj['unit']})"
                                        else:
                                            item_name = 'Inconnu'
                                    else:
                                        item_name = '-'
                                    
                                    col_item, col_edit, col_del = st.columns([8, 1, 1])
                                    with col_item:
                                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• {item_name}")
                                    with col_edit:
                                        if st.button("✏️", key=f"edit_btn_{meal['id']}", help="Modifier"):
                                            st.session_state[f"show_edit_{meal['id']}"] = True
                                    with col_del:
                                        if st.button("❌", key=f"del_meal_{meal['id']}", help="Supprimer"):
                                            try:
                                                supabase.table("planned_meals").delete().eq("id", meal['id']).execute()
                                                refresh_data()
                                            except Exception as e:
                                                st.error(f"Erreur : {e}")
                                    
                                    if st.session_state.get(f"show_edit_{meal['id']}", False):
                                        with st.expander(f"✏️ Modifier : {item_name}", expanded=True):
                                            rec = recipes_dict.get(meal.get('recipe_id'))
                                            
                                            if rec and rec['name'].startswith('[Ing] '):
                                                ing_name = get_display_name(rec)
                                                ing_obj = next((i for i in ingredients if i['name'] == ing_name), None)
                                                
                                                col1, col2, col3 = st.columns(3)
                                                with col1:
                                                    new_qty = st.number_input(
                                                        f"Quantité ({ing_obj['unit'] if ing_obj else ''})",
                                                        min_value=0.1,
                                                        value=float(meal.get('ingredient_qty') or meal.get('servings', 1)),
                                                        step=0.5,
                                                        key=f"edit_qty_{meal['id']}"
                                                    )
                                                with col2:
                                                    new_servings = st.number_input(
                                                        "Convives",
                                                        min_value=1,
                                                        value=int(meal.get('servings', 4)),
                                                        step=1,
                                                        key=f"edit_serv_{meal['id']}"
                                                    )
                                                with col3:
                                                    st.write("")
                                                    st.write("")
                                                    if st.button("💾 Enregistrer", key=f"save_edit_{meal['id']}", use_container_width=True):
                                                        supabase.table("planned_meals").update({
                                                            "ingredient_qty": new_qty,
                                                            "servings": new_servings
                                                        }).eq("id", meal['id']).execute()
                                                        st.session_state[f"show_edit_{meal['id']}"] = False
                                                        refresh_data()
                                            
                                            elif rec and rec['name'].startswith('[Txt] '):
                                                col1, col2, col3 = st.columns(3)
                                                with col1:
                                                    new_text = st.text_input(
                                                        "Texte",
                                                        value=get_display_name(rec),
                                                        key=f"edit_txt_{meal['id']}"
                                                    )
                                                with col2:
                                                    new_servings = st.number_input(
                                                        "Convives",
                                                        min_value=1,
                                                        value=int(meal.get('servings', 4)),
                                                        step=1,
                                                        key=f"edit_serv_{meal['id']}"
                                                    )
                                                with col3:
                                                    st.write("")
                                                    st.write("")
                                                    if st.button("💾 Enregistrer", key=f"save_edit_{meal['id']}", use_container_width=True):
                                                        supabase.table("recipes").update({
                                                            "name": f"[Txt] {new_text.strip()}"
                                                        }).eq("id", meal['recipe_id']).execute()
                                                        supabase.table("planned_meals").update({
                                                            "servings": new_servings
                                                        }).eq("id", meal['id']).execute()
                                                        st.session_state[f"show_edit_{meal['id']}"] = False
                                                        refresh_data()
                                            
                                            elif rec:
                                                col1, col2 = st.columns(2)
                                                with col1:
                                                    new_servings = st.number_input(
                                                        "Convives",
                                                        min_value=1,
                                                        value=int(meal.get('servings', rec.get('base_servings', 4))),
                                                        step=1,
                                                        key=f"edit_serv_{meal['id']}"
                                                    )
                                                with col2:
                                                    st.write("")
                                                    st.write("")
                                                    if st.button("💾 Enregistrer", key=f"save_edit_{meal['id']}", use_container_width=True):
                                                        supabase.table("planned_meals").update({
                                                            "servings": new_servings
                                                        }).eq("id", meal['id']).execute()
                                                        st.session_state[f"show_edit_{meal['id']}"] = False
                                                        refresh_data()
                                            
                                            if st.button("❌ Fermer", key=f"close_edit_{meal['id']}"):
                                                st.session_state[f"show_edit_{meal['id']}"] = False
                                                st.rerun()
                    else:
                        st.caption("Aucun repas planifié")
                    
                    expander_key = f"expander_{day_info['day_name']}_{day_info['day_number']}"
                    
                    if expander_key not in st.session_state:
                        st.session_state[expander_key] = False
                    
                    with st.expander(f"➕ Ajouter", expanded=st.session_state[expander_key]):
                        col_type, col_meal_type = st.columns([1, 1])
                        with col_type:
                            item_type = st.radio(
                                "Type",
                                ["Recette", "Ingrédient", "Texte libre"],
                                horizontal=True,
                                key=f"item_type_{day_info['day_name']}_{day_info['day_number']}"
                            )
                        with col_meal_type:
                            meal_type = st.selectbox(
                                "Repas",
                                ["-"] + REPAS,
                                format_func=lambda x: REPAS_LABELS.get(x, x) if x != "-" else "-",
                                key=f"meal_type_{day_info['day_name']}_{day_info['day_number']}"
                            )
                        
                        col_item, col_servings = st.columns([2, 1])
                        with col_item:
                            if item_type == "Recette":
                                if recipes:
                                    recipe_names = ["-"] + [r['name'] for r in recipes]
                                    selected_item = st.selectbox("Recette", recipe_names, key=f"recipe_{day_info['day_name']}_{day_info['day_number']}")
                                    selected_recipe = next((r for r in recipes if r['name'] == selected_item), None) if selected_item != "-" else None
                                    default_servings = selected_recipe.get('base_servings', 4) if selected_recipe else 4
                                else:
                                    st.warning("Aucune recette disponible")
                                    selected_recipe = None
                                    default_servings = 4
                            elif item_type == "Ingrédient":
                                if ingredients:
                                    ingredient_names = ["-"] + [i['name'] for i in ingredients]
                                    selected_item = st.selectbox("Ingrédient", ingredient_names, key=f"ingredient_{day_info['day_name']}_{day_info['day_number']}")
                                    selected_recipe = None
                                    default_servings = 1
                                else:
                                    st.warning("Aucun ingrédient disponible")
                                    selected_recipe = None
                                    default_servings = 1
                            else:
                                free_text = st.text_input("Texte libre", placeholder="ex: Restaurant, Pizza, etc.", key=f"free_text_{day_info['day_name']}_{day_info['day_number']}")
                                selected_item = None
                                selected_recipe = None
                                default_servings = 1
                        
                        with col_servings:
                            if item_type == "Recette":
                                servings = st.number_input("Convives", min_value=1, value=default_servings, step=1, key=f"servings_{day_info['day_name']}_{day_info['day_number']}")
                                ingredient_qty = None
                            elif item_type == "Ingrédient":
                                selected_ing_obj = next((i for i in ingredients if i['name'] == selected_item), None) if selected_item != "-" else None
                                ing_unit = selected_ing_obj['unit'] if selected_ing_obj else ""
                                label_qty = f"Quantité ({ing_unit})" if ing_unit else "Quantité"
                                ingredient_qty = st.number_input(label_qty, min_value=0.1, value=float(default_servings), step=0.5, key=f"ingredient_qty_{day_info['day_name']}_{day_info['day_number']}")
                                servings = st.number_input("Convives", min_value=1, value=4, step=1, key=f"servings_{day_info['day_name']}_{day_info['day_number']}")
                            else:
                                servings = st.number_input("Convives", min_value=1, value=4, step=1, key=f"servings_{day_info['day_name']}_{day_info['day_number']}")
                                ingredient_qty = None
                        
                        col_add_btn, col_close_btn = st.columns(2)
                        with col_add_btn:
                            if st.button("➕ Ajouter", key=f"add_meal_{day_info['day_name']}_{day_info['day_number']}", use_container_width=True):
                                if meal_type == "-":
                                    st.warning("Sélectionnez un repas (Déjeuner ou Dîner)")
                                elif item_type == "Recette" and selected_item == "-":
                                    st.warning("Sélectionnez une recette")
                                elif item_type == "Ingrédient" and selected_item == "-":
                                    st.warning("Sélectionnez un ingrédient")
                                elif item_type == "Texte libre" and not free_text.strip():
                                    st.warning("Saisissez un texte")
                                else:
                                    try:
                                        if item_type == "Recette" and selected_recipe:
                                            supabase.table("planned_meals").insert({
                                                "day": day_info['day_name'],
                                                "date_menu": day_info['date'].isoformat(),
                                                "meal_type": meal_type,
                                                "recipe_id": selected_recipe['id'],
                                                "servings": servings
                                            }).execute()
                                        elif item_type == "Ingrédient":
                                            ing_obj = next((i for i in ingredients if i['name'] == selected_item), None)
                                            if ing_obj:
                                                existing_ing_recipe = next((r for r in all_recipes if r['name'] == f"[Ing] {ing_obj['name']}"), None)
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
                                                            "quantity": 1,
                                                            "unit": ing_obj['unit']
                                                        }).execute()
                                                    else:
                                                        st.error("Erreur lors de la création")
                                                        st.stop()
                                                supabase.table("planned_meals").insert({
                                                    "day": day_info['day_name'],
                                                    "date_menu": day_info['date'].isoformat(),
                                                    "meal_type": meal_type,
                                                    "recipe_id": ing_recipe_id,
                                                    "servings": servings,
                                                    "ingredient_qty": ingredient_qty
                                                }).execute()
                                        elif item_type == "Texte libre":
                                            txt_recipe = supabase.table("recipes").insert({
                                                "name": f"[Txt] {free_text.strip()}",
                                                "base_servings": 1,
                                                "instructions": ""
                                            }).execute()
                                            if txt_recipe.data:
                                                supabase.table("planned_meals").insert({
                                                    "day": day_info['day_name'],
                                                    "date_menu": day_info['date'].isoformat(),
                                                    "meal_type": meal_type,
                                                    "recipe_id": txt_recipe.data[0]['id'],
                                                    "servings": servings
                                                }).execute()
                                        st.success(f"✅ Ajouté pour {day_info['day_name']} {day_info['day_number']} !")
                                        st.session_state[expander_key] = True
                                        refresh_data()
                                    except Exception as e:
                                        st.error(f"Erreur : {e}")
                        with col_close_btn:
                            if st.button("Fermer", key=f"close_expander_{day_info['day_name']}_{day_info['day_number']}", use_container_width=True):
                                st.session_state[expander_key] = False
                                st.rerun()
                    
                    st.markdown("---")
            
            st.markdown("---")
            col_export, col_clear = st.columns(2)
            
            with col_export:
                if st.button("📄 Générer la fiche PDF", key="generate_pdf_btn", use_container_width=True):
                    recipe_ings = st.session_state.data.get('recipe_ingredients', [])
                    week_dates = [d['date'].isoformat() for d in week_days]
                    week_meals = [pm for pm in planned_meals if pm.get('date_menu') in week_dates]
                    
                    aggregated = {}
                    for pm in week_meals:
                        rec = recipes_dict.get(pm['recipe_id'])
                        if not rec:
                            continue
                        if rec['name'].startswith('[Ing] '):
                            ing_name = get_display_name(rec)
                            ing = next((i for i in ingredients_dict.values() if i['name'] == ing_name), None)
                            if ing and not ing.get('exclude_from_list'):
                                unite_liste = ing.get('unite_liste_courses') or ing['unit']
                                qty_source = pm.get('ingredient_qty') or pm['servings']
                                qty = convert_to_unit(qty_source, ing['unit'], unite_liste, ing.get('poids_piece_g'))
                                if ing['id'] not in aggregated:
                                    aggregated[ing['id']] = {"name": ing['name'], "qty": 0, "unit": unite_liste, "category": ing.get('category', 'Autre')}
                                aggregated[ing['id']]['qty'] += qty
                        elif not rec['name'].startswith('[Txt] '):
                            ratio = pm['servings'] / rec.get('base_servings', 1)
                            for ri in recipe_ings:
                                if ri['recipe_id'] == pm['recipe_id']:
                                    ing = ingredients_dict.get(ri['ingredient_id'])
                                    if not ing or ing.get('exclude_from_list'):
                                        continue
                                    ri_unit = ri.get('unit') or ing['unit']
                                    unite_liste = ing.get('unite_liste_courses') or ing['unit']
                                    qty = convert_to_unit(ri['quantity'] * ratio, ri_unit, unite_liste, ing.get('poids_piece_g'))
                                    if ing['id'] not in aggregated:
                                        aggregated[ing['id']] = {"name": ing['name'], "qty": 0, "unit": unite_liste, "category": ing.get('category', 'Autre')}
                                    aggregated[ing['id']]['qty'] += qty
                    
                    recurrent = [i for i in ingredients_dict.values() if i.get('is_recurrent')]
                    
                    pdf_bytes = generate_pdf(week_meals, aggregated, recurrent, recipes_dict, ingredients_dict=ingredients_dict, start_date=start_date)
                    if pdf_bytes:
                        st.session_state.pdf_bytes = pdf_bytes
                        st.session_state.show_pdf = True
                        st.rerun()
            
            with col_clear:
                if st.button("🗑️ Vider toute la semaine", key="clear_week_bottom", use_container_width=True):
                    try:
                        week_dates = [d['date'].isoformat() for d in week_days]
                        for date_str in week_dates:
                            meals_to_delete = [pm for pm in planned_meals if pm.get('date_menu') == date_str]
                            for meal in meals_to_delete:
                                supabase.table("planned_meals").delete().eq("id", meal['id']).execute()
                        st.success("✅ Semaine vidée !")
                        refresh_data()
                    except Exception as e:
                        st.error(f"Erreur : {e}")
            
            if st.session_state.get('show_pdf', False) and st.session_state.get('pdf_bytes'):
                st.markdown("---")
                st.success("✅ PDF généré avec succès !")
                open_pdf_button(st.session_state.pdf_bytes)
                col_download, col_close = st.columns(2)
                with col_download:
                    st.download_button("📥 Télécharger le PDF", data=st.session_state.pdf_bytes, file_name=f"menus_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf", mime="application/pdf", key="download_pdf_btn", use_container_width=True)
                with col_close:
                    if st.button("❌ Fermer", key="close_pdf_view", use_container_width=True):
                        st.session_state.show_pdf = False
                        st.rerun()

    # ============================
    # CONSULTER
    # ============================
    elif st.session_state.active_tab == "🔍 Consulter":
        st.header("Consulter une recette")
        
        all_recipes = st.session_state.data.get('recipes', [])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = st.session_state.data.get('ingredients', [])
        
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ') and not r['name'].startswith('[Txt] ')])
        
        if not recipes:
            st.info("Aucune recette disponible.")
        else:
            # Vérifier si une recette a été sélectionnée depuis "Menus du jour"
            if 'selected_recipe_for_consult' in st.session_state:
                selected_recipe_id = st.session_state.selected_recipe_for_consult
                selected_recipe = next((r for r in recipes if r['id'] == selected_recipe_id), None)
                if selected_recipe:
                    selected_name = selected_recipe['name']
                    del st.session_state.selected_recipe_for_consult
                else:
                    selected_name = None
            else:
                selected_name = None
            
            if selected_name is None:
                recipe_names = ["-"] + [r['name'] for r in recipes]
                selected_name = st.selectbox("Choisir une recette", recipe_names, key="consult_recipe_select")
            
            if selected_name == "-" or selected_name is None:
                st.info("Sélectionnez une recette à consulter.")
            else:
                recipe = next((r for r in recipes if r['name'] == selected_name), None)
                
                if recipe:
                    st.markdown("---")
                    
                    col_title, col_servings = st.columns([2, 1])
                    with col_title:
                        st.subheader(f"📖 {recipe['name']}")
                    with col_servings:
                        base_servings = recipe.get('base_servings', 4)
                        target_servings = st.number_input("Nombre de personnes", min_value=1, max_value=50, value=base_servings, step=1, key=f"consult_servings_{recipe['id']}")
                    
                    ratio = target_servings / base_servings if base_servings > 0 else 1
                    
                    st.markdown("### 🛒 Ingrédients")
                    
                    rec_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                    
                    if rec_ings:
                        for ri in rec_ings:
                            ing = next((i for i in ingredients if i['id'] == ri['ingredient_id']), None)
                            if ing:
                                qty_adjusted = ri['quantity'] * ratio
                                qty_display = format_quantity(qty_adjusted)
                                display_unit = ri.get('unit') or ing['unit']
                                
                                col1, col2, col3 = st.columns([3, 2, 2])
                                with col1:
                                    st.markdown(f"**{ing['name']}**")
                                with col2:
                                    st.markdown(f"{qty_display} {display_unit}")
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
    # CRÉER / ÉDITER
    # ============================
    elif st.session_state.active_tab == "✏️ Créer / Éditer":
        st.header("Créer / Éditer une recette")

        all_recipes = st.session_state.data.get('recipes', [])
        recipes = sort_list_by_name([r for r in all_recipes if not r['name'].startswith('[Ing] ') and not r['name'].startswith('[Txt] ')])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))

        mode = st.radio("Mode", ["➕ Créer une nouvelle recette", "✏️ Éditer une recette existante"], horizontal=True, key="recipe_mode")

        st.markdown("---")

        if mode == "➕ Créer une nouvelle recette":
            col_left, col_right = st.columns([1, 1])
            
            with col_left:
                st.markdown("### 📝 Informations de base")
                name = st.text_input("Nom de la recette *", placeholder="ex: Blanquette de veau", key="create_recipe_name")
                servings = st.number_input("Nombre de personnes", min_value=1, value=4, key="create_recipe_servings")
                st.markdown("### 📝 Instructions")
                if 'new_recipe_instructions' not in st.session_state:
                    st.session_state.new_recipe_instructions = [""]
                for idx, instruction in enumerate(st.session_state.new_recipe_instructions):
                    col_instr, col_del_instr = st.columns([5, 1])
                    with col_instr:
                        st.text_input(f"Instruction {idx + 1}", value=instruction, key=f"create_instruction_{idx}", placeholder=f"Étape {idx + 1}...")
                        st.session_state.new_recipe_instructions[idx] = st.session_state[f"create_instruction_{idx}"]
                    with col_del_instr:
                        if len(st.session_state.new_recipe_instructions) > 1:
                            if st.button("❌", key=f"del_create_instruction_{idx}"):
                                st.session_state.new_recipe_instructions.pop(idx)
                                st.rerun()
                if st.button("➕ Nouvelle instruction", key="add_create_instruction", use_container_width=True):
                    st.session_state.new_recipe_instructions.append("")
                    st.rerun()
            
            with col_right:
                st.markdown("### 🛒 Ingrédients de la recette")
                if 'new_recipe_ings' not in st.session_state:
                    st.session_state.new_recipe_ings = [{"ingredient": None, "quantity": 100.0, "unit": "g"}]
                if not ingredients:
                    st.warning("Aucun ingrédient disponible.")
                else:
                    for idx, row in enumerate(st.session_state.new_recipe_ings):
                        col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 0.5])
                        with col1:
                            ing_names = ["-"] + [i['name'] for i in ingredients]
                            already_selected = [r['ingredient'] for i, r in enumerate(st.session_state.new_recipe_ings) if i != idx and r['ingredient']]
                            available_for_this_row = [n for n in ing_names if n == "-" or n not in already_selected]
                            if row['ingredient'] and row['ingredient'] in available_for_this_row:
                                current_index = available_for_this_row.index(row['ingredient'])
                            elif row['ingredient']:
                                available_for_this_row.insert(1, row['ingredient'])
                                current_index = 1
                            else:
                                current_index = 0
                            selected_ing = st.selectbox("Ingrédient", available_for_this_row, index=current_index, key=f"create_ing_select_{idx}", label_visibility="collapsed")
                            st.session_state.new_recipe_ings[idx]['ingredient'] = selected_ing if selected_ing != "-" else None
                        with col2:
                            qty = st.number_input("Quantité", min_value=0.1, value=float(row['quantity']), step=10.0, key=f"create_ing_qty_{idx}", label_visibility="collapsed")
                            st.session_state.new_recipe_ings[idx]['quantity'] = qty
                        with col3:
                            if selected_ing and selected_ing != "-":
                                ing_obj = next((i for i in ingredients if i['name'] == selected_ing), None)
                                default_unit = ing_obj['unit'] if ing_obj else "g"
                            else:
                                default_unit = row.get('unit', 'g')
                            unit_index = UNITES.index(default_unit) if default_unit in UNITES else 0
                            selected_unit = st.selectbox("Unité", UNITES, index=unit_index, key=f"create_ing_unit_{idx}", label_visibility="collapsed")
                            st.session_state.new_recipe_ings[idx]['unit'] = selected_unit
                        with col4:
                            if len(st.session_state.new_recipe_ings) > 1:
                                if st.button("❌", key=f"remove_create_ing_{idx}"):
                                    st.session_state.new_recipe_ings.pop(idx)
                                    st.rerun()
                    if st.button("➕ Nouvelle ligne", key="add_create_ing_row", use_container_width=True):
                        st.session_state.new_recipe_ings.append({"ingredient": None, "quantity": 100.0, "unit": "g"})
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
                                    ing_obj = next((i for i in ingredients if i['name'] == new_ing['ingredient']), None)
                                    if ing_obj:
                                        supabase.table("recipe_ingredients").insert({
                                            "recipe_id": new_recipe_id,
                                            "ingredient_id": ing_obj['id'],
                                            "quantity": new_ing['quantity'],
                                            "unit": new_ing['unit']
                                        }).execute()
                                        added_count += 1
                            success_msg = f"✅ Recette '{name}' créée avec {added_count} ingrédient(s) !"
                            if added_count == 0:
                                success_msg += "\n💡 Vous pourrez ajouter des ingrédients plus tard."
                            st.success(success_msg)
                            st.session_state.new_recipe_ings = [{"ingredient": None, "quantity": 100.0, "unit": "g"}]
                            st.session_state.new_recipe_instructions = [""]
                            refresh_data()
                        else:
                            st.error("Erreur lors de la création")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

        else:
            if not recipes:
                st.info("Aucune recette à éditer. Créez-en une d'abord !")
            else:
                recipe_names = ["-"] + [r['name'] for r in recipes]
                selected_name = st.selectbox("Recette à modifier", recipe_names, key="edit_recipe_select")
                
                if selected_name == "-":
                    st.info("Sélectionnez une recette à modifier.")
                else:
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
                                            "quantity": ri['quantity'],
                                            "unit": ri.get('unit')
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
                                st.session_state[f'edit_instructions_{recipe["id"]}'] = text_to_instructions(recipe.get('instructions', ''))
                            new_name = st.text_input("Nom", value=recipe['name'], key=f"edit_rname_{recipe['id']}")
                            new_servings = st.number_input("Personnes de base", min_value=1, value=recipe.get('base_servings', 4), key=f"edit_rservings_{recipe['id']}")
                            st.markdown("**Instructions :**")
                            for idx, instruction in enumerate(st.session_state[f'edit_instructions_{recipe["id"]}']):
                                col_instr, col_del_instr = st.columns([5, 1])
                                with col_instr:
                                    st.text_input(f"Instruction {idx + 1}", value=instruction, key=f"edit_instruction_{recipe['id']}_{idx}")
                                    st.session_state[f'edit_instructions_{recipe["id"]}'][idx] = st.session_state[f"edit_instruction_{recipe['id']}_{idx}"]
                                with col_del_instr:
                                    if len(st.session_state[f'edit_instructions_{recipe["id"]}']) > 1:
                                        if st.button("❌", key=f"del_edit_instruction_{recipe['id']}_{idx}"):
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
                                        display_unit = ri.get('unit') or ing['unit']
                                        col1, col2, col3 = st.columns([4, 2, 1])
                                        col1.markdown(f"**{ing['name']}**")
                                        col2.markdown(f"{format_quantity(ri['quantity'])} {display_unit}")
                                        if col3.button("❌", key=f"del_ri_{ri['id']}"):
                                            try:
                                                supabase.table("recipe_ingredients").delete().eq("id", ri['id']).execute()
                                                refresh_data()
                                            except Exception as e:
                                                st.error(f"Erreur : {e}")
                            else:
                                st.info("Aucun ingrédient pour l'instant")
                            
                            st.markdown("**Ajouter des ingrédients :**")
                            existing_ings = [ri['ingredient_id'] for ri in rec_ings]
                            available_ings = [i for i in ingredients if i['id'] not in existing_ings]
                            if available_ings:
                                if f'new_ings_{recipe["id"]}' not in st.session_state:
                                    st.session_state[f'new_ings_{recipe["id"]}'] = [{"ingredient": None, "quantity": 100.0, "unit": "g"}]
                                for idx, row in enumerate(st.session_state[f'new_ings_{recipe["id"]}']):
                                    col1, col2, col3, col4 = st.columns([3, 1.5, 1.5, 0.5])
                                    with col1:
                                        ing_names = ["-"] + [i['name'] for i in available_ings]
                                        already_selected = [r['ingredient'] for i, r in enumerate(st.session_state[f'new_ings_{recipe["id"]}']) if i != idx and r['ingredient']]
                                        available_for_this_row = [n for n in ing_names if n == "-" or n not in already_selected]
                                        if row['ingredient'] and row['ingredient'] in available_for_this_row:
                                            current_index = available_for_this_row.index(row['ingredient'])
                                        elif row['ingredient']:
                                            available_for_this_row.insert(1, row['ingredient'])
                                            current_index = 1
                                        else:
                                            current_index = 0
                                        selected_ing = st.selectbox("Ingrédient", available_for_this_row, index=current_index, key=f"new_ing_select_{recipe['id']}_{idx}", label_visibility="collapsed")
                                        st.session_state[f'new_ings_{recipe["id"]}'][idx]['ingredient'] = selected_ing if selected_ing != "-" else None
                                    with col2:
                                        qty = st.number_input("Quantité", min_value=0.1, value=float(row['quantity']), step=10.0, key=f"new_ing_qty_{recipe['id']}_{idx}", label_visibility="collapsed")
                                        st.session_state[f'new_ings_{recipe["id"]}'][idx]['quantity'] = qty
                                    with col3:
                                        if selected_ing and selected_ing != "-":
                                            ing_obj = next((i for i in available_ings if i['name'] == selected_ing), None)
                                            default_unit = ing_obj['unit'] if ing_obj else "g"
                                        else:
                                            default_unit = row.get('unit', 'g')
                                        unit_index = UNITES.index(default_unit) if default_unit in UNITES else 0
                                        selected_unit = st.selectbox("Unité", UNITES, index=unit_index, key=f"new_ing_unit_{recipe['id']}_{idx}", label_visibility="collapsed")
                                        st.session_state[f'new_ings_{recipe["id"]}'][idx]['unit'] = selected_unit
                                    with col4:
                                        if len(st.session_state[f'new_ings_{recipe["id"]}']) > 1:
                                            if st.button("❌", key=f"remove_new_ing_{recipe['id']}_{idx}"):
                                                st.session_state[f'new_ings_{recipe["id"]}'].pop(idx)
                                                st.rerun()
                                col_add_row, col_save_all = st.columns(2)
                                with col_add_row:
                                    if st.button("➕ Nouvelle ligne", key=f"add_row_{recipe['id']}", use_container_width=True):
                                        st.session_state[f'new_ings_{recipe["id"]}'].append({"ingredient": None, "quantity": 100.0, "unit": "g"})
                                        st.rerun()
                                with col_save_all:
                                    if st.button("💾 Ajouter tous", key=f"save_all_ings_{recipe['id']}", use_container_width=True, type="primary"):
                                        try:
                                            added_count = 0
                                            for new_ing in st.session_state[f'new_ings_{recipe["id"]}']:
                                                if new_ing['ingredient']:
                                                    ing_obj = next((i for i in available_ings if i['name'] == new_ing['ingredient']), None)
                                                    if ing_obj:
                                                        supabase.table("recipe_ingredients").insert({
                                                            "recipe_id": recipe['id'],
                                                            "ingredient_id": ing_obj['id'],
                                                            "quantity": new_ing['quantity'],
                                                            "unit": new_ing['unit']
                                                        }).execute()
                                                        added_count += 1
                                            if added_count > 0:
                                                st.success(f"✅ {added_count} ingrédient(s) ajouté(s) !")
                                                st.session_state[f'new_ings_{recipe["id"]}'] = [{"ingredient": None, "quantity": 100.0, "unit": "g"}]
                                                refresh_data()
                                            else:
                                                st.warning("Sélectionnez au moins un ingrédient")
                                        except Exception as e:
                                            st.error(f"Erreur : {e}")
                            else:
                                st.info("Tous les ingrédients disponibles sont déjà dans cette recette")

    # ============================
    # INGRÉDIENTS
    # ============================
    elif st.session_state.active_tab == "🥕 Ingrédients":
        st.header("Ingrédients")

        if st.button("➕ Ajouter un ingrédient", key="btn_show_add_ing", use_container_width=True):
            st.session_state.show_add_ing = True

        if st.session_state.get('show_add_ing', False):
            with st.form("add_ingredient_form"):
                st.subheader("Nouvel ingrédient")
                name = st.text_input("Nom *", key="new_ing_name")
                col1, col2 = st.columns(2)
                unit = col1.selectbox("Unité", ["-"] + UNITES, key="new_ing_unit")
                category = col2.selectbox("Rayon", ["-"] + RAYONS, key="new_ing_category")
                col3, col4 = st.columns(2)
                exclude = col3.checkbox("🚪 Fond de placard", key="new_ing_exclude")
                recurrent = col4.checkbox("🔁 Récurrent", key="new_ing_recurrent")
                st.markdown("---")
                col5, col6 = st.columns(2)
                unite_liste = col5.selectbox("Unité liste de courses", ["-"] + UNITES, key="new_ing_unite_liste")
                poids_piece = col6.number_input("Poids d'une pièce (en grammes)", min_value=0.0, value=0.0, step=10.0, key="new_ing_poids_piece")
                
                col_submit, col_cancel = st.columns(2)
                with col_submit:
                    submitted = st.form_submit_button("Enregistrer", use_container_width=True)
                with col_cancel:
                    cancelled = st.form_submit_button("Annuler", use_container_width=True)
                
                if submitted:
                    if not name.strip():
                        st.error("Nom obligatoire")
                    elif unit == "-" or category == "-":
                        st.error("Sélectionnez une unité et un rayon")
                    else:
                        try:
                            data_to_insert = {
                                "name": name.strip().capitalize(),
                                "unit": unit,
                                "category": category,
                                "exclude_from_list": exclude,
                                "is_recurrent": recurrent,
                                "poids_piece_g": poids_piece if poids_piece > 0 else None,
                                "unite_liste_courses": unite_liste if unite_liste != "-" else None
                            }
                            supabase.table("ingredients").insert(data_to_insert).execute()
                            st.session_state.show_add_ing = False
                            refresh_data()
                        except Exception as e:
                            st.error(f"Erreur : {e}")
                
                if cancelled:
                    st.session_state.show_add_ing = False
                    st.rerun()

        ingredients = sort_list_by_name(st.session_state.data.get('ingredients', []))
        
        if ingredients:
            has_poids = 'poids_piece_g' in ingredients[0] if ingredients else False
            has_unite_liste = 'unite_liste_courses' in ingredients[0] if ingredients else False
            
            columns_to_show = ['name', 'unit', 'category', 'exclude_from_list', 'is_recurrent']
            column_config = {
                "name": "Nom",
                "unit": "Unité",
                "category": "Rayon",
                "exclude_from_list": st.column_config.CheckboxColumn("Fond de placard"),
                "is_recurrent": st.column_config.CheckboxColumn("Récurrent")
            }
            if has_poids:
                columns_to_show.append('poids_piece_g')
                column_config["poids_piece_g"] = st.column_config.NumberColumn("Poids (g/pièce)", format="%.0f")
            if has_unite_liste:
                columns_to_show.append('unite_liste_courses')
                column_config["unite_liste_courses"] = "Unité liste"
            
            df_display = pd.DataFrame(ingredients)[columns_to_show]
            st.dataframe(df_display, column_config=column_config, hide_index=True, use_container_width=True)
            
            with st.expander("✏️ Modifier un ingrédient"):
                ing_names = ["-"] + [i['name'] for i in ingredients]
                selected_ing_name = st.selectbox("Sélectionner", ing_names, key="select_ing_to_edit")
                
                if selected_ing_name == "-":
                    st.info("Sélectionnez un ingrédient à modifier.")
                else:
                    selected_ing = next((i for i in ingredients if i['name'] == selected_ing_name), None)
                    
                    if selected_ing:
                        with st.form(f"edit_ing_form_{selected_ing['id']}"):
                            new_name = st.text_input("Nom", value=selected_ing['name'], key=f"edit_name_{selected_ing['id']}")
                            col1, col2 = st.columns(2)
                            new_unit = col1.selectbox("Unité", UNITES, index=UNITES.index(selected_ing['unit']) if selected_ing['unit'] in UNITES else 0, key=f"edit_unit_{selected_ing['id']}")
                            new_category = col2.selectbox("Rayon", RAYONS, index=RAYONS.index(selected_ing['category']) if selected_ing['category'] in RAYONS else 0, key=f"edit_cat_{selected_ing['id']}")
                            col3, col4 = st.columns(2)
                            new_exclude = col3.checkbox("🚪 Fond de placard", value=selected_ing.get('exclude_from_list', False), key=f"edit_exclude_{selected_ing['id']}")
                            new_recurrent = col4.checkbox("🔁 Récurrent", value=selected_ing.get('is_recurrent', False), key=f"edit_recurrent_{selected_ing['id']}")
                            st.markdown("---")
                            col5, col6 = st.columns(2)
                            current_unite_liste = selected_ing.get('unite_liste_courses')
                            unite_liste_index = UNITES.index(current_unite_liste) + 1 if current_unite_liste in UNITES else 0
                            new_unite_liste = col5.selectbox("Unité liste de courses", ["-"] + UNITES, index=unite_liste_index, key=f"edit_unite_liste_{selected_ing['id']}")
                            new_poids = col6.number_input("Poids d'une pièce (en grammes)", min_value=0.0, value=float(selected_ing.get('poids_piece_g') or 0) if selected_ing.get('poids_piece_g') else 0.0, step=10.0, key=f"edit_poids_{selected_ing['id']}")
                            
                            col_save, col_del = st.columns(2)
                            with col_save:
                                save_clicked = st.form_submit_button("💾 Sauvegarder", use_container_width=True)
                            with col_del:
                                delete_clicked = st.form_submit_button("🗑️ Supprimer", use_container_width=True)
                            
                            if save_clicked:
                                try:
                                    update_data = {
                                        "name": new_name.strip().capitalize(),
                                        "unit": new_unit,
                                        "category": new_category,
                                        "exclude_from_list": new_exclude,
                                        "is_recurrent": new_recurrent,
                                        "unite_liste_courses": new_unite_liste if new_unite_liste != "-" else None
                                    }
                                    if 'poids_piece_g' in selected_ing:
                                        update_data["poids_piece_g"] = new_poids if new_poids > 0 else None
                                    
                                    supabase.table("ingredients").update(update_data).eq("id", selected_ing['id']).execute()
                                    
                                    # Mettre à jour les recettes [Ing] associées
                                    if new_name.strip().capitalize() != selected_ing['name']:
                                        supabase.table("recipes").update({
                                            "name": f"[Ing] {new_name.strip().capitalize()}"
                                        }).eq("name", f"[Ing] {selected_ing['name']}").execute()
                                    
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
