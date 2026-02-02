import streamlit as st
from ruamel.yaml import YAML
import sys
import os
import re

# Simulateur de f-strings
import numpy as np # Pour la simulation dans le validateur
import random
import ast  #Pour la simulation dans le validateur
import tokenize
import io, copy
from io import StringIO
from collections import Counter
import ast



def trigger_rerun():
    # Cette fonction ne fait rien d'autre que forcer Streamlit 
    # à relire tout le script avec les nouvelles valeurs.
    pass


def sync_export(qid, source_key):
    # On récupère la valeur du widget qui vient de changer
    val = st.session_state[source_key]
    # On met à jour le dictionnaire de référence
    st.session_state.selected_for_export[qid] = val
    
    # On synchronise l'autre widget pour qu'il soit à jour au prochain affichage
    other_key = f"check_side_{qid}" if "main" in source_key else f"check_main_{qid}"
    st.session_state[other_key] = val

def validate_fstring(text):
    if not text or '{' not in text:
        return None
    
    start = 0
    while True:
        start = text.find('{', start)
        if start == -1: break
        
        end_brace = text.find('}', start)
        if end_brace == -1: return "⚠️ Accolade non fermée"
            
        full_block = text[start+1:end_brace].replace('\n', '')
        
        # On essaie d'isoler la partie 'code' du 'formatage'
        # On cherche le ":" le plus à droite qui n'est pas dans des parenthèses
        code_part = full_block
        bracket_level = 0
        for i in range(len(full_block)-1, -1, -1):
            char = full_block[i]
            if char == ')': bracket_level += 1
            elif char == '(': bracket_level -= 1
            elif char == ':' and bracket_level == 0:
                code_part = full_block[:i]
                break
        
        try:
            ast.parse(code_part.strip(), mode='eval')
        except SyntaxError as e:
            return f"⚠️ Erreur dans '{{{code_part.strip()}}}' : {e.msg}"
            
        start = end_brace + 1
    return None

# Preview LaTeX
def render_preview(label, text):
    """Affiche un aperçu si du LaTeX ou du Markdown est présent."""
    if text and ('$' in text or '{' in text):
        with st.container():
            #st.caption(f"Aperçu du rendu ({label}) :")
            st.markdown(
                f"<div style='font-size:0.8rem; color:gray; margin-bottom:-0.2rem;'>"
                f"Aperçu du rendu ({label}) :</div>",
        unsafe_allow_html=True
    )
            st.info(text) # st.info rend le Markdown et le LaTeX entre $ nativement

from ruamel.yaml import YAML

def save_my_yaml(filename):
    # 1. On initialise ruamel.yaml proprement
    yaml_format = YAML()
    yaml_format.preserve_quotes = True
    yaml_format.indent(mapping=2, sequence=4, offset=2)
    
    if not filename:
        st.error("Le nom du fichier ne peut pas être vide.")
        return
    
    # 2. Nettoyage des contraintes vides
    # On travaille sur une copie ou directement si on accepte la modif en session
    data_to_save = st.session_state.data
    for q in list(data_to_save.keys()):
        obj = data_to_save[q]
        if isinstance(obj, dict) and 'constraints' in obj and not obj['constraints']:
            del obj['constraints']
    
    # 3. Écriture avec ruamel (pour éviter les tags !!python/object)
    with open(filename, 'w', encoding='utf-8') as f:
        yaml_format.dump(data_to_save, f)
    
    st.success(f"Fichier enregistré proprement sous `{filename}`")

# Pour exports
if 'selected_for_export' not in st.session_state:
    # On initialise avec False pour tous les quiz existants
    st.session_state.selected_for_export = {}


# --- CONFIGURATION YAML ---
# Utilisation de ruamel.yaml pour conserver le formatage et les styles de citations
yaml = YAML()
yaml.preserve_quotes = True 
yaml.indent(mapping=2, sequence=4, offset=2)

# --- GESTION DU FICHIER ---
if len(sys.argv) > 1 and sys.argv[1].endswith(('.yaml', '.yml')):
    FILE_PATH = sys.argv[1]
else:
    FILE_PATH = "quiz.yaml"

# Initialisation
# Initialisation des variables de session
if "shared_fn" not in st.session_state:
    st.session_state["shared_fn"] = FILE_PATH

# IMPORTANT : On pré-remplit les clés des widgets pour éviter le vide au chargement
if "fn_sidebar" not in st.session_state:
    st.session_state["fn_sidebar"] = st.session_state["shared_fn"]
if "fn_main" not in st.session_state:
    st.session_state["fn_main"] = st.session_state["shared_fn"]

if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None

def update_from_sidebar():
    val = st.session_state["fn_sidebar"]
    st.session_state["shared_fn"] = val
    st.session_state["fn_main"] = val

def update_from_main():
    val = st.session_state["fn_main"]
    st.session_state["shared_fn"] = val
    st.session_state["fn_sidebar"] = val



# fin hack pour le file_uploader
def load_data():
    if not os.path.exists(FILE_PATH):
        return {"title": "Nouveau Quiz", "quiz1": {"question": "", "propositions": []}}
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        return yaml.load(f)

# Initialisation de la session pour la persistance des données
if 'data' not in st.session_state:
    st.session_state.data = load_data()

data = st.session_state.data
st.session_state["quiz_title"] = st.session_state.data.get("title", "Entrez un titre ici")



#%%% ajout
# --- 2. PRÉPARATION DES DONNÉES  ---

quiz_ids_all = [k for k in data.keys() if k != 'title']

# On collecte tout en une seule passe
all_categories = set()
all_tags = set()
cat_counts = Counter()

for qid in quiz_ids_all:
    cat = data[qid].get('category', 'Aucune')
    all_categories.add(cat)
    cat_counts[cat] += 1
    
    tags = data[qid].get('tags', [])
    if isinstance(tags, list):
        all_tags.update(tags)

if "Aucune" in all_categories:
    all_categories.remove('Aucune') #insert(0, all_categories.pop(all_categories.index("Aucune")))
# On prépare les listes triées pour les widgets
sorted_cats = sorted(list(all_categories))
category_list = sorted_cats
sorted_tags = sorted(list(all_tags))

if "current_quiz" not in st.session_state:
    # On initialise avec le premier quiz de la liste, s'il y en a un
    st.session_state.current_quiz = quiz_ids_all[0] if quiz_ids_all else None

#%%% fin ajout


# -----------------------------------

st.set_page_config(layout="wide", page_title=f"Éditeur YAML - {FILE_PATH}")

hacks = '''# hack pour le file_uploader
st.markdown("""
<style>

/* Zone compacte */
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {
    padding-top: 0.3rem;
    padding-bottom: 0.3rem;
    min-height: unset;
}

/* Cache cloud + textes */
div[data-testid="stFileUploader"]
section[data-testid="stFileUploaderDropzone"]
div[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none;
}

/* Centre le bouton */
div[data-testid="stFileUploader"]
section[data-testid="stFileUploaderDropzone"]
span[data-testid="stBaseButton-secondary"] {
    margin: 0 auto;
}

/* Cache le nom du fichier + croix */
div[data-testid="stFileUploader"] ul {
    display: none;
}

</style>
""", unsafe_allow_html=True)

# fin hack pour le file_uploader

st.markdown("""
<style>


input[aria-label="Titre du document"] {
    font-size: 1.75rem !important;
    font-weight: 600 !important;
    border: none !important;
    background: transparent !important;
}

input[aria-label="Titre du document"]:focus {
    outline: none !important;
    box-shadow: none !important;
}

</style>
""", unsafe_allow_html=True)

# Hack pour les st.sidebar.divider
# Réduire la hauteur des dividers
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] hr {
        margin-top: 0.25rem;
        margin-bottom: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Réduire le haut de page
st.markdown(
    """
    <style>
    .block-container {
        padding-top: .0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Condenser la sidebar
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        padding-top: 0rem;
    }
    section[data-testid="stSidebar"] .block-container {
        gap: 0.35rem;
    }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        margin-bottom: 0.25rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# le haut de la sidebar
st.markdown(
    """
    <style>
    /* Réduire la hauteur du header de la sidebar */
    [data-testid="stSidebarHeader"] {
        height: 1.0rem;  
        min-height: 0.5rem;
        padding: 0;
        margin: 0;
    }

    /* Masquer le spacer (logo vide) */
    [data-testid="stLogoSpacer"] {
        display: none;
    }

    /* Ajuster le bouton collapse */
    [data-testid="stSidebarCollapseButton"] {
        margin-top: 0;
        padding: 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Et la zone principale

st.markdown(
    """
    <style>
    /* Réduire la hauteur globale du header */
    header[data-testid="stHeader"] {
        height: 2rem;       /* valeur minimale souhaitée */
        min-height: 2rem;
        padding: 0;
        margin: 0;
    }

    /* Toolbar interne */
    div[data-testid="stToolbar"] {
        padding: 0;
        margin: 0;
        height: 2rem;
    }

    /* Déployer button, menu etc. : s’assurer qu’ils restent visibles */
    div[data-testid="stToolbarActions"],
    div[data-testid="stAppDeployButton"],
    span[data-testid="stMainMenu"] {
        margin-top: 0;
        padding-top: 0;
    }
    </style>
    """,
    unsafe_allow_html=True
)
'''
# Le style qui ferait tout

st.markdown("""
<style>

/* ===== File Uploader compact ===== */
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {
    padding-top: 0.3rem;
    padding-bottom: 0.3rem;
    min-height: unset;
}
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] div[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none;
}
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] span[data-testid="stBaseButton-secondary"] {
    margin: 0 auto;
}
div[data-testid="stFileUploader"] ul {
    display: none;
}

/* ===== Titre principal ===== */
input[aria-label="Titre du document"] {
    font-size: 1.75rem !important;
    font-weight: 600 !important;
    border: none !important;
    background: transparent !important;
}
input[aria-label="Titre du document"]:focus {
    outline: none !important;
    box-shadow: none !important;
}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] {
    padding-top: 0rem;
}
section[data-testid="stSidebar"] .block-container {
    gap: 0.35rem;
}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    margin-bottom: 0.25rem;
}
section[data-testid="stSidebar"] hr {
    margin-top: 0.25rem;
    margin-bottom: 0.25rem;
}
[data-testid="stSidebarHeader"] {
    height: 1.0rem;
    min-height: 0.5rem;
    padding: 0;
    margin: 0;
}
[data-testid="stLogoSpacer"] {
    display: none;
}
[data-testid="stSidebarCollapseButton"] {
    margin-top: 0;
    padding: 0;
}

/* ===== Header principal ===== */
header[data-testid="stHeader"] {
    height: 2rem;
    min-height: 2rem;
    padding: 0;
    margin: 0;
}
div[data-testid="stToolbar"] {
    padding: 0;
    margin: 0;
    height: 2rem;
}
div[data-testid="stToolbarActions"],
div[data-testid="stAppDeployButton"],
span[data-testid="stMainMenu"] {
    margin-top: 0;
    padding-top: 0;
}

/* ===== Container principal ===== */
.block-container {
    padding-top: 0rem;
    padding-bottom: 0.5rem;
}

</style>
""", unsafe_allow_html=True)

def prepare_data(indata, output_file, mode="crypt", pwd=""):    
    from labquiz.putils import crypt_data, encode_data
    from pathlib import Path
     
    import copy
    # Lecture du fichier YAML
    data = copy.deepcopy(indata)

    # Mélange des propositions pour chaque quiz
    for quiz_name, quiz_content in data.items():
        if "propositions" in quiz_content:
            random.shuffle(quiz_content["propositions"])
            
    # Questions only
    data_only = copy.deepcopy(data)
    # suppression indices pour chaque quiz
    for quiz_name, quiz_content in data_only.items():
        if quiz_name == "title": continue 
        quiz_content.pop("constraints", None)
        for prop in quiz_content["propositions"]:
            keys_to_remove = {"expected", "reponse", "tip"}
            for k in keys_to_remove:
                prop.pop(k, None)
  
    path = Path(output_file)
    if mode == "crypt":
        data_out = crypt_data(data, f"{path.stem}_crypt", pwd=pwd)
        data_only_out = crypt_data(data_only, f"{path.stem}_qo_crypt",  pwd=pwd)
    elif mode == "enc":
        data_out = encode_data(data)
        data_only_out = encode_data(data_only) 
    else:
        mode = "yml"
        data_out = data
        data_only_out = data_only
        
    if mode == "crypt" and pwd != '':
        st.warning("⚠️ File crypted with pwd. Ensure to use the `madatoryInternet=True` option in quiz init")    
    
    return data_out, data_only_out

# Exports possibles (dans la sidebar)
@st.dialog("Configuration de l'export")
def export_config_dialog(export_data, format_type):
    st.subheader(f"Format : {format_type}")
    
    # Champ commun : Nom du fichier
    default_name = "mon_quiz"
    file_name = st.text_input("Nom du fichier (sans extension)", value=default_name)
    
    output_content = ""
    output_qo_content = ""
    extension = ""
    mime_type = ""

    # Options spécifiques selon le format
    if format_type == "Extrait (YAML)":
        fmt = st.radio("Type d'export", ["YAML crypté", "YAML encodé", "YAML sans encodage"])
        pwd = ""
        if fmt == "YAML crypté":
            mode = "crypt"
        elif fmt == "YAML encodé":
            mode = "enc"
        else:
            mode = "yml"
        if mode == "crypt":
            col_crypt1, col_crypt2  = st.columns([6, 4])
            with col_crypt1:
                pwd = st.text_input("Mot de passe", type="password", help="💡 Ce pwd participe à l'encryption")
        outdata, outdata_only = prepare_data(export_data, file_name, mode=mode, pwd=pwd)
        stream = StringIO()
        yaml.dump(outdata, stream)
        output_content = stream.getvalue()
        stream2 = StringIO()
        yaml.dump(outdata_only, stream2)
        output_qo_content = stream2.getvalue()
        extension = ".yaml"
        mime_type = "text/plain"
        st.info("💡 Ce mode permet de sauvegarder tout ou partie des questions en un nouveau fichier, "
        "avec encryptage optionnel. ")

    if format_type == "Interactif (Entraînement)":
        from convert_to_interactive_html import convert_to_interactive_html
        output_content = convert_to_interactive_html(export_data)
        extension = ".html"
        mime_type = "text/html"
        st.info("💡 Ce mode permet l'autocorrection immédiate pour les élèves.")

    elif format_type == "Examen (Serveur)":
        server_url = st.text_input("URL du serveur de réception", placeholder="https://script.google.com/...")
        if server_url:
            from convert_to_html_exam import convert_to_server_quiz
            output_content = convert_to_server_quiz(export_data, server_url)
            extension = ".html"
            mime_type = "text/html"
        else:
            st.warning("Veuillez saisir l'URL du serveur pour continuer.")

    elif format_type == "AMC (LaTeX)":
        neg_points = st.checkbox("Points négatifs (malus -1)", value=True)
        from amc_exporter import convert_to_amc_latex
        output_content = convert_to_amc_latex(export_data, use_negative_points=neg_points)
        extension = ".tex"
        mime_type = "text/x-tex"
        st.info("💡 Extraction au format LaTeX-AMC.")

    # Bouton de téléchargement final
    if output_content:
        st.divider()
        if not format_type == "Extrait (YAML)":
            st.download_button(
                label=f"⬇️ Télécharger {file_name}{extension}",
                data=output_content,
                file_name=f"{file_name}{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                #on_click=st.rerun # Pour fermer ou rafraîchir après action
            )
        else:
            st.session_state.output_content = str(output_content)
            st.session_state.output_qo_content = str(output_qo_content)
            st.download_button(
                label=f"⬇️ Télécharger {file_name}_{mode}{extension}",
                data=st.session_state.output_content,
                file_name=f"{file_name}_{mode}{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                key="download_full"
                #on_click=st.rerun # Pour fermer ou rafraîchir après action
            )
            st.download_button(
                label=f"⬇️ Télécharger {file_name}_qo_{mode}{extension} (questions only)",
                data=st.session_state.output_qo_content,
                file_name=f"{file_name}_{mode}_qo{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                key="download_qo"
                #on_click=st.rerun # Pour fermer ou rafraîchir après action
            )


# --- BARRE LATÉRALE (SIDEBAR) ---
data = st.session_state.data


st.sidebar.title("📂 Navigation")

## --- IMPORTER un YAML 

st.sidebar.divider()
st.sidebar.subheader("📥 Importer un nouveau fichier")
#st.sidebar.caption(f"(Fichier en cours : `{st.session_state['shared_fn']}`)")

uploaded_file = st.sidebar.file_uploader(
    "Choisir un fichier", 
    type=["yaml", "yml"],
    help="Charge le contenu d'un fichier YAML dans l'éditeur"
)

if uploaded_file is not None:
    #if st.sidebar.button("🚀 Charger ce fichier", use_container_width=True):
    if uploaded_file.name != st.session_state.last_uploaded_file:
        try:
            # 1. Lecture du contenu du fichier uploadé
            # On utilise l'instance 'yaml' (ruamel) déjà configurée
            data = yaml.load(uploaded_file)
            
            # 2. Mise à jour du session_state
            st.session_state.data = data
            st.session_state.data['title'] = data.get('title', 'Entrer un titre ici')
            st.session_state["quiz_title"] = st.session_state.data["title"]

            # 3. Mise à jour du nom de fichier pour les futures sauvegardes
            
            st.session_state["shared_fn"] = uploaded_file.name
            st.session_state.last_uploaded_file = uploaded_file.name

            # 4. Message de succès et rafraîchissement
            st.toast(f"Fichier `{st.session_state['shared_fn']}` chargé avec succès !")
            st.rerun()
            
        except Exception as e:
            st.sidebar.error(f"Erreur de lecture : {e}")

## -- CHOIX D'UNE QUESTION
st.sidebar.divider()
st.sidebar.subheader("🎰🎲♠ Gestion des quizzes")

quiz_ids = [k for k in data.keys() if k != 'title']
# ------- ajout des catégories -------

# 3. Widget de filtrage dans la sidebar

# -----
# --- Dans la sidebar, calcul des compteurs ---
quiz_ids_all = [k for k in data.keys() if k != 'title']

# 1. Compter les occurrences de chaque catégorie
filtrage_ancien = """
from collections import Counter
counts = Counter(data[qid].get('category', 'Aucune') for qid in quiz_ids_all)

# 2. Préparer la liste des catégories triées
raw_categories = sorted([c for c in counts.keys() if c != 'Aucune'])
if 'Aucune' in counts:
    raw_categories.insert(0, 'Aucune')

# 3. Créer les labels d'affichage avec les compteurs
# On garde un dictionnaire pour retrouver le nom réel de la catégorie après sélection
cat_display_map = {f"{c} ({counts[c]})": c for c in raw_categories}
cat_display_map[f"Toutes ({len(quiz_ids_all)})"] = "Toutes"

cat_options_display = list(cat_display_map.keys())

# 4. Widget Selectbox
selected_display = st.sidebar.selectbox(
    "Filtrer par catégorie", 
    cat_options_display,
    index=st.session_state.get('last_cat_idx', 0)
)
st.session_state.last_cat_idx = cat_options_display.index(selected_display)

# 5. Récupération de la vraie valeur pour le filtrage
selected_cat = cat_display_map[selected_display]
"""

# Filtre Catégorie (utilise sorted_cats préparé plus haut)
cat_options = [f"Toutes ({len(quiz_ids_all)})"] + [f"{c} ({cat_counts[c]})" for c in sorted_cats]
selected_cat_ui = st.sidebar.selectbox("Catégorie", cat_options)
selected_cat = selected_cat_ui.split(" (")[0] if selected_cat_ui != "Toutes" else "Toutes"

# Filtre Tags (utilise sorted_tags préparé plus haut)
selected_tags = st.sidebar.multiselect("Filtrer par Tags", 
                            placeholder="Choisir un tag", options=sorted_tags)

# 4. Logique de Filtrage Conjoint
filtered_ids = []
for qid in quiz_ids_all:
    q_cat = data[qid].get('category', 'Aucune')
    q_tags = data[qid].get('tags', [])
    
    # Vérification catégorie
    match_cat = (selected_cat == "Toutes" or q_cat == selected_cat)
    # Vérification tags (la question doit contenir TOUS les tags sélectionnés)
    match_tags = all(tag in q_tags for tag in selected_tags)
    
    if match_cat and match_tags:
        filtered_ids.append(qid)

# 5. Affichage du résultat final dans la navigation
#st.sidebar.divider()
#st.sidebar.subheader(f"Résultats ({len(filtered_ids)})")

filtrage_ancien = """# 6. Filtrage effectif
if selected_cat == "Toutes":
    quiz_ids = quiz_ids_all
else:
    quiz_ids = [qid for qid in quiz_ids_all if data[qid].get('category', 'Aucune') == selected_cat]
"""

quiz_ids = filtered_ids
# -----

bozo = """cat_options = ["Toutes"] + category_list
selected_cat = st.sidebar.selectbox(
    "Filtrer par catégorie", 
    cat_options,
    index=st.session_state.get('last_cat_idx', 0)
)

# On mémorise l'index pour le prochain rerun
st.session_state.last_cat_idx = cat_options.index(selected_cat)

# Filtrage effectif
if selected_cat == "Toutes":
    quiz_ids = quiz_ids_all
else:
    quiz_ids = [qid for qid in quiz_ids_all if data[qid].get('category', 'Aucune') == selected_cat]
"""

# --- Le reste de votre logique de navigation ---
machin = '''if 'current_quiz' not in st.session_state or st.session_state.current_quiz not in quiz_ids:
    st.session_state.current_quiz = quiz_ids[0] if quiz_ids else None

selected_quiz = st.sidebar.selectbox(
    f"Choisir une question parmi {len(filtered_ids)}", 
    quiz_ids, 
    key="current_quiz", #"nav_select", 
    index=quiz_ids.index(st.session_state.current_quiz) if st.session_state.current_quiz in quiz_ids else 0
)
st.session_state.current_quiz = selected_quiz
'''
# On trouve la position de la question actuelle dans la liste
idx = filtered_ids.index(st.session_state.current_quiz) if st.session_state.current_quiz in filtered_ids else 0

selected_quiz = st.sidebar.selectbox(
    f"Choisir une question parmi {len(filtered_ids)}", 
    quiz_ids, 
    index=quiz_ids.index(st.session_state.current_quiz) if st.session_state.current_quiz in quiz_ids else 0
    )
# On met à jour la session SEULEMENT si l'utilisateur a cliqué sur le menu
if selected_quiz != st.session_state.current_quiz:
    st.session_state.current_quiz = selected_quiz
    st.rerun()
# -------------------------------------


# --- ACTIONS SUR LE QUIZ SÉLECTIONNÉ ---

col1, col2 = st.sidebar.columns(2)

with col1:
    # 1. BOUTON CLONER
    if st.button("👯 Dupliquer", use_container_width=True, help="Copier ce quiz"):
        import copy
        numbers = [int(re.findall(r'\d+', k)[0]) for k in quiz_ids if re.findall(r'\d+', k)]
        next_num = max(numbers) + 1 if numbers else 1
        new_id = f"quiz{next_num}"
        st.session_state.data[new_id] = copy.deepcopy(data[selected_quiz])
        st.session_state.current_quiz = new_id
        st.rerun()

with col2:
    # 2. BOUTON SUPPRIMER AVEC CONFIRMATION
    # On utilise le session_state pour mémoriser si on a cliqué une première fois
    confirm_key = f"confirm_del_{selected_quiz}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        if st.button("🗑️ Supprimer", use_container_width=True, help="Supprimer ce quiz"):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        # Deuxième état : demande de confirmation
        if st.button("❗ Confirmer ?", use_container_width=True, type="primary"):
            if len(quiz_ids) > 1:
                del st.session_state.data[selected_quiz]
                remaining_ids = [k for k in st.session_state.data.keys() if k != 'title']
                st.session_state.current_quiz = remaining_ids[0]
                st.session_state[confirm_key] = False
                st.rerun()
            else:
                st.sidebar.error("Dernier quiz !")
                st.session_state[confirm_key] = False
        # Bouton pour annuler
        if st.button("Annuler", use_container_width=True):
            st.session_state[confirm_key] = False
            st.rerun()


# 4. BOUTON NOUVEAU
if st.sidebar.button("➕ Nouveau Quiz", use_container_width=True):
    numbers = [int(re.findall(r'\d+', k)[0]) for k in quiz_ids if re.findall(r'\d+', k)]
    next_num = max(numbers) + 1 if numbers else 1
    new_id = f"quiz{next_num}"
    st.session_state.data[new_id] = {
        "type": "qcm",
        "question": "Nouvelle question",
        "propositions": [{"proposition": "Choix 1", "expected": False}]
    }
    st.session_state.current_quiz = new_id
    st.rerun()


#st.sidebar.divider()

xzz = """
# 3. BOUTON ENREGISTRER (SYNC)
st.sidebar.subheader("💾 Sauvegarde Rapide")

st.sidebar.text_input("Nom du fichier", key="fn_sidebar", on_change=update_from_sidebar)

if st.sidebar.button("💾 SAUVEGARDER (Sidebar)", key="btn_side_save"):
    # On utilise .get() avec une valeur de secours pour éviter le crash
    fname = st.session_state.get("fn_sidebar") or st.session_state["shared_fn"]
    save_my_yaml(fname)
"""

# --- SECTION EXPORT (Nouvelle version)---
st.sidebar.divider()
st.sidebar.title("📤 Exportation")

# Initialisation du dictionnaire de sélection
if 'selected_for_export' not in st.session_state:
    st.session_state.selected_for_export = {qid: False for qid in quiz_ids}

# 1. BOUTONS TOUT COCHER / DÉCOCHER
col_all1, col_all2 = st.sidebar.columns(2)
if col_all1.button("✅ Tout cocher", use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = True
        # On force la mise à jour des clés des widgets
        st.session_state[f"check_side_{qid}"] = True
        st.session_state[f"check_main_{qid}"] = True
    st.rerun()

if col_all2.button("❌ Tout décocher", use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = False
        st.session_state[f"check_side_{qid}"] = False
        st.session_state[f"check_main_{qid}"] = False
    st.rerun()

# 2. ZONE DE SÉLECTION (Cases à cocher)
with st.sidebar.expander("Sélectionner les questions", expanded=False):
    for qid in quiz_ids:
        side_key = f"check_side_{qid}"
        # On s'assure que la clé du widget existe et est alignée sur le dictionnaire
        if side_key not in st.session_state:
            st.session_state[side_key] = st.session_state.selected_for_export.get(qid, False)

        st.checkbox(
            qid, 
            key=side_key,
            on_change=sync_export,
            args=(qid, side_key)
        )
        

# 2. Menu de choix du format
selected_qids = [qid for qid in quiz_ids if st.session_state.selected_for_export.get(qid, False)]

if selected_qids:
    st.sidebar.markdown(f"**{len(selected_qids)} question(s) sélectionnée(s)**")
    
    # Préparation de l'export_data réindexé (votre logique existante)
    export_data = {"title": data.get('title', 'Sans titre')}
    for i, old_id in enumerate(selected_qids):
        export_data[f"quiz{i+1}"] = copy.deepcopy(data[old_id])

    # Le menu déroulant d'export
    export_format = st.sidebar.selectbox(
        "Choisir le format d'export",
        ["---", "Extrait (YAML)", "Interactif (Entraînement)", "Examen (Serveur)", "AMC (LaTeX)"]
    )

    if export_format != "---":
        if st.sidebar.button("Configurer & Exporter", use_container_width=True):
            export_config_dialog(export_data, export_format)
            


else:
    st.sidebar.info("Cochez des questions pour exporter.")


zzz = """
# --- SECTION EXPORT ---
st.sidebar.divider()
st.sidebar.title("📤 Exportation")

# Initialisation du dictionnaire de sélection
if 'selected_for_export' not in st.session_state:
    st.session_state.selected_for_export = {qid: False for qid in quiz_ids}

# 1. BOUTONS TOUT COCHER / DÉCOCHER
col_all1, col_all2 = st.sidebar.columns(2)
if col_all1.button("✅ Tout cocher", use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = True
        # On force la mise à jour des clés des widgets
        st.session_state[f"check_side_{qid}"] = True
        st.session_state[f"check_main_{qid}"] = True
    st.rerun()

if col_all2.button("❌ Tout décocher", use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = False
        st.session_state[f"check_side_{qid}"] = False
        st.session_state[f"check_main_{qid}"] = False
    st.rerun()

# 2. ZONE DE SÉLECTION (Cases à cocher)
with st.sidebar.expander("Sélectionner les questions", expanded=False):
    for qid in quiz_ids:
        side_key = f"check_side_{qid}"
        # On s'assure que la clé du widget existe et est alignée sur le dictionnaire
        if side_key not in st.session_state:
            st.session_state[side_key] = st.session_state.selected_for_export.get(qid, False)

        st.checkbox(
            qid, 
            key=side_key,
            on_change=sync_export,
            args=(qid, side_key)
        )
        
        
        

# 3. PRÉPARATION DES DONNÉES ET RÉINDEXATION
selected_qids = [qid for qid in quiz_ids if st.session_state.selected_for_export.get(qid, False)]

if selected_qids:
    
    # Création du nouvel objet avec réindexation
    export_data = {"title": f"Export - {data.get('title', 'Sans titre')}"}
    
    for i, old_id in enumerate(selected_qids):
        new_id = f"quiz{i+1}"
        # On utilise deepcopy pour isoler totalement les données exportées
        export_data[new_id] = copy.deepcopy(data[old_id])
    
    # Génération du flux YAML
    stream = io.StringIO()
    yaml.dump(export_data, stream)
    yaml_string = stream.getvalue()
    
    # 4. BOUTON DE TÉLÉCHARGEMENT
    st.sidebar.download_button(
        label=f"💾 Télécharger ({len(selected_qids)} questions)",
        data=yaml_string,
        file_name="quiz_export.yaml",
        mime="text/yaml",
        use_container_width=True,
        type="primary"
    )

    # --- BOUTON EXPORT AMC ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 Export LaTeX")
    neg_points = st.sidebar.checkbox("Points négatifs (malus -1)", value=True)
    
    if st.sidebar.button("📄 Générer code AMC (LaTeX)", use_container_width=True):
        from amc_exporter import convert_to_amc_latex
        
        # On passe l'option à la fonction
        amc_code = convert_to_amc_latex(export_data, use_negative_points=neg_points)
        
        st.sidebar.download_button(
            label="⬇️ Télécharger le .tex",
            data=amc_code,
            file_name="quiz_amc.tex",
            mime="text/x-tex",
            use_container_width=True
        )
else:
    st.sidebar.info("Cochez des questions pour exporter.")

"""

wzz = """ #Commenté car double emploi zone centrale
# ----- PARAMETRES GENERAUX -----
st.sidebar.title("⚙️ Paramètres Généraux")
data['title'] = st.sidebar.text_input(
    "Titre du document", 
    data.get('title', ''), 
    help="Le titre principal du fichier YAML (clé 'title')."
)
"""

# --- ZONE PRINCIPALE ---
#st.title(f"📖 {data.get('title', 'Quiz sans titre')}")
#st.subheader(f"📖 {data.get('title', 'Quiz sans titre')}")
with st.container():
    st.markdown(
        """
        <style>
        /* Premier widget dans un container */
        .block-container > div:first-child {
            margin-top: 1.0rem !important;
            padding-top: 1.0rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    title = st.text_input(
        "Titre du document", 
        #value=f"📖 {st.session_state.data.get('title', 'Quiz sans titre')}",
        key="quiz_title",
        help="Le titre principal du fichier YAML (clé 'title') - Modifiable ici.",
        #label_visibility="collapsed",
    )

data["title"] = title.lstrip("📖 ").strip()
st.session_state.data["title"] = title.lstrip("📖 ").strip()
st.caption(f"Fichier en cours : `{st.session_state['shared_fn']}`")
col_save1, col_save2 = st.columns([6, 4])

with col_save1:
    # Champ texte central

    st.text_input(
    "Modifiez pour 'Enregistrer sous'.", 
    key="fn_main", 
    on_change=update_from_main,
    help="'Enregistrer sous'."
    )

with col_save2:
    st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
    
    btn_save, btn_download = st.columns([1, 1], gap="small")

    with btn_save:
        if st.button("💾 SAUVER", key="btn_main_save_final", use_container_width=True):
            fname = st.session_state.get("fn_main") or st.session_state["shared_fn"]
            save_my_yaml(fname)

    with btn_download:
        if st.button("⬇ DOWNLOAD", use_container_width=True):
            export_config_dialog(data, "YAML")


if st.session_state.current_quiz:
    q_id = st.session_state.current_quiz
    q_data = data[q_id]
    
    st.divider()
    #st.subheader(f"Édition de : {q_id}")

    avant = '''   #ajout synchro export
    col_title, col_check = st.columns([4, 1])

    with col_title:
        st.subheader(f"Édition de {selected_quiz}")

    with col_check:
        main_key = f"check_main_{selected_quiz}"
        
        st.session_state[main_key] = st.session_state.selected_for_export.get(selected_quiz, False)

        st.checkbox(
            "Exporter", 
            key=main_key,
            on_change=sync_export,
            args=(selected_quiz, main_key),
            help="Cocher pour inclure cette question dans le futur export YAML"
        )
'''
## avec flèches avant/après
if st.session_state.current_quiz and filtered_ids:
    current_idx = filtered_ids.index(st.session_state.current_quiz)
    
    # On crée 4 colonnes : [Bouton Prev, Titre, Bouton Next, Checkbox]
    # Les ratios [0.5, 4, 0.5, 1.5] permettent de garder les boutons petits et le titre large
    col_prev, col_title, col_next, col_check = st.columns([0.5, 3, 0.5, 1.5], vertical_alignment="center")

    with col_prev:
        if st.button("⬅️", disabled=(current_idx == 0)):
            st.session_state.current_quiz = filtered_ids[current_idx - 1]
            st.rerun()

    with col_next:
        if st.button("➡️", disabled=(current_idx == len(filtered_ids) - 1)):
            st.session_state.current_quiz = filtered_ids[current_idx + 1]
            st.rerun()

    with col_title:
        st.subheader(f"Édition de {st.session_state.current_quiz}")


    with col_check:
        main_key = f"check_main_{st.session_state.current_quiz}"
        # On s'assure que l'état est bien initialisé
        st.session_state[main_key] = st.session_state.selected_for_export.get(st.session_state.current_quiz, False)

        st.checkbox(
            "Exporter", 
            key=main_key,
            on_change=sync_export,
            args=(st.session_state.current_quiz, main_key),
            help="Cocher pour inclure cette question dans le futur export YAML"
        )
    
   # st.divider()
## fin avec  flèches avant/après

#fin ajout synchro export

# ----- ajout catégories -----

#    st.subheader(f"Édition de {st.session_state.current_quiz}")
    
    # Champ Catégorie avec suggestion des catégories existantes
    # On utilise un text_input pour permettre l'ajout de nouvelles catégories
   # Préparation des catégories existantes (formatage propre)
# One more
# Options du menu : Aucune, les existantes, et l'option de création
    current_cat = q_data.get('category', 'Aucune')
    all_cats = sorted(list(set(data[qid].get('category', 'Aucune') for qid in quiz_ids_all if data[qid].get('category', 'Aucune') != "Aucune")))
    menu_options = ["Aucune"] + all_cats + ["➕ Nouvelle catégorie..."]
    
    # On définit l'index par défaut
    default_idx = menu_options.index(current_cat) if current_cat in menu_options else 0

    # 2. Mise en page
    col_cat1, col_cat2 = st.columns([4,6])
    
    with col_cat1:
        selected_from_menu = st.selectbox(
            "🗂️ Catégorie",
            options=menu_options,
            index=default_idx,
            key=f"select_cat_{st.session_state.current_quiz}",
            help="Catégorie de la question",
        )

        # Si l'utilisateur veut créer une nouvelle catégorie
        if selected_from_menu == "➕ Nouvelle catégorie...":
            new_cat_name = st.text_input(
                "Nom de la nouvelle catégorie",
                placeholder="Saisissez le nom ici...",
                key=f"new_cat_input_{st.session_state.current_quiz}",
                help="Tapez pour ajouter la catégorie",
            )
            if new_cat_name: # Dès qu'il y a un nom, on l'applique
                if new_cat_name != current_cat:
                    q_data['category'] = new_cat_name
                    st.rerun()
        else:
            # Si on change pour une catégorie existante ou "Aucune"
            if selected_from_menu != current_cat:
                q_data['category'] = selected_from_menu
                st.rerun()

    out = '''with col_cat2:
        # Alignement vertical
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if all_cats:
            # On ré-affiche le joli bloc bleu avec la liste globale pour rappel
            st.info(f"**Existantes :**\n{', '.join(all_cats)}")
        else:
            st.caption("Aucune autre catégorie définie.")'''
    # fin one more
    with col_cat2:
        current_tags = q_data.get('tags', [])

        widget_key = f"tags_widget_{st.session_state.current_quiz}"
        state_key  = f"tags_state_{st.session_state.current_quiz}"

        # Init du state métier
        if state_key not in st.session_state:
            st.session_state[state_key] = current_tags.copy()

        # ⚠️ IMPORTANT : inclure les tags existants + sélectionnés
        all_tags = sorted(set(sorted_tags) | set(st.session_state[state_key]))

        updated_tags = st.multiselect(
            "🏷️ Tags (Difficulté, Thème secondaire...)",
            options=all_tags,
            default=st.session_state[state_key],   # ← autorisé (pas la clé widget)
            accept_new_options=True,
            placeholder="Choisir ou entrer un nouveau tag",
            key=widget_key
        )

        # ⬇️ logique métier (clé NON widget)
        if updated_tags != st.session_state[state_key]:
            st.session_state[state_key] = updated_tags
            q_data["tags"] = updated_tags


    # ----- fin ajout catégories -----

    # Fin ajout tags --------------------

    # 1. Question et Type
    col_q1, col_q2 = st.columns([4, 1])

    with col_q1:
        q_data['question'] = st.text_area(
            "Texte de la question", 
            q_data.get('question', ''), 
            height=80,
            help="Supporte le Markdown et le LaTeX (ex: $x^2$)."
        )
        render_preview("Question", q_data['question'])

    types_dispo = ["qcm", "numeric", "qcm-template", "numeric-template"]
    current_type = q_data.get('type', 'qcm')
    with col_q2:
        with st.container(border=True):
            q_data['type'] = st.selectbox(
                "Type", 
                types_dispo, 
                index=types_dispo.index(current_type) if current_type in types_dispo else 0,
                help="Définit le comportement de validation du quiz."
            )

            q_data['label'] =  st.text_input("Label", 
                                value=q_data.get('label', f'q:{q_id}'), 
                                help="Label de la question.")

    # 2. CONTRAINTES
    with st.expander("🔗 Contraintes logiques (XOR, IMPLY...)", expanded=False):
        if 'constraints' not in q_data: q_data['constraints'] = []
        
        # Récupération des labels pour le multiselect
        available_labels = [p.get('label', f'p{i}') for i, p in enumerate(q_data.get('propositions', []))]
        constraints_types = ["XOR", "SAME", "IMPLY", "IMPLYFALSE"]
        
        for idx, c in enumerate(q_data['constraints']):
            cc1, cc2, cc3, cc4 = st.columns([1, 2, 1, 0.5])
            
            c['type'] = cc1.selectbox("Type", constraints_types, index=constraints_types.index(c.get('type', 'XOR')) if c.get('type') in constraints_types else 0, key=f"ct_{q_id}_{idx}")
            c['indices'] = cc2.multiselect("Labels (max 2)", available_labels, default=[i for i in c.get('indices', []) if i in available_labels], max_selections=2, key=f"ci_{q_id}_{idx}")
            c['malus'] = cc3.number_input("Malus", value=int(c.get('malus', 1)), key=f"cm_{q_id}_{idx}")
            
            cc4.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            if cc4.button("🗑️", key=f"cdel_{q_id}_{idx}", help="Supprimer cette contrainte"):
                q_data['constraints'].pop(idx)
                st.rerun()
        
        if st.button("➕ Ajouter une contrainte"):
            q_data['constraints'].append({"indices": [], "type": "XOR", "malus": 1})
            st.rerun()

    # 3. PROPOSITIONS
    st.write("---")
    st.subheader("Propositions")
    if 'propositions' not in q_data: q_data['propositions'] = []
    
    for i, p in enumerate(q_data['propositions']):
        with st.expander(f"Proposition {i+1} : {p.get('label', '...')}", expanded=True):
            # Ligne 1 : Label et Correct/Expected
            c1, _, c3 = st.columns([2, 2, 1])
            p['label'] = c1.text_input("Label", p.get('label', ''), key=f"l_{q_id}_{i}", help="Identifiant court pour les contraintes.")
            
            exp_val = p.get('expected', False)
            if isinstance(exp_val, bool) or str(exp_val).lower() in ['true', 'false']:
                c3.markdown("<div style='padding-top: 35px;'></div>", unsafe_allow_html=True)
                p['expected'] = c3.checkbox("Correct ?", value=(str(exp_val).lower() == 'true'), key=f"e_{q_id}_{i}")
            else:
                # VALIDATION DE LA FORMULE ICI
                # On utilise on_change pour déclencher le script dès que le champ est modifié
                new_val = c3.text_input(
                    "Valeur attendue", 
                    value=str(exp_val), 
                    key=f"e_{q_id}_{i}",
                    on_change=trigger_rerun  # <--- FORCE LA MISE À JOUR
                )

                # On valide New_val DIRECTEMENT
                val_error = validate_fstring(new_val)

                if val_error:
                    st.error(val_error)
                    # Optionnel : On peut empêcher la mise à jour des données si erreur
                    # p['expected'] = exp_val 
                else:
                    p['expected'] = new_val

            p['proposition'] = st.text_area("Texte", p.get('proposition', ''), key=f"p_{q_id}_{i}", height=68)
            render_preview("Proposition", p['proposition'])

            p['reponse'] = st.text_area("Explication (reponse)", p.get('reponse', ''), key=f"r_{q_id}_{i}", height=68, help="Message affiché après la validation.")
            p['tip'] = st.text_area("Indice (tip)", p.get('tip', ''), key=f"t_{q_id}_{i}", height=68, help="Indice optionnel.")

            # Ligne 5 : Points et Suppression
            cb1, cb2, cb3 = st.columns([2, 2, 1])
            res_b = cb1.text_input("Bonus", str(p.get('bonus', '')), key=f"b_{q_id}_{i}", help="Points ajoutés (vide = 1).")
            res_m = cb2.text_input("Malus", str(p.get('malus', '')), key=f"m_{q_id}_{i}", help="Points retirés (vide = 0).")
            

            # --- ESPACE BOUTONS (Supprimer + Dupliquer) ---
            with cb3:
                # On remonte un peu le premier bouton avec un padding négatif si besoin
                st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
                
                if st.button("🗑️ Supprimer", key=f"del_{q_id}_{i}", use_container_width=True):
                    q_data['propositions'].pop(i)
                    st.rerun()

                # Bouton Dupliquer juste en dessous, sans espace supplémentaire
                if st.button("👯 Dupliquer", key=f"dup_prop_{q_id}_{i}", use_container_width=True):
                    import copy
                    new_prop = copy.deepcopy(p)
                    new_prop['label'] = f"{p.get('label', '')} copie"
                    q_data['propositions'].insert(i + 1, new_prop)
                    st.rerun()

            # Nettoyage des clés Bonus/Malus pour le YAML
            if res_b.strip(): p['bonus'] = int(res_b) if res_b.lstrip('-').isdigit() else res_b
            elif 'bonus' in p: del p['bonus']
            if res_m.strip(): p['malus'] = int(res_m) if res_m.lstrip('-').isdigit() else res_m
            elif 'malus' in p: del p['malus']

    if st.button("➕ Ajouter une proposition"):
        q_data['propositions'].append({"label": f"p{len(q_data['propositions'])+1}", "proposition": "", "expected": False})
        st.rerun()

else:
    st.info("Utilisez la barre latérale pour naviguer ou créer un nouveau quiz.")