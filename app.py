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
# CHARGEMENT DES DONNÉES (CACHE)
# ------------------------------
@st.cache_data(ttl=30)
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
    st.cache_data.clear()
    st.rerun()

# ------------------------------
# FONCTIONS UTILITAIRES
# ------------------------------
def clean_pdf_str(text: Any) -> str:
    if not text:
        return ""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def format_quantity(qty: float) -> str:
    if isinstance(qty, float) and qty.is_integer():
        return str(int(qty))
    return f"{qty:.2f}".rstrip('0').rstrip('.')

# ------------------------------
# GÉNÉRATION PDF
# ------------------------------
def generate_pdf(planned_meals: List[Dict], aggregated_items: Dict,
                 recurrent_items: List[Dict], recipes_dict: Dict) -> bytes:
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
    pdf.cell(0, 10, ' 1. Planning des Repas', ln=True, fill=True)
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
    pdf.cell(30, 8, 'Jour', border=1, fill=True)
    pdf.cell(80, 8, 'Midi', border=1, fill=True)
    pdf.cell(80, 8, 'Soir', border=1, ln=True, fill=True)

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
    pdf.cell(0, 5, '✂️ - - - - - - - - - - Découper ici - - - - - - - - - - ✂️', ln=True, align='C')
    pdf.ln(8)

    # Liste de courses
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, ' 2. Liste de Courses', ln=True, fill=True)
    pdf.ln(3)

    by_cat = defaultdict(list)
    for item in aggregated_items.values():
        by_cat[item.get('category', 'Autre')].append(item)

    if not by_cat:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 5, 'Aucun article à acheter.', ln=True)
    else:
        for cat in RAYONS:
            if cat in by_cat:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.cell(0, 7, f'• {clean_pdf_str(cat)}', ln=True, fill=True)
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
        pdf.cell(0, 10, ' 3. Produits récurrents', ln=True, fill=True)
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

# ------------------------------
# INTERFACE PRINCIPALE
# ------------------------------
def main():
    if not supabase:
        st.error("🚫 Application non fonctionnelle.")
        st.stop()

    st.title("🍽️ Mon Gestionnaire de Menus")
    st.markdown("---")

    # Chargement initial
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

        # Bouton d'ajout dans une modale
        col_add, col_refresh = st.columns([1, 5])
        with col_add:
            if st.button("➕ Ajouter un ingrédient", use_container_width=True):
                st.session_state.show_add_ing = True
        with col_refresh:
            st.write("")  # espacement

        # Modale d'ajout
        if st.session_state.get('show_add_ing', False):
            with st.form("add_ing_form"):
                st.subheader("Nouvel ingrédient")
                name = st.text_input("Nom *")
                col1, col2 = st.columns(2)
                unit = col1.selectbox("Unité", UNITES)
                category = col2.selectbox("Rayon", RAYONS)
                col3, col4 = st.columns(2)
                exclude = col3.checkbox("🚪 Fond de placard")
                recurrent = col4.checkbox("🔁 Récurrent")
                submitted = st.form_submit_button("Enregistrer")
                if submitted:
                    if not name.strip():
                        st.error("Nom obligatoire")
                    else:
                        supabase.table("ingredients").insert({
                            "name": name.strip().capitalize(),
                            "unit": unit,
                            "category": category,
                            "exclude_from_list": exclude,
                            "is_recurrent": recurrent
                        }).execute()
                        st.success("Ingrédient ajouté !")
                        st.session_state.show_add_ing = False
                        refresh_data()

        # Affichage des ingrédients avec data_editor
        ingredients = st.session_state.data.get('ingredients', [])
        if ingredients:
            df = pd.DataFrame(ingredients)
            df = df[['name', 'unit', 'category', 'exclude_from_list', 'is_recurrent']]
            edited_df = st.data_editor(
                df,
                column_config={
                    "name": "Nom",
                    "unit": "Unité",
                    "category": st.column_config.SelectboxColumn("Rayon", options=RAYONS),
                    "exclude_from_list": st.column_config.CheckboxColumn("Fond de placard"),
                    "is_recurrent": st.column_config.CheckboxColumn("Récurrent")
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key="ingredients_editor"
            )

            # Boutons pour sauvegarder ou supprimer
            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Sauvegarder modifications", use_container_width=True):
                    # Mise à jour de chaque ligne modifiée
                    for idx, row in edited_df.iterrows():
                        original = next((i for i in ingredients if i['name'] == row['name'] and i['unit'] == row['unit']), None)
                        if original:
                            supabase.table("ingredients").update({
                                "unit": row['unit'],
                                "category": row['category'],
                                "exclude_from_list": row['exclude_from_list'],
                                "is_recurrent": row['is_recurrent']
                            }).eq("id", original['id']).execute()
                    st.success("Modifications enregistrées")
                    refresh_data()
            with col_del:
                if st.button("🗑️ Supprimer sélection", use_container_width=True):
                    # Récupérer les lignes sélectionnées dans l'éditeur
                    selected_rows = st.session_state.get("ingredients_editor", {}).get("edited_rows", {})
                    if selected_rows:
                        # Supprimer les ingrédients correspondants
                        for idx in selected_rows:
                            row = edited_df.iloc[idx]
                            ing = next((i for i in ingredients if i['name'] == row['name'] and i['unit'] == row['unit']), None)
                            if ing:
                                supabase.table("ingredients").delete().eq("id", ing['id']).execute()
                        st.success("Ingrédients supprimés")
                        refresh_data()
                    else:
                        st.warning("Sélectionnez d'abord des lignes à supprimer")
        else:
            st.info("Aucun ingrédient pour le moment.")

    # ============================
    # ONGLET RECETTES
    # ============================
    with tab_recettes:
        st.header("Recettes")

        # Récupération des données
        recipes = st.session_state.data.get('recipes', [])
        recipe_ings = st.session_state.data.get('recipe_ingredients', [])
        ingredients = st.session_state.data.get('ingredients', [])

        # Bouton nouvelle recette
        col_new, col_refresh = st.columns([1, 5])
        with col_new:
            if st.button("➕ Nouvelle recette", use_container_width=True):
                st.session_state.show_add_recipe = True
        with col_refresh:
            st.write("")

        # Modale nouvelle recette
        if st.session_state.get('show_add_recipe', False):
            with st.form("add_recipe_form"):
                st.subheader("Créer une recette")
                name = st.text_input("Nom *")
                servings = st.number_input("Personnes", min_value=1, value=4)
                instructions = st.text_area("Instructions", height=100)
                submitted = st.form_submit_button("Créer")
                if submitted:
                    if not name.strip():
                        st.error("Nom obligatoire")
                    else:
                        supabase.table("recipes").insert({
                            "name": name.strip().capitalize(),
                            "base_servings": servings,
                            "instructions": instructions
                        }).execute()
                        st.success("Recette créée !")
                        st.session_state.show_add_recipe = False
                        refresh_data()

        if not recipes:
            st.info("Aucune recette disponible.")
        else:
            # Sélection d'une recette
            recipe_names = [r['name'] for r in recipes]
            selected_name = st.selectbox("Choisir une recette", recipe_names, key="selected_recipe")
            recipe = next((r for r in recipes if r['name'] == selected_name), None)

            if recipe:
                st.markdown("---")
                col_info, col_actions = st.columns([3, 1])
                with col_info:
                    st.subheader(f"📖 {recipe['name']}")
                    base_servings = recipe.get('base_servings', 4)
                    # Ajustement des portions
                    target_servings = st.number_input(
                        "Personnes", min_value=1, max_value=50, value=base_servings,
                        key=f"servings_{recipe['id']}"
                    )
                    ratio = target_servings / base_servings
                with col_actions:
                    st.write("")
                    st.write("")
                    col_dup, col_del = st.columns(2)
                    if col_dup.button("📋 Dupliquer", use_container_width=True):
                        # Duplication rapide
                        new_name = f"{recipe['name']} (copie)"
                        new_rec = supabase.table("recipes").insert({
                            "name": new_name,
                            "base_servings": recipe['base_servings'],
                            "instructions": recipe.get('instructions', '')
                        }).execute()
                        new_id = new_rec.data[0]['id']
                        # Copier les ingrédients
                        orig_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                        for ri in orig_ings:
                            supabase.table("recipe_ingredients").insert({
                                "recipe_id": new_id,
                                "ingredient_id": ri['ingredient_id'],
                                "quantity": ri['quantity']
                            }).execute()
                        st.success("Recette dupliquée !")
                        refresh_data()
                    if col_del.button("🗑️ Supprimer", use_container_width=True, type="primary"):
                        supabase.table("recipes").delete().eq("id", recipe['id']).execute()
                        st.success("Recette supprimée")
                        refresh_data()

                # Ingrédients de la recette
                st.markdown("#### 🛒 Ingrédients")
                rec_ings = [ri for ri in recipe_ings if ri['recipe_id'] == recipe['id']]
                if rec_ings:
                    # Créer un DataFrame éditable
                    ing_list = []
                    for ri in rec_ings:
                        ing = next((i for i in ingredients if i['id'] == ri['ingredient_id']), None)
                        if ing:
                            ing_list.append({
                                "ingredient": ing['name'],
                                "quantity": ri['quantity'],
                                "unit": ing['unit']
                            })
                    df_ings = pd.DataFrame(ing_list)
                    edited_ings = st.data_editor(
                        df_ings,
                        column_config={
                            "ingredient": "Ingrédient",
                            "quantity": st.column_config.NumberColumn("Quantité", min_value=0.1, step=0.1),
                            "unit": "Unité"
                        },
                        hide_index=True,
                        use_container_width=True,
                        num_rows="fixed",
                        key=f"rec_ings_editor_{recipe['id']}"
                    )
                    # Boutons pour sauvegarder ou supprimer des lignes
                    col_save_ings, col_del_ings = st.columns(2)
                    if col_save_ings.button("💾 Sauvegarder", use_container_width=True):
                        # Mettre à jour les quantités modifiées
                        for idx, row in edited_ings.iterrows():
                            original_ri = rec_ings[idx]
                            if row['quantity'] != original_ri['quantity']:
                                supabase.table("recipe_ingredients").update({
                                    "quantity": row['quantity']
                                }).eq("id", original_ri['id']).execute()
                        st.success("Quantités mises à jour")
                        refresh_data()
                    if col_del_ings.button("🗑️ Supprimer sélection", use_container_width=True):
                        selected_rows = st.session_state.get(f"rec_ings_editor_{recipe['id']}", {}).get("edited_rows", {})
                        if selected_rows:
                            for idx in selected_rows:
                                ri_to_del = rec_ings[idx]
                                supabase.table("recipe_ingredients").delete().eq("id", ri_to_del['id']).execute()
                            st.success("Ingrédients supprimés de la recette")
                            refresh_data()
                        else:
                            st.warning("Sélectionnez des lignes à supprimer")
                else:
                    st.info("Aucun ingrédient ajouté à cette recette.")

                # Ajout d'un ingrédient
                st.markdown("#### ➕ Ajouter un ingrédient")
                ing_names = [i['name'] for i in ingredients if i['name'] not in [ri['ingredient'] for ri in ing_list]]
                if ing_names:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        selected_ing = st.selectbox("Ingrédient", ing_names, key=f"add_ing_{recipe['id']}")
                    with col2:
                        qty = st.number_input("Quantité", min_value=0.1, value=100.0, key=f"qty_{recipe['id']}")
                    with col3:
                        if st.button("Ajouter", key=f"btn_add_ing_{recipe['id']}", use_container_width=True):
                            ing_obj = next((i for i in ingredients if i['name'] == selected_ing), None)
                            if ing_obj:
                                supabase.table("recipe_ingredients").insert({
                                    "recipe_id": recipe['id'],
                                    "ingredient_id": ing_obj['id'],
                                    "quantity": qty
                                }).execute()
                                st.success("Ingrédient ajouté")
                                refresh_data()
                else:
                    st.info("Tous les ingrédients disponibles sont déjà dans la recette.")

                # Instructions
                st.markdown("#### 📝 Instructions")
                if recipe.get('instructions'):
                    st.write(recipe['instructions'])
                else:
                    st.info("Aucune instruction.")

                # Bouton pour modifier les infos de base
                with st.expander("✏️ Modifier nom, personnes, instructions"):
                    with st.form(f"edit_recipe_{recipe['id']}"):
                        new_name = st.text_input("Nom", value=recipe['name'])
                        new_servings = st.number_input("Personnes", value=recipe.get('base_servings', 4))
                        new_instructions = st.text_area("Instructions", value=recipe.get('instructions', ''))
                        if st.form_submit_button("Sauvegarder"):
                            supabase.table("recipes").update({
                                "name": new_name,
                                "base_servings": new_servings,
                                "instructions": new_instructions
                            }).eq("id", recipe['id']).execute()
                            st.success("Recette mise à jour")
                            refresh_data()

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

        # Colonne gauche : planification
        col_plan, col_list = st.columns([1, 1])

        with col_plan:
            st.subheader("📅 Planification")

            # Formulaire d'ajout compact
            with st.form("add_meal_form"):
                col_day, col_meal = st.columns(2)
                day = col_day.selectbox("Jour", JOURS)
                meal_type = col_meal.selectbox("Repas", REPAS)
                recipe_names = [r['name'] for r in recipes]
                recipe_name = st.selectbox("Recette", recipe_names)
                recipe = next((r for r in recipes if r['name'] == recipe_name), None)
                servings = st.number_input("Convives", min_value=1, value=recipe.get('base_servings', 4) if recipe else 4)
                submitted = st.form_submit_button("➕ Ajouter au planning", use_container_width=True)
                if submitted and recipe:
                    supabase.table("planned_meals").insert({
                        "day": day,
                        "meal_type": meal_type,
                        "recipe_id": recipe['id'],
                        "servings": servings
                    }).execute()
                    st.success("Repas ajouté !")
                    refresh_data()

            # Affichage du planning par jour
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
                                supabase.table("planned_meals").delete().eq("id", pm['id']).execute()
                                refresh_data()

                if st.button("🗑️ Vider tout le planning", use_container_width=True):
                    supabase.table("planned_meals").delete().neq("id", 0).execute()
                    st.success("Planning vidé")
                    refresh_data()

        # Colonne droite : liste de courses
        with col_list:
            st.subheader("🛒 Liste de courses")

            # Calcul de l'agrégation
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
                            st.checkbox(f"{item['name']} : {qty_str} {item['unit']}", key=f"shop_{item['name']}_{rayon}")

            # Produits récurrents
            st.markdown("---")
            st.subheader("🔁 Produits récurrents")
            recurrent = [i for i in ingredients_dict.values() if i.get('is_recurrent')]
            if recurrent:
                for item in recurrent:
                    st.checkbox(f"{item['name']} ({item.get('category', 'Autre')})", key=f"rec_{item['id']}")
            else:
                st.caption("Aucun produit récurrent configuré.")

            # Export PDF
            st.markdown("---")
            if st.button("📄 Générer la fiche PDF", use_container_width=True):
                pdf_bytes = generate_pdf(planned_meals, aggregated, recurrent, recipes_dict)
                if pdf_bytes:
                    st.download_button(
                        "📥 Télécharger le PDF",
                        data=pdf_bytes,
                        file_name="menu_semaine.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

if __name__ == "__main__":
    main()
