import streamlit as st
import streamlit.components.v1 as components
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

# --- FONCTION DE NETTOYAGE UNICODE POUR FPDF ---
def clean_pdf_text(text: str) -> str:
    """Nettoie le texte pour éviter les erreurs d'encodage FPDF avec Helvetica."""
    if not text:
        return ""
    replacements = {
        "•": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-"
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")

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
        res = supabase.table("planned_meals").select("id, day, meal_type, nb_persons, recipes(name), ingredients(name)").execute()
        return res.data or []
    except Exception:
        return []

# --- GÉNÉRATEUR PDF AMÉLIORÉ (FPDF2) ---
class MenuPDF(FPDF):
    def __init__(self, start_date_str, end_date_str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.start_date_str = start_date_str
        self.end_date_str = end_date_str

    def header(self):
        # Bandeau de titre supérieur
        self.set_fill_color(46, 125, 50)  # Vert Forêt
        self.rounded_rect(10, 8, 190, 14, 3, style="F")
        
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 12)
        self.set_xy(10, 8)
        self.cell(190, 14, clean_pdf_text(f"MENU ET COURSES DU {self.start_date_str} AU {self.end_date_str}"), align="C")
        self.ln(18)

def generate_pdf(planning, shopping, recurring, days_list, start_str, end_str):
    pdf = MenuPDF(start_str, end_str)
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    top_y = 26
    total_h = 258

    # Palette de couleurs
    PRIMARY_R, PRIMARY_G, PRIMARY_B = 46, 125, 50      # Vert Forêt
    TEXT_DARK_R, TEXT_DARK_G, TEXT_DARK_B = 30, 41, 59 # Slate Foncé
    BORDER_R, BORDER_G, BORDER_B = 203, 213, 225        # Gris bordures
    BG_LIGHT_R, BG_LIGHT_G, BG_LIGHT_B = 248, 250, 252 # Fond cartes

    # --- PARTIE GAUCHE (Planning 120 mm) ---
    left_x = 10
    left_w = 120
    day_h = (total_h - 5) / 7

    for i, day in enumerate(days_list):
        y_pos = top_y + (i * day_h)

        # Fond de la carte du jour
        pdf.set_fill_color(BG_LIGHT_R, BG_LIGHT_G, BG_LIGHT_B)
        pdf.set_draw_color(BORDER_R, BORDER_G, BORDER_B)
        pdf.rounded_rect(left_x, y_pos, left_w, day_h - 3, 2.5, style="DF")

        # Bandeau du nom du jour
        pdf.set_fill_color(232, 245, 233)  # Vert pastel
        pdf.rounded_rect(left_x, y_pos, left_w, 7, 2, style="FD")

        pdf.set_xy(left_x + 4, y_pos + 1)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(PRIMARY_R, PRIMARY_G, PRIMARY_B)
        pdf.cell(left_w - 8, 5, clean_pdf_text(day.upper()))

        # Contenu Repas
        pdf.set_text_color(TEXT_DARK_R, TEXT_DARK_G, TEXT_DARK_B)
        
        midi_txt = clean_pdf_text(planning.get((day, "Midi"), "-"))
        soir_txt = clean_pdf_text(planning.get((day, "Soir"), "-"))

        # Ligne Midi
        pdf.set_xy(left_x + 4, y_pos + 8.5)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(12, 4.5, "Midi :")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(left_w - 20, 4.5, midi_txt)

        # Ligne Soir
        pdf.set_xy(left_x + 4, y_pos + 18)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(12, 4.5, "Soir :")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.multi_cell(left_w - 20, 4.5, soir_txt)

    # --- PARTIE DROITE (Courses & Récurrents 65 mm) ---
    right_x = 135
    right_w = 65

    # 1. Liste de courses
    list_h = 140
    pdf.set_fill_color(BG_LIGHT_R, BG_LIGHT_G, BG_LIGHT_B)
    pdf.set_draw_color(BORDER_R, BORDER_G, BORDER_B)
    pdf.rounded_rect(right_x, top_y, right_w, list_h, 2.5, style="DF")

    # En-tête Liste de courses
    pdf.set_fill_color(PRIMARY_R, PRIMARY_G, PRIMARY_B)
    pdf.rounded_rect(right_x, top_y, right_w, 8, 2, style="F")
    pdf.set_xy(right_x, top_y + 1)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(right_w, 6, "LISTE DE COURSES", align="C")

    # Contenu Ingrédients
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(TEXT_DARK_R, TEXT_DARK_G, TEXT_DARK_B)
    pdf.set_xy(right_x + 4, top_y + 11)
    courses_txt = "\n".join([f"- {clean_pdf_text(item)}" for item in shopping]) if shopping else "Aucun article"
    pdf.multi_cell(right_w - 8, 4.5, courses_txt)

    # 2. Produits récurrents
    rec_y = top_y + list_h + 4
    rec_h = total_h - list_h - 4
    pdf.set_fill_color(BG_LIGHT_R, BG_LIGHT_G, BG_LIGHT_B)
    pdf.set_draw_color(BORDER_R, BORDER_G, BORDER_B)
    pdf.rounded_rect(right_x, rec_y, right_w, rec_h, 2.5, style="DF")

    # En-tête Récurrents
    pdf.set_fill_color(100, 116, 139)  # Gris ardoise
    pdf.rounded_rect(right_x, rec_y, right_w, 7, 2, style="F")
    pdf.set_xy(right_x, rec_y + 1)
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(right_w, 5, "PRODUITS RÉCURRENTS", align="C")

    # Contenu Produits Récurrents
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(TEXT_DARK_R, TEXT_DARK_G, TEXT_DARK_B)
    pdf.set_xy(right_x + 4, rec_y + 9)
    recurring_txt = "\n".join([f"- {clean_pdf_text(item)}" for item in recurring]) if recurring else "Aucun produit"
    pdf.multi_cell(right_w - 8, 4.5, recurring_txt)

    return bytes(pdf.output())

# --- NAVIGATION PAR ONGLETS ---
tab_planning, tab_recipes, tab_ingredients, tab_recurring = st.tabs([
    "📅 Planning & PDF", 
    "📖 Gestion des Recettes", 
    "🥬 Ingrédients Simples", 
    "🔁 Produits Récurrents"
])

# =============================================================================
# ONGLET 1 : PLANNING PAR CADRES JOURNALIERS & GÉNÉRATION PDF
# =============================================================================
with tab_planning:
    col_d1, _ = st.columns([1, 2])
    with col_d1:
        start_date = st.date_input("Date du samedi (début du menu)", datetime.date.today(), key="start_date_picker")
    
    end_date = start_date + datetime.timedelta(days=6)
    start_str = start_date.strftime("%d/%m/%Y")
    end_str = end_date.strftime("%d/%m/%Y")

    st.subheader(f"📌 Planning de la semaine ({start_str} au {end_str})")

    # Chargement des référentiels
    recipes = load_recipes()
    ingredients = load_ingredients()
    recipe_map = {r["name"]: r["id"] for r in recipes if r and "name" in r}
    ingredient_map = {i["name"]: i["id"] for i in ingredients if i and "name" in i}

    # Chargement et structuration des repas planifiés
    planned = load_planned_meals()
    planning_data = {}  # Clé: (jour, meal_type) -> Liste d'objets
    shopping_list = []

    for p in planned:
        if not isinstance(p, dict):
            continue
        item_id = p.get("id")
        day = p.get("day")
        m_type = p.get("meal_type")
        persons = p.get("nb_persons") or 4
        
        item_name = None
        if p.get("recipes") and isinstance(p["recipes"], dict):
            item_name = p["recipes"].get("name")
        elif p.get("ingredients") and isinstance(p["ingredients"], dict):
            item_name = p["ingredients"].get("name")
            
        if item_name and day and m_type:
            key = (day, m_type)
            if key not in planning_data:
                planning_data[key] = []
            planning_data[key].append({
                "id": item_id,
                "name": item_name,
                "persons": persons
            })
            shopping_list.append(item_name)

    shopping_list = sorted(list(set(shopping_list)))
    recurring_items = load_recurring_items()

    # Option de réinitialisation globale
    with st.expander("⚙️ Option : Réinitialiser toute la semaine"):
        if st.button("🗑️ Vider entièrement le planning de la semaine"):
            try:
                supabase.table("planned_meals").delete().neq("day", "").execute()
                st.success("Le planning a été entièrement vidé.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erreur : {e}")

    # --- AFFICHAGE DE 1 CADRE PAR JOUR ---
    for day in DAYS:
        with st.container(border=True):
            st.markdown(f"### 📅 {day}")
            
            col_midi, col_soir = st.columns(2)
            
            # --- CADRE / BLOC MIDI ---
            with col_midi:
                st.markdown("#### ☀️ Midi")
                midi_items = planning_data.get((day, "Midi"), [])
                if midi_items:
                    for item in midi_items:
                        c_txt, c_del = st.columns([5, 1])
                        with c_txt:
                            st.write(f"• **{item['name']}** ({item['persons']} pers.)")
                        with c_del:
                            if st.button("🗑️", key=f"del_{item['id']}", help=f"Supprimer {item['name']}"):
                                supabase.table("planned_meals").delete().eq("id", item["id"]).execute()
                                st.cache_data.clear()
                                st.rerun()
                else:
                    st.caption("Aucun élément")

            # --- CADRE / BLOC SOIR ---
            with col_soir:
                st.markdown("#### 🌙 Soir")
                soir_items = planning_data.get((day, "Soir"), [])
                if soir_items:
                    for item in soir_items:
                        c_txt, c_del = st.columns([5, 1])
                        with c_txt:
                            st.write(f"• **{item['name']}** ({item['persons']} pers.)")
                        with c_del:
                            if st.button("🗑️", key=f"del_{item['id']}", help=f"Supprimer {item['name']}"):
                                supabase.table("planned_meals").delete().eq("id", item["id"]).execute()
                                st.cache_data.clear()
                                st.rerun()
                else:
                    st.caption("Aucun élément")

            # --- FORMULAIRE D'AJOUT POUR CE JOUR ---
            with st.expander(f"➕ Ajouter un élément au menu de {day}"):
                source_type = st.radio(
                    "Élément à ajouter :",
                    ["Recette", "Ingrédient simple"],
                    horizontal=True,
                    key=f"source_{day}"
                )
                
                with st.form(key=f"form_add_{day}"):
                    c1, c2, c3 = st.columns([2, 4, 2])
                    with c1:
                        m_type = st.selectbox("Repas", ["Midi", "Soir"], key=f"mtype_{day}")
                    with c2:
                        if source_type == "Recette":
                            names_list = ["-- Aucune --"] + sorted(list(recipe_map.keys()))
                            chosen_name = st.selectbox("Choisir la recette", names_list, key=f"choice_{day}")
                        else:
                            names_list = ["-- Aucun --"] + sorted(list(ingredient_map.keys()))
                            chosen_name = st.selectbox("Choisir l'ingrédient", names_list, key=f"choice_{day}")
                    with c3:
                        nb_pers = st.number_input("Pers.", min_value=1, max_value=20, value=4, step=1, key=f"np_{day}")

                    submit_btn = st.form_submit_button(f"Ajouter à {day}")

                if submit_btn:
                    recipe_id = recipe_map.get(chosen_name) if source_type == "Recette" and chosen_name != "-- Aucune --" else None
                    ingredient_id = ingredient_map.get(chosen_name) if source_type == "Ingrédient simple" and chosen_name != "-- Aucun --" else None

                    if recipe_id or ingredient_id:
                        try:
                            supabase.table("planned_meals").insert({
                                "day": day,
                                "meal_type": m_type,
                                "recipe_id": recipe_id,
                                "ingredient_id": ingredient_id,
                                "nb_persons": nb_pers
                            }).execute()
                            st.success(f"Ajouté avec succès pour {day} ({m_type}) !")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de l'enregistrement : {e}")
                    else:
                        st.warning("Veuillez sélectionner un élément valide dans la liste.")

    st.divider()

    # --- GÉNÉRATION DU PDF ---
    pdf_planning_dict = {}
    for (d, mt), items_list in planning_data.items():
        formatted_list = [f"{it['name']} ({it['persons']}p)" for it in items_list]
        pdf_planning_dict[(d, mt)] = " + ".join(formatted_list)

    if st.button("📄 Générer le PDF du menu", type="primary"):
        pdf_bytes = generate_pdf(pdf_planning_dict, shopping_list, recurring_items, DAYS, start_str, end_str)
        b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

        # Bouton JavaScript pour ouvrir dans un nouvel onglet
        js_code = f"""
            <button id="open-pdf-btn" style="
                display: inline-block;
                padding: 12px 24px;
                color: white;
                background-color: #2E7D32;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
                cursor: pointer;">
                🔗 Cliquer ici pour ouvrir le PDF dans un nouvel onglet
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
                const blobUrl = URL.createObjectURL(blob);
                window.open(blobUrl, "_blank");
            }});
            </script>
        """
        
        components.html(js_code, height=60)

        # Bouton de téléchargement direct
        st.download_button(
            label="📥 Télécharger directement le PDF",
            data=pdf_bytes,
            file_name=f"menu_{start_str.replace('/', '-')}.pdf",
            mime="application/pdf"
        )

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
