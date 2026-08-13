import streamlit as st
from supabase import create_client, Client
from fpdf import FPDF
import io
import pandas as pd
from typing import Dict, List, Optional, Any
import hashlib

# Configuration de la page
st.set_page_config(
    page_title="Gestionnaire de Menus",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CONSTANTES
# ==========================================
UNITES = ["g", "kg", "ml", "cl", "l", "unité", "c. à soupe", "c. à café", 
          "pincée", "sachet", "gousse", "tranche", "boîte"]
RAYONS = ["Fruits & Légumes", "Boucherie & Poissonnerie", "Frais & Produits Laitiers", 
          "Épicerie Salée", "Épicerie Sucrée", "Boissons", "Surgelés", "Autre"]
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
REPAS = ["Midi", "Soir"]

# ==========================================
# INITIALISATION SUPABASE AVEC GESTION D'ERREURS
# ==========================================
@st.cache_resource(ttl=3600)
def init_supabase() -> Optional[Client]:
    """Initialise la connexion Supabase avec gestion des erreurs."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        # Test de connexion
        client.table("ingredients").select("id").limit(1).execute()
        return client
    except Exception as e:
        st.error(f"❌ Erreur de connexion à Supabase : {str(e)}")
        st.info("Vérifiez vos credentials dans les secrets Streamlit.")
        return None

supabase = init_supabase()

# ==========================================
# FONCTIONS UTILITAIRES
# ==========================================
def fetch_all_data(supabase: Client) -> Dict[str, List]:
    """Récupère toutes les données nécessaires en une seule fois."""
    data = {
        'ingredients': [],
        'recipes': [],
        'recipe_ingredients': [],
        'planned_meals': []
    }
    
    try:
        # Récupération de toutes les données
        for table in data.keys():
            response = supabase.table(table).select("*").execute()
            data[table] = response.data if response.data else []
    except Exception as e:
        st.error(f"Erreur lors de la récupération des données : {e}")
    
    return data

def clean_pdf_str(text: Any) -> str:
    """Nettoie les chaînes de caractères pour FPDF (encodage Latin-1)."""
    if not text:
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def format_quantity(qty: float) -> str:
    """Formate proprement les quantités."""
    if isinstance(qty, float) and qty.is_integer():
        return str(int(qty))
    return f"{qty:.2f}".rstrip('0').rstrip('.')

def confirm_delete(message: str) -> bool:
    """Affiche une confirmation de suppression."""
    if message not in st.session_state:
        st.session_state[message] = False
    
    if st.button("🗑️ Supprimer", key=f"del_{message}"):
        st.session_state[message] = True
    
    if st.session_state[message]:
        st.warning("⚠️ Cette action est irréversible !")
        col1, col2 = st.columns(2)
        if col1.button("✅ Confirmer", key=f"confirm_{message}"):
            st.session_state[message] = False
            return True
        if col2.button("❌ Annuler", key=f"cancel_{message}"):
            st.session_state[message] = False
            return False
    return False

# ==========================================
# FONCTION DE GÉNÉRATION DU PDF AMÉLIORÉE
# ==========================================
def generate_pdf(planned_meals: List[Dict], aggregated_items: Dict, 
                 recurrent_items: List[Dict], recipes_dict: Dict) -> bytes:
    """Génère un PDF A4 avec le menu et la liste de courses."""
    try:
        pdf = FPDF(format='A4', unit='mm')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # En-tête avec logo et date
        pdf.set_font('Helvetica', 'B', 20)
        pdf.cell(0, 15, clean_pdf_str('🍽️ Menu de la Semaine'), ln=True, align='C')
        
        # Date du jour
        from datetime import datetime
        date_str = datetime.now().strftime("%d/%m/%Y")
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 5, clean_pdf_str(f'Généré le {date_str}'), ln=True, align='C')
        pdf.ln(5)
        
        # Ligne de séparation
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        
        # --- SECTION 1 : PLANNING ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(0, 10, clean_pdf_str(' 1. Planning des Repas'), ln=True, fill=True)
        pdf.ln(3)
        
        # Création du tableau de planning
        schedule = {d: {"Midi": "-", "Soir": "-"} for d in JOURS}
        for pm in planned_meals:
            d = pm.get('day')
            m = pm.get('meal_type')
            rec_name = recipes_dict.get(pm.get('recipe_id'), {}).get('name', 'Inconnu')
            serv = pm.get('servings', 1)
            if d in schedule and m in schedule[d]:
                schedule[d][m] = f"{rec_name} ({serv}p)"
        
        # Tableau avec couleurs alternées
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(30, 8, clean_pdf_str('Jour'), border=1, fill=True)
        pdf.cell(80, 8, clean_pdf_str('Midi'), border=1, fill=True)
        pdf.cell(80, 8, clean_pdf_str('Soir'), border=1, ln=True, fill=True)
        
        pdf.set_font('Helvetica', size=9)
        for i, day in enumerate(JOURS):
            # Alternance de couleurs
            if i % 2 == 0:
                pdf.set_fill_color(250, 250, 250)
            else:
                pdf.set_fill_color(240, 240, 240)
            
            midi_txt = clean_pdf_str(schedule[day]['Midi'])[:50]
            soir_txt = clean_pdf_str(schedule[day]['Soir'])[:50]
            
            pdf.cell(30, 7, clean_pdf_str(day), border=1, fill=True)
            pdf.cell(80, 7, midi_txt, border=1, fill=True)
            pdf.cell(80, 7, soir_txt, border=1, ln=True, fill=True)
        
        pdf.ln(8)
        
        # Ligne de découpe
        pdf.set_dash_pattern(dash=2, gap=2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.set_dash_pattern()
        pdf.set_font('Helvetica', 'I', 8)
        pdf.cell(0, 5, clean_pdf_str('✂️ - - - - - - - - - - Découper ici - - - - - - - - - - ✂️'), 
                ln=True, align='C')
        pdf.ln(8)
        
        # --- SECTION 2 : LISTE DE COURSES ---
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, clean_pdf_str(' 2. Liste de Courses'), ln=True, fill=True)
        pdf.ln(3)
        
        # Organisation par rayon
        by_cat = {}
        for item in aggregated_items.values():
            cat = item.get('category', 'Autre')
            by_cat.setdefault(cat, []).append(item)
        
        if not by_cat:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.cell(0, 5, clean_pdf_str('Aucun article à acheter pour ces repas.'), ln=True)
        else:
            for cat in RAYONS:
                if cat in by_cat:
                    # En-tête de catégorie
                    pdf.set_font('Helvetica', 'B', 11)
                    pdf.set_fill_color(220, 220, 220)
                    pdf.cell(0, 7, clean_pdf_str(f'• {cat}'), ln=True, fill=True)
                    
                    # Items de la catégorie
                    pdf.set_font('Helvetica', size=9)
                    for it in by_cat[cat]:
                        qty_str = format_quantity(it['qty'])
                        line = f"   [  ] {it['name']} : {qty_str} {it['unit']}"
                        pdf.cell(0, 5, clean_pdf_str(line), ln=True)
                    pdf.ln(2)
        
        pdf.ln(5)
        
        # --- SECTION 3 : PRODUITS RÉCURRENTS ---
        if recurrent_items:
            pdf.set_font('Helvetica', 'B', 14)
            pdf.cell(0, 10, clean_pdf_str(' 3. Produits récurrents'), ln=True, fill=True)
            pdf.ln(3)
            
            pdf.set_font('Helvetica', size=9)
            # Affichage en 2 colonnes
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

# ==========================================
# INTERFACE PRINCIPALE
# ==========================================
def main():
    """Fonction principale de l'application."""
    
    if not supabase:
        st.error("🚫 Application non fonctionnelle : impossible de se connecter à la base de données.")
        st.stop()
    
    st.title("🍽️ Mon Gestionnaire de Menus")
    st.markdown("---")
    
    # Chargement des données au démarrage
    if 'data_loaded' not in st.session_state:
        with st.spinner("Chargement des données..."):
            st.session_state.data = fetch_all_data(supabase)
            st.session_state.data_loaded = True
    
    # Navigation par onglets
    tab_ingredients, tab_recipes, tab_menus = st.tabs([
        "🥕 Ingrédients", 
        "📖 Recettes", 
        "📅 Menus & Courses"
    ])
    
    # ==========================================
    # ONGLET 1 : INGRÉDIENTS
    # ==========================================
    with tab_ingredients:
        st.header("Gestion de la base d'ingrédients")
        
        # Création de colonnes pour le layout
        col_add, col_list = st.columns([1, 2])
        
        with col_add:
            st.subheader("➕ Ajouter un ingrédient")
            with st.form("form_add_ingredient", clear_on_submit=True):
                name = st.text_input("Nom de l'ingrédient *", placeholder="ex: Carotte")
                col1, col2 = st.columns(2)
                unit = col1.selectbox("Unité par défaut *", UNITES)
                category = col2.selectbox("Rayon / Catégorie", RAYONS)
                
                st.markdown("---")
                col3, col4 = st.columns(2)
                exclude_from_list = col3.checkbox("🚪 Fond de placard")
                is_recurrent = col4.checkbox("🔁 Produit récurrent")
                
                submitted = st.form_submit_button("Ajouter", use_container_width=True)
                
                if submitted:
                    if not name.strip():
                        st.error("❌ Le nom est obligatoire !")
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
                            st.success(f"✅ '{name}' ajouté !")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur : {e}")
        
        with col_list:
            st.subheader("📋 Ingrédients enregistrés")
            
            ingredients_list = st.session_state.data.get('ingredients', [])
            
            if not ingredients_list:
                st.info("Aucun ingrédient enregistré.")
            else:
                # Conversion en DataFrame pour meilleure visualisation
                df = pd.DataFrame(ingredients_list)
                
                # Configuration des colonnes
                column_config = {
                    "id": None,
                    "name": "Nom",
                    "unit": "Unité",
                    "category": "Rayon",
                    "exclude_from_list": st.column_config.CheckboxColumn(
                        "Fond de placard",
                        help="Ne sera jamais ajouté aux courses"
                    ),
                    "is_recurrent": st.column_config.CheckboxColumn(
                        "Récurrent",
                        help="Toujours dans les produits récurrents"
                    )
                }
                
                st.dataframe(
                    df,
                    column_config=column_config,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Modification d'un ingrédient
                with st.expander("✏️ Modifier / Supprimer"):
                    ing_dict = {f"{ing['name']} ({ing['unit']})": ing for ing in ingredients_list}
                    selected = st.selectbox("Sélectionner", list(ing_dict.keys()))
                    target = ing_dict[selected]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button("✏️ Modifier", use_container_width=True):
                            st.session_state.edit_ing = target
                    
                    with col2:
                        if st.button("🗑️ Supprimer", use_container_width=True, type="primary"):
                            if confirm_delete(f"delete_ing_{target['id']}"):
                                supabase.table("ingredients").delete().eq("id", target["id"]).execute()
                                st.success("✅ Supprimé !")
                                st.rerun()
    
    # ==========================================
    # ONGLET 2 : RECETTES
    # ==========================================
    with tab_recipes:
        st.header("Gestion des recettes")
        
        # Sous-onglets
        tab_view, tab_edit = st.tabs(["🔍 Consulter", "✏️ Créer / Éditer"])
        
        with tab_view:
            recipes_list = st.session_state.data.get('recipes', [])
            
            if not recipes_list:
                st.info("Aucune recette disponible.")
            else:
                recipe_names = [r["name"] for r in recipes_list]
                selected_name = st.selectbox("Choisir une recette", recipe_names)
                recipe = next((r for r in recipes_list if r["name"] == selected_name), None)
                
                if recipe:
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        st.subheader(f"📖 {recipe['name']}")
                        base_servings = recipe.get("base_servings", 4)
                        target_servings = st.number_input(
                            "Nombre de personnes",
                            min_value=1,
                            max_value=50,
                            value=base_servings
                        )
                        ratio = target_servings / base_servings
                        
                        if target_servings != base_servings:
                            st.info(f"💡 Quantités ajustées pour {target_servings} pers.")
                    
                    with col2:
                        st.subheader("🛒 Ingrédients")
                        
                        # Récupération des ingrédients de la recette
                        rec_ings = [
                            ri for ri in st.session_state.data.get('recipe_ingredients', [])
                            if ri.get("recipe_id") == recipe["id"]
                        ]
                        
                        if not rec_ings:
                            st.warning("Aucun ingrédient pour cette recette.")
                        else:
                            ingredients_dict = {
                                ing["id"]: ing for ing in st.session_state.data.get('ingredients', [])
                            }
                            
                            for ri in rec_ings:
                                ing = ingredients_dict.get(ri.get("ingredient_id"))
                                if ing:
                                    qty = ri["quantity"] * ratio
                                    qty_str = format_quantity(qty)
                                    
                                    tags = []
                                    if ing.get("exclude_from_list"):
                                        tags.append("Fond de placard")
                                    if ing.get("is_recurrent"):
                                        tags.append("Récurrent")
                                    
                                    tag_str = f" *({', '.join(tags)})*" if tags else ""
                                    st.write(f"• **{ing['name']}** : {qty_str} {ing['unit']}{tag_str}")
                    
                    st.markdown("---")
                    st.subheader("📝 Instructions")
                    if recipe.get("instructions"):
                        st.write(recipe["instructions"])
                    else:
                        st.info("Aucune instruction.")
        
        with tab_edit:
            col_create, col_manage = st.columns([1, 2])
            
            with col_create:
                st.subheader("➕ Nouvelle recette")
                with st.form("form_new_recipe", clear_on_submit=True):
                    name = st.text_input("Nom *")
                    servings = st.number_input("Personnes", min_value=1, value=4)
                    instructions = st.text_area("Instructions", height=100)
                    
                    if st.form_submit_button("Créer", use_container_width=True):
                        if not name.strip():
                            st.error("❌ Nom obligatoire !")
                        else:
                            try:
                                supabase.table("recipes").insert({
                                    "name": name.strip().capitalize(),
                                    "base_servings": servings,
                                    "instructions": instructions
                                }).execute()
                                st.success("✅ Recette créée !")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")
            
            with col_manage:
                st.subheader("⚙️ Gérer les recettes")
                
                recipes_list = st.session_state.data.get('recipes', [])
                
                if not recipes_list:
                    st.info("Aucune recette à gérer.")
                else:
                    recipe_dict = {r["name"]: r for r in recipes_list}
                    selected = st.selectbox("Sélectionner", list(recipe_dict.keys()))
                    target = recipe_dict[selected]
                    
                    # Modification
                    with st.expander("✏️ Modifier"):
                        with st.form(f"form_edit_{target['id']}"):
                            new_name = st.text_input("Nom", value=target["name"])
                            new_servings = st.number_input("Personnes", value=target.get("base_servings", 4))
                            new_instructions = st.text_area("Instructions", value=target.get("instructions", ""))
                            
                            if st.form_submit_button("Sauvegarder"):
                                supabase.table("recipes").update({
                                    "name": new_name,
                                    "base_servings": new_servings,
                                    "instructions": new_instructions
                                }).eq("id", target["id"]).execute()
                                st.success("✅ Mis à jour !")
                                st.rerun()
                    
                    # Gestion des ingrédients
                    st.subheader("Ingrédients de la recette")
                    
                    rec_ings = [
                        ri for ri in st.session_state.data.get('recipe_ingredients', [])
                        if ri.get("recipe_id") == target["id"]
                    ]
                    
                    ingredients_dict = {
                        ing["id"]: ing for ing in st.session_state.data.get('ingredients', [])
                    }
                    
                    # Affichage des ingrédients actuels
                    for ri in rec_ings:
                        ing = ingredients_dict.get(ri.get("ingredient_id"))
                        if ing:
                            col1, col2, col3 = st.columns([3, 2, 1])
                            col1.write(f"**{ing['name']}**")
                            col2.write(f"{ri['quantity']} {ing['unit']}")
                            if col3.button("❌", key=f"del_ri_{ri['id']}"):
                                supabase.table("recipe_ingredients").delete().eq("id", ri["id"]).execute()
                                st.rerun()
                    
                    # Ajout d'ingrédient
                    st.markdown("---")
                    ing_options = [i["name"] for i in st.session_state.data.get('ingredients', [])]
                    
                    col1, col2, col3 = st.columns([2, 1, 1])
                    selected_ing = col1.selectbox("Ingrédient", ing_options)
                    qty = col2.number_input("Quantité", min_value=0.1, value=100.0)
                    
                    if col3.button("➕", key="add_ing"):
                        ing_obj = next(
                            (i for i in st.session_state.data.get('ingredients', []) 
                             if i["name"] == selected_ing),
                            None
                        )
                        
                        if ing_obj:
                            supabase.table("recipe_ingredients").insert({
                                "recipe_id": target["id"],
                                "ingredient_id": ing_obj["id"],
                                "quantity": qty
                            }).execute()
                            st.rerun()
                    
                    # Suppression de la recette
                    st.markdown("---")
                    if st.button("🗑️ Supprimer la recette", type="primary"):
                        if confirm_delete(f"delete_rec_{target['id']}"):
                            supabase.table("recipes").delete().eq("id", target["id"]).execute()
                            st.success("✅ Recette supprimée !")
                            st.rerun()
    
    # ==========================================
    # ONGLET 3 : MENUS & COURSES
    # ==========================================
    with tab_menus:
        st.header("Planification & Liste de courses")
        
        col_plan, col_list = st.columns([1, 1])
        
        # --- PLANIFICATION ---
        with col_plan:
            st.subheader("📅 Planifier un repas")
            
            recipes_list = st.session_state.data.get('recipes', [])
            planned_meals = st.session_state.data.get('planned_meals', [])
            
            if not recipes_list:
                st.warning("Créez d'abord des recettes !")
            else:
                with st.form("form_add_meal"):
                    col1, col2 = st.columns(2)
                    day = col1.selectbox("Jour", JOURS)
                    meal_type = col2.selectbox("Repas", REPAS)
                    
                    recipe_names = [r["name"] for r in recipes_list]
                    recipe_name = st.selectbox("Recette", recipe_names)
                    recipe = next((r for r in recipes_list if r["name"] == recipe_name), None)
                    
                    servings = st.number_input("Convives", min_value=1, value=recipe.get("base_servings", 4) if recipe else 4)
                    
                    if st.form_submit_button("➕ Ajouter", use_container_width=True):
                        if recipe:
                            supabase.table("planned_meals").insert({
                                "day": day,
                                "meal_type": meal_type,
                                "recipe_id": recipe["id"],
                                "servings": servings
                            }).execute()
                            st.success("✅ Repas ajouté !")
                            st.rerun()
            
            st.markdown("---")
            st.subheader("Planning actuel")
            
            if not planned_meals:
                st.info("Aucun repas planifié.")
            else:
                recipes_dict = {r["id"]: r for r in recipes_list}
                
                # Organisation par jour
                from collections import defaultdict
                by_day = defaultdict(list)
                for pm in planned_meals:
                    by_day[pm["day"]].append(pm)
                
                for day in JOURS:
                    if day in by_day:
                        st.markdown(f"**{day}**")
                        for pm in by_day[day]:
                            rec = recipes_dict.get(pm["recipe_id"], {})
                            col1, col2 = st.columns([4, 1])
                            col1.write(f"• {pm['meal_type']} : {rec.get('name', 'Inconnu')} ({pm['servings']}p)")
                            if col2.button("❌", key=f"del_pm_{pm['id']}"):
                                supabase.table("planned_meals").delete().eq("id", pm["id"]).execute()
                                st.rerun()
                
                if st.button("🗑️ Tout effacer", type="primary"):
                    if confirm_delete("clear_all_meals"):
                        supabase.table("planned_meals").delete().neq("id", 0).execute()
                        st.rerun()
        
        # --- LISTE DE COURSES ---
        with col_list:
            st.subheader("🛒 Liste de courses")
            
            # Calcul de l'agrégation
            ingredients_dict = {
                i["id"]: i for i in st.session_state.data.get('ingredients', [])
            }
            recipes_dict = {r["id"]: r for r in recipes_list}
            recipe_ings = st.session_state.data.get('recipe_ingredients', [])
            
            aggregated = {}
            
            for pm in planned_meals:
                recipe = recipes_dict.get(pm["recipe_id"])
                if not recipe:
                    continue
                
                ratio = pm["servings"] / recipe.get("base_servings", 1)
                
                for ri in recipe_ings:
                    if ri["recipe_id"] == pm["recipe_id"]:
                        ing = ingredients_dict.get(ri["ingredient_id"])
                        if not ing or ing.get("exclude_from_list"):
                            continue
                        
                        qty = ri["quantity"] * ratio
                        
                        if ing["id"] not in aggregated:
                            aggregated[ing["id"]] = {
                                "name": ing["name"],
                                "qty": 0,
                                "unit": ing["unit"],
                                "category": ing.get("category", "Autre")
                            }
                        aggregated[ing["id"]]["qty"] += qty
            
            if not aggregated:
                st.info("Ajoutez des repas pour générer la liste.")
            else:
                # Organisation par rayon
                by_cat = defaultdict(list)
                for item in aggregated.values():
                    by_cat[item["category"]].append(item)
                
                for rayon in RAYONS:
                    if rayon in by_cat:
                        st.markdown(f"**{rayon}**")
                        for item in by_cat[rayon]:
                            qty_str = format_quantity(item["qty"])
                            st.checkbox(f"{item['name']} : {qty_str} {item['unit']}")
            
            # Produits récurrents
            st.markdown("---")
            st.subheader("🔁 Produits récurrents")
            
            recurrent = [i for i in ingredients_dict.values() if i.get("is_recurrent")]
            
            if not recurrent:
                st.caption("Aucun produit récurrent.")
            else:
                for item in recurrent:
                    st.checkbox(f"{item['name']} ({item.get('category', 'Autre')})")
            
            # Export PDF
            st.markdown("---")
            if st.button("📄 Générer PDF", use_container_width=True):
                pdf_bytes = generate_pdf(planned_meals, aggregated, recurrent, recipes_dict)
                
                if pdf_bytes:
                    st.download_button(
                        "📥 Télécharger PDF",
                        data=pdf_bytes,
                        file_name="menu_semaine.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()
