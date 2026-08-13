import streamlit as st
import datetime
import base64
from fpdf import FPDF
from supabase import create_client, Client

# --- CONFIGURATION SUPABASE (SECRETS) ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except KeyError:
    SUPABASE_URL = "https://votre-id-projet.supabase.co"
    SUPABASE_KEY = "votre-cle-anon"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Gestionnaire de Menus", layout="wide", page_icon="🍽️")
st.title("🍽️ Planificateur de Menus & PDF")

# --- LISTE DES JOURS DU SAMEDI AU VENDREDI ---
DAYS = ["Samedi", "Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]

# --- FONCTIONS DE CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=30)
def load_recipes():
    try:
        res = supabase.table("recipes").select("id, name").order("name").execute()
        return res.data or []
    except Exception:
        return []

@st.cache_data(ttl=30)
def load_ingredients():
    try:
        res = supabase.table("ingredients").select("id, name").order("name").execute()
        return res.data or []
    except Exception:
        return []

@st.cache_data(ttl=30)
def load_recurring_items():
    try:
        res = supabase.table("recurring_items").select("id, name").order("name").execute()
        return [r["name"] for r in res.data] if res.data else ["Sacs poubelle", "Papier toilette", "Éponges", "Lessive"]
    except Exception:
        return ["Sacs poubelle", "Papier toilette", "Éponges", "Lessive"]

@st.cache_data(ttl=30)
def load_planned_meals():
    try:
        res = supabase.table("planned_meals").select("*, recipes(name), ingredients(name)").execute()
        return res.data or []
    except Exception:
        return []

# --- GENERATEUR PDF (FPDF2) ---
class MenuPDF(FPDF):
    def __init__(self, start_date_str, end_date_str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str

    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 10, f"Menu du {self.start_date_str} au {self.end_date_str}", border=0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(3)

def generate_pdf(planning, shopping, recurring, days_list, start_str, end_str):
    pdf = MenuPDF(start_str, end_str)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    top_y = 25
    total_h = 255

    # PARTIE GAUCHE (2/3 de la largeur : 120 mm)
    left_x = 10
    left_w = 120
    day_h = total_h / 7

    for i, day in enumerate(days_list):
        y_pos = top_y + (i * day_h)
        
        pdf.rect(left_x, y_pos, left_w, day_h - 2)
        
        pdf.set_xy(left_x + 3, y_pos + 2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(left_w - 6, 5, day)

        pdf.set_font("Helvetica", "", 9)
        midi_txt = planning.get((day, "Midi"), "-")
        soir_txt = planning.get((day, "Soir"), "-")

        pdf.set_xy(left_x + 5, y_pos + 9)
        pdf.cell(left_w - 10, 5, f"Midi : {midi_txt}")
        
        pdf.set_xy(left_x + 5, y_pos + 16)
        pdf.cell(left_w - 10, 5, f"Soir : {soir_txt}")

    # PARTIE DROITE (1/3 de la largeur : 65 mm)
    right_x = 135
    right_w = 65

    # 1. Liste de courses
    list_h = 135
    pdf.rect(right_x, top_y, right_w, list_h)
    
    pdf.set_xy(right_x + 2, top_y + 2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(right_w - 4, 6, "Liste de courses", align="C")
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(right_x + 3, top_y + 10)
    courses_txt = "\n".join([f"• {item}" for item in shopping]) if shopping else "Aucun article"
    pdf.multi_cell(right_w - 6, 5, courses_txt)

    # 2. Produits récurrents
    rec_y = top_y + list_h + 4
    rec_h = total_h - list_h - 4
    pdf.rect(right_x, rec_y, right_w, rec_h)

    pdf.set_xy(right_x + 2, rec_y + 2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(right_w - 4, 6, "Produits récurrents", align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(right_x + 3, rec_y + 10)
    recurring_txt = "\n".join([f"• {item}" for item in recurring]) if recurring else "Aucun produit"
    pdf.multi_cell(right_w - 6, 5, recurring_txt)

    return bytes(pdf.output())

# --- NAVIGATION PAR ONGLETS ---
tab_planning, tab_recipes, tab_ingredients, tab_recurring = st.tabs([
    "📅 Planning & PDF", 
    "📖 Gestion des Recettes", 
    "🥬 Ingrédients Simples", 
    "🔁 Produits Récurrents"
])

# =============================================================================
# ONGLET 1 : PLANNING & GÉNÉRATION PDF
# =============================================================================
with tab_planning:
    col_date, _ = st.columns([1, 2])
    with col_date:
        start_date = st.date_input("Date du samedi (début du menu)", datetime.date.today(), key="start_date_picker")
    
    end_date = start_date + datetime.timedelta(days=6)

    start_str = start_date.strftime("%d/%m/%Y")
    end_str = end_date.strftime("%d/%m/%Y")

    st.subheader(f"📌 Planification du {start_str} au {end_str}")

    meal_types = ["Midi", "Soir"]

    recipes = load_recipes()
    ingredients = load_ingredients()

    recipe_map = {r["name"]: r["id"] for r in recipes if r and "name" in r}
    ingredient_map = {i["name"]: i["id"] for i in ingredients if i and "name" in i}

    # Choix du type d'élément (Hors du formulaire pour la réactivité immédiate)
    source_type = st.radio(
        "Élément à ajouter :", 
        ["Recette", "Ingrédient simple"], 
        horizontal=True,
        key="meal_source_type"
    )

    with st.form("add_meal_form"):
        c1, c2, c3, c4 = st.columns([2, 2, 4, 2])
        with c1:
            selected_day = st.selectbox("Jour", DAYS)
        with c2:
            selected_type = st.selectbox("Repas", meal_types)
        with c3:
            if source_type == "Recette":
                recipe_names = ["-- Aucune --"] + sorted(list(recipe_map.keys()))
                chosen_item = st.selectbox("Choisir la recette", recipe_names)
            else:
                ingredient_names = ["-- Aucun --"] + sorted(list(ingredient_map.keys()))
                chosen_item = st.selectbox("Choisir l'ingrédient simple", ingredient_names)
        with c4:
            nb_persons = st.number_input("Pers.", min_value=1, max_value=20, value=4, step=1)

        submit_meal = st.form_submit_button("Affecter au menu")

    if submit_meal:
        recipe_id = recipe_map.get(chosen_item) if source_type == "Recette" and chosen_item != "-- Aucune --" else None
        ingredient_id = ingredient_map.get(chosen_item) if source_type == "Ingrédient simple" and chosen_item != "-- Aucun --" else None

        if recipe_id or ingredient_id:
            try:
                # Supprime le repas déjà existant sur ce créneau
                supabase.table("planned_meals").delete().eq("day", selected_day).eq("meal_type", selected_type).execute()
                # Insère le nouveau repas avec le nombre de personnes
                supabase.table("planned_meals").insert({
                    "day": selected_day,
                    "meal_type": selected_type,
                    "recipe_id": recipe_id,
                    "ingredient_id": ingredient_id,
                    "nb_persons": nb_persons
                }).execute()
                st.success(f"Repas mis à jour pour {selected_day} ({selected_type}) - {nb_persons} pers.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erreur lors de la mise à jour : {e}")

    # Récupération et traitement des données planifiées
    planned = load_planned_meals()
    planning_dict = {}
    shopping_list = []

    for p in planned:
        if not isinstance(p, dict):
            continue
        day = p.get("day")
        m_type = p.get("meal_type")
        persons = p.get("nb_persons") or 4
        
        item_name = None
        if p.get("recipes"):
            item_name = p["recipes"].get("name")
        elif p.get("ingredients"):
            item_name = p["ingredients"].get("name")
            
        if item_name:
            # Formatage pour l'affichage (ex: Lasagnes (4 pers.))
            display_str = f"{item_name} ({persons} pers.)"
            planning_dict[(day, m_type)] = display_str
            shopping_list.append(item_name)

    shopping_list = sorted(list(set(shopping_list)))
    recurring_items = load_recurring_items()

    st.divider()

    if st.button("📄 Générer et ouvrir le PDF du menu", type="primary"):
        pdf_bytes = generate_pdf(planning_dict, shopping_list, recurring_items, DAYS, start_str, end_str)
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        
        html_button = f'''
            <a href="data:application/pdf;base64,{b64_pdf}" target="_blank" style="
                display: inline-block;
                padding: 12px 24px;
                color: white;
                background-color: #007bff;
                text-decoration: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                margin-top: 15px;">
                🔗 Cliquez ici pour ouvrir le PDF dans un nouvel onglet
            </a>
        '''
        st.markdown(html_button, unsafe_allow_html=True)

# =============================================================================
# ONGLET 2 : GESTION DES RECETTES
# =============================================================================
with tab_recipes:
    st.subheader("📖 Ajouter une nouvelle recette")
    with st.form("add_recipe_form"):
        new_recipe_name = st.text_input("Nom de la recette")
        submit_recipe = st.form_submit_button("Enregistrer la recette")

        if submit_recipe:
            if new_recipe_name.strip():
                try:
                    supabase.table("recipes").insert({"name": new_recipe_name.strip()}).execute()
                    st.success(f"Recette '{new_recipe_name}' ajoutée !")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
            else:
                st.warning("Saisissez un nom de recette.")

    st.divider()
    st.subheader("Liste des recettes enregistrées")
    current_recipes = load_recipes()
    if current_recipes:
        for r in current_recipes:
            st.text(f"• {r.get('name')}")
    else:
        st.info("Aucune recette enregistrée pour le moment.")

# =============================================================================
# ONGLET 3 : INGRÉDIENTS SIMPLES
# =============================================================================
with tab_ingredients:
    st.subheader("🥬 Ajouter un ingrédient simple")
    st.caption("Ces ingrédients serviront pour les repas libres (ex: Salade, Œufs sur le plat).")
    
    with st.form("add_ingredient_form"):
        new_ing_name = st.text_input("Nom de l'ingrédient")
        submit_ing = st.form_submit_button("Enregistrer l'ingrédient")

        if submit_ing:
            if new_ing_name.strip():
                try:
                    supabase.table("ingredients").insert({"name": new_ing_name.strip()}).execute()
                    st.success(f"Ingrédient '{new_ing_name}' ajouté !")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur : {e}")
            else:
                st.warning("Saisissez un nom d'ingrédient.")

    st.divider()
    st.subheader("Liste des ingrédients simples")
    current_ingredients = load_ingredients()
    if current_ingredients:
        for ing in current_ingredients:
            st.text(f"• {ing.get('name')}")
    else:
        st.info("Aucun ingrédient enregistré.")

# =============================================================================
# ONGLET 4 : PRODUITS RÉCURRENTS
# =============================================================================
with tab_recurring:
    st.subheader("🔁 Gestion des produits récurrents")
    st.caption("Ces produits apparaîtront en bas à droite sur l'impression PDF.")

    with st.form("add_recurring_form"):
        new_rec_name = st.text_input("Nom du produit récurrent (ex: Papier toilette, Lessive)")
        submit_rec = st.form_submit_button("Ajouter à la liste")

        if submit_rec:
            if new_rec_name.strip():
                try:
                    supabase.table("recurring_items").insert({"name": new_rec_name.strip()}).execute()
                    st.success(f"Produit '{new_rec_name}' ajouté !")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur ou table 'recurring_items' non créée dans Supabase ({e})")
            else:
                st.warning("Saisissez un nom d'article.")

    st.divider()
    st.subheader("Produits récurrents actuels")
    curr_items = load_recurring_items()
    for item in curr_items:
        st.text(f"• {item}")
