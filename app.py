import streamlit as st
import datetime
import base64
from fpdf import FPDF
from supabase import create_client, Client

# --- CONFIGURATION SUPABASE ---
# --- CONFIGURATION SUPABASE ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except KeyError:
    # Option de secours si les secrets ne sont pas définis
    SUPABASE_URL = "https://ton-id-projet.supabase.co"
    SUPABASE_KEY = "ta-cle-api-anon"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=30)
def load_recipes():
    res = supabase.table("recipes").select("*").execute()
    return res.data or []

@st.cache_data(ttl=30)
def load_ingredients():
    res = supabase.table("ingredients").select("*").order("name").execute()
    return res.data or []

@st.cache_data(ttl=30)
def load_planned_meals():
    res = supabase.table("planned_meals").select("*, recipes(title), ingredients(name)").execute()
    return res.data or []

# --- CALCUL DES DATES DU MENU ---
col_date, _ = st.columns([1, 2])
with col_date:
    start_date = st.date_input("Date de début du menu", datetime.date.today())
end_date = start_date + datetime.timedelta(days=7)

start_str = start_date.strftime("%d/%m/%Y")
end_str = end_date.strftime("%d/%m/%Y")

# --- BANDEAU LATÉRAL : CRÉER UN INGRÉDIENT SIMPLE ---
with st.sidebar:
    st.header("➕ Ajouter un ingrédient simple")
    new_ing_name = st.text_input("Nom de l'ingrédient (ex: Salade, Œufs)")
    if st.button("Enregistrer l'ingrédient"):
        if new_ing_name.strip():
            try:
                supabase.table("ingredients").insert({"name": new_ing_name.strip()}).execute()
                st.success(f"Ingrédient '{new_ing_name}' ajouté !")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error("Cet ingrédient existe déjà ou une erreur est survenue.")
        else:
            st.warning("Veuillez saisir un nom.")

# --- PLANIFICATION DES REPAS ---
st.subheader("📌 Planification de la semaine")

days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
meal_types = ["Midi", "Soir"]

recipes = load_recipes()
ingredients = load_ingredients()

recipe_map = {r["title"]: r["id"] for r in recipes}
ingredient_map = {i["name"]: i["id"] for i in ingredients}

with st.form("add_meal_form"):
    c1, c2, c3, c4 = st.columns([2, 2, 3, 4])
    
    with c1:
        selected_day = st.selectbox("Jour", days)
    with c2:
        selected_type = st.selectbox("Repas", meal_types)
    with c3:
        source_type = st.radio("Type de repas", ["Recette", "Ingrédient simple"], horizontal=True)
    with c4:
        if source_type == "Recette":
            chosen_item = st.selectbox("Choisir la recette", ["-- Aucune --"] + list(recipe_map.keys()))
        else:
            chosen_item = st.selectbox("Choisir l'ingrédient", ["-- Aucun --"] + list(ingredient_map.keys()))

    submit_meal = st.form_submit_button("Affecter au menu")

if submit_meal:
    recipe_id = None
    ingredient_id = None

    if source_type == "Recette" and chosen_item != "-- Aucune --":
        recipe_id = recipe_map.get(chosen_item)
    elif source_type == "Ingrédient simple" and chosen_item != "-- Aucun --":
        ingredient_id = ingredient_map.get(chosen_item)

    if recipe_id or ingredient_id:
        # Supprime le repas existant pour ce créneau
        supabase.table("planned_meals").delete().eq("day", selected_day).eq("meal_type", selected_type).execute()
        # Insertion du nouveau repas
        supabase.table("planned_meals").insert({
            "day": selected_day,
            "meal_type": selected_type,
            "recipe_id": recipe_id,
            "ingredient_id": ingredient_id
        }).execute()

        st.success(f"Repas mis à jour pour {selected_day} ({selected_type})")
        st.cache_data.clear()
        st.rerun()

# --- TRAITEMENT DES DONNÉES PLANIFIÉES ET DE LA LISTE DE COURSES ---
planned = load_planned_meals()
planning_dict = {}
shopping_list = []

for p in planned:
    day = p["day"]
    m_type = p["meal_type"]
    
    if p.get("recipes"):
        title = p["recipes"]["title"]
        planning_dict[(day, m_type)] = title
        # On peut aussi ajouter le titre de la recette ou ses sous-ingrédients
        shopping_list.append(title)
    elif p.get("ingredients"):
        title = p["ingredients"]["name"]
        planning_dict[(day, m_type)] = title
        # L'ingrédient simple s'ajoute directement à la liste de courses !
        shopping_list.append(title)

# Suppression des doublons pour la liste de courses
shopping_list = sorted(list(set(shopping_list)))

# Produits récurrents (exemples modifiables)
recurring_items = ["Sacs poubelle", "Papier toilette", "Éponges", "Lessive"]

# --- GENERATEUR PDF SUR-MESURE (FPDF2) ---
class MenuPDF(FPDF):
    def __init__(self, start_date_str, end_date_str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str

    def header(self):
        self.set_font("Helvetica", "B", 15)
        # Titre centré au sommet de la page
        self.cell(0, 10, f"Menu du {self.start_date_str} au {self.end_date_str}", border=0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(3)

def generate_pdf(planning, shopping, recurring, start_str, end_str):
    pdf = MenuPDF(start_str, end_str)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    top_y = 25
    total_h = 255  # Hauteur disponible sur la page A4

    # -------------------------------------------------------------
    # PARTE GAUCHE (2/3 de la largeur : 120 mm)
    # -------------------------------------------------------------
    left_x = 10
    left_w = 120
    day_h = total_h / 7  # Hauteur uniforme pour chaque jour (~36.4 mm)

    for i, day in enumerate(days):
        y_pos = top_y + (i * day_h)
        
        # Encadrement du bloc du jour
        pdf.rect(left_x, y_pos, left_w, day_h - 2)
        
        # Titre du jour
        pdf.set_xy(left_x + 3, y_pos + 2)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(left_w - 6, 5, day)

        # Repas Midi & Soir
        pdf.set_font("Helvetica", "", 9)
        midi_txt = planning.get((day, "Midi"), "-")
        soir_txt = planning.get((day, "Soir"), "-")

        pdf.set_xy(left_x + 5, y_pos + 9)
        pdf.cell(left_w - 10, 5, f"Midi : {midi_txt}")
        
        pdf.set_xy(left_x + 5, y_pos + 16)
        pdf.cell(left_w - 10, 5, f"Soir : {soir_txt}")

    # -------------------------------------------------------------
    # PARTIE DROITE (1/3 de la largeur : 65 mm)
    # -------------------------------------------------------------
    right_x = 135
    right_w = 65

    # 1. Liste de courses (Haut du tiers droit)
    list_h = 135
    pdf.rect(right_x, top_y, right_w, list_h)
    
    pdf.set_xy(right_x + 2, top_y + 2)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(right_w - 4, 6, "Liste de courses", align="C")
    
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(right_x + 3, top_y + 10)
    courses_txt = "\n".join([f"• {item}" for item in shopping]) if shopping else "Aucun article"
    pdf.multi_cell(right_w - 6, 5, courses_txt)

    # 2. Produits récurrents (Bas du tiers droit)
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

# --- AFFICHAGE & GÉNÉRATION PDF ---
st.divider()

if st.button("📄 Générer et ouvrir le PDF du menu", type="primary"):
    pdf_bytes = generate_pdf(planning_dict, shopping_list, recurring_items, start_str, end_str)
    
    # Encode le PDF en base64
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
    
    # Bouton HTML pour forcer l'ouverture dans un nouvel onglet sans téléchargement direct
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
