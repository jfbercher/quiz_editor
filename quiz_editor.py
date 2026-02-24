import streamlit as st
from ruamel.yaml import YAML
import sys
import os
import re
import types


# Simulateur de f-strings
import numpy as np # For simulation in the validator
import random
import ast  #For simulation in the validator
import tokenize
import io, copy
from io import StringIO
from collections import Counter
import ast
from convert_quiz_format import convert_quiz_data_v1_to_v2
#from i18n import _

from i18n import init_i18n, set_language, get_translator


_ = init_i18n(default_lang="en")

# Language selection
#lang = st.sidebar.selectbox("Language", ["🇬🇧 en", "🇫🇷 fr"], index=["en", "fr"].index(st.session_state.lang))
languages = {
    "en": "🇬🇧 English",
    "fr": "🇫🇷 Français",
    "es": "🇪🇸 Spanish",
    "it": "🇮🇹 Italian",
    "de": "🇩🇪 German",
    "ar": "🇪🇨 Arabic",
    "cn": "🇨🇳 Chinese",
}

lang = st.sidebar.selectbox(
    "Language",
    options=list(languages.keys()),
    format_func=lambda x: languages[x],
    index=list(languages.keys()).index(st.session_state.lang),
)

if lang != st.session_state.lang:
    #print(f"Language changed from {st.session_state.lang} to {lang}")
    if "quiz_title" in st.session_state and st.session_state.quiz_title == _("New Quiz"): 
        _ = set_language(lang)
        st.session_state.quiz_title = _("New Quiz")
    else:
        _ = set_language(lang)
    st.rerun()


def trigger_rerun():
    # This function does nothing other than force Streamlit 
    # to reread the entire script with the new values.
    pass


def sync_export(qid, source_key):
    # We retrieve the value of the widget that has just changed

    val = st.session_state[source_key]
    # We update the reference dictionary
    st.session_state.selected_for_export[qid] = val
    
    # We synchronize the other widget so that it is up to date on the next display
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
        if end_brace == -1: return _("⚠️ Unclosed brace")
            
        full_block = text[start+1:end_brace].replace('\n', '')
        
        # We try to isolate the 'code' part from the 'formatting' 
        # We are looking for the rightmost ":" which is not in parentheses
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
            return f"⚠️ Error in '{{{code_part.strip()}}}' : {e.msg}"
            
        start = end_brace + 1
    return None

# Preview LaTeX
def render_preview(label, text):
    """Displays a preview if LaTeX or Markdown is present."""
    if text and ('$' in text or '{' in text):
        with st.container():
            #st.caption(f"Aperçu du rendu ({label}) :")
            st.markdown(
                f"<div style='font-size:0.8rem; color:gray; margin-bottom:-0.2rem;'>" \
                + _("Render preview ({label}) :</div>").format(label=label),
        unsafe_allow_html=True
    )
            st.info(text) # st.info renders Markdown and LaTeX between $ natively

def help_button(title, content, key):
    @st.dialog(title)
    def show():
        st.markdown(content)
    if st.button("❓", key=key):
        show()

def save_my_yaml(filename):
    yaml_format = YAML()
    yaml_format.preserve_quotes = True
    yaml_format.indent(mapping=2, sequence=4, offset=2)
    
    if not filename:
        st.error(_("The file name cannot be empty."))
        return
    
    # Cleaning Empty Constraints
    data_to_save = st.session_state.data
    for q in list(data_to_save.keys()):
        obj = data_to_save[q]
        if isinstance(obj, dict) and 'constraints' in obj and not obj['constraints']:
            del obj['constraints']
    
    with open(filename, 'w', encoding='utf-8') as f:
        yaml_format.dump(data_to_save, f)
    
    st.success(_("File saved successfully as `{filename}`").format(filename=filename))
    return data_to_save

def save_my_yaml_withoutst(filename):
    # 1. On initialise ruamel.yaml proprement
    yaml_format = YAML()
    yaml_format.preserve_quotes = True
    yaml_format.indent(mapping=2, sequence=4, offset=2) 
    
    data_to_save = st.session_state.data
    for q in list(data_to_save.keys()):
        obj = data_to_save[q]
        if isinstance(obj, dict) and 'constraints' in obj and not obj['constraints']:
            del obj['constraints']
    
    with open(filename, 'w', encoding='utf-8') as f:
        yaml_format.dump(data_to_save, f)

    return data_to_save

# Pour exports
if 'selected_for_export' not in st.session_state:
    # On initialise avec False pour tous les quiz existants
    st.session_state.selected_for_export = {}


# --- YAML CONFIGURATION  ---
# 
yaml = YAML()
yaml.preserve_quotes = True 
yaml.indent(mapping=2, sequence=4, offset=2)

# --- GESTION DU FICHIER ---
if len(sys.argv) > 1 and sys.argv[1].endswith(('.yaml', '.yml')):
    FILE_PATH = sys.argv[1]
else:
    FILE_PATH = "quiz.yaml"

# Initialization
# Initialization of session variables
if "shared_fn" not in st.session_state:
    st.session_state["shared_fn"] = FILE_PATH

if "fn_sidebar" not in st.session_state:
    st.session_state["fn_sidebar"] = st.session_state["shared_fn"]
if "fn_main" not in st.session_state:
    st.session_state["fn_main"] = st.session_state["shared_fn"]

if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None

if "output_content" not in st.session_state:
    st.session_state.output_content = None

def update_from_sidebar():
    val = st.session_state["fn_sidebar"]
    st.session_state["shared_fn"] = val
    st.session_state["fn_main"] = val

def update_from_main():
    val = st.session_state["fn_main"]
    st.session_state["shared_fn"] = val
    st.session_state["fn_sidebar"] = val



def load_data():
    if not os.path.exists(FILE_PATH):
        return {"title": _("New Quiz"), "quiz1": {"question": "", "propositions": []}}
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        data = yaml.load(f)
        data = convert_quiz_data_v1_to_v2(data)
        return data

# Session initialization for data persistence
if 'data' not in st.session_state:
    st.session_state.data = load_data()


if "quiz_title" not in st.session_state:
    st.session_state.quiz_title = st.session_state.data.get("title", _("Enter a title here"))

def extract_key_number(key):
    match = re.search(r'(\d+)$', key)
    return int(match.group(1)) if match else 0

def natural_key(string_): #Gemini
    """Splits the string into a list of strings and integers."""
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', string_)]

# sort data
data = st.session_state.data
st.session_state.data = {k: data[k] for k in sorted(data, key=natural_key)} #extract_key_number)}
data = st.session_state.data


# ---  DATA PREPARATION ---

quiz_ids_all = [k for k in data.keys() if k != 'title']

# We collect everything in one go
all_categories = set()
all_tags = set()
cat_counts = Counter()

for qid in quiz_ids_all:
    cat = data[qid].get('category', _('None'))
    all_categories.add(cat)
    cat_counts[cat] += 1
    
    tags = data[qid].get('tags', [])
    if isinstance(tags, list):
        all_tags.update(tags)

if _("None") in all_categories:
    all_categories.remove(_('None')) #insert(0, all_categories.pop(all_categories.index("Aucune")))
# Set up sorted lists for the widgets
sorted_cats = sorted(list(all_categories))
category_list = sorted_cats
sorted_tags = sorted(list(all_tags))

if "current_quiz" not in st.session_state:
    # We initialize with the first quiz in the list, if there is one.
    st.session_state.current_quiz = quiz_ids_all[0] if quiz_ids_all else None



# -----------------------------------

st.set_page_config(layout="wide", page_title=_("YAML Editor - {FILE_PATH}").format(FILE_PATH=FILE_PATH),  
                   page_icon="1F4C3.png") #📃")


# --- STYLE ---
st.markdown("""
<style>

/* ===== File Uploader compact ===== */
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] {{
    padding-top: 0.3rem;
    padding-bottom: 0.3rem;
    min-height: unset;
}}
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] div[data-testid="stFileUploaderDropzoneInstructions"] {{
    display: none;
}}
div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"] span[data-testid="stBaseButton-secondary"] {{
    margin: 0 auto;
}}
div[data-testid="stFileUploader"] ul {{
    display: none;
}}

/* ===== Main title ===== */
input[aria-label="{doctitle}"] {{
    font-size: 1.75rem !important;
    font-weight: 600 !important;
    border: none !important;
    background: transparent !important;
}}
input[aria-label="{doctitle}"]:focus {{
    outline: none !important;
    box-shadow: none !important;
}}

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] {{
    padding-top: 0rem;
}}
section[data-testid="stSidebar"] .block-container {{
    gap: 0.35rem;
}}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    margin-bottom: 0.25rem;
}}
section[data-testid="stSidebar"] hr {{
    margin-top: 0.25rem;
    margin-bottom: 0.25rem;
}}
[data-testid="stSidebarHeader"] {{
    height: 1.0rem;
    min-height: 0.5rem;
    padding: 0;
    margin: 0;
}}
[data-testid="stLogoSpacer"] {{
    display: none;
}}
[data-testid="stSidebarCollapseButton"] {{
    margin-top: 0;
    padding: 0;
}}

/* ===== Header principal ===== */
header[data-testid="stHeader"] {{
    height: 2rem;
    min-height: 2rem;
    padding: 0;
    margin: 0;
}}
div[data-testid="stToolbar"] {{
    padding: 0;
    margin: 0;
    height: 2rem;
}}
div[data-testid="stToolbarActions"],
div[data-testid="stAppDeployButton"],
span[data-testid="stMainMenu"] {{
    margin-top: 0;
    padding-top: 0;
}}

/* ===== Container principal ===== */
.block-container {{
    padding-top: 0rem;
    padding-bottom: 0.5rem;
}}

</style>
""".format(doctitle=_("Document Title")), unsafe_allow_html=True)

def prepare_data(indata, output_file, mode="crypt", pwd=""):    
    from labquiz.putils import crypt_data, encode_data
    from pathlib import Path
     
    import copy
    # Lecture du fichier YAML
    data = copy.deepcopy(indata)

    # Suffle propositions for each quiz
    for quiz_name, quiz_content in data.items():
        if "propositions" in quiz_content:
            random.shuffle(quiz_content["propositions"])
            
    # Questions only
    data_only = copy.deepcopy(data)
    # removing hints for every quiz
    for quiz_name, quiz_content in data_only.items():
        if quiz_name == "title": continue 
        quiz_content.pop("constraints", None)
        for prop in quiz_content["propositions"]:
            keys_to_remove = {"expected", "answer", "tip"}
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
        st.warning(_("⚠️ File encrypted with password. Be sure to use the `mandatoryInternet=True` option when initializing the quiz")) 
        #("⚠️ File crypted with pwd. Ensure to use the `mandatoryInternet=True` option in quiz init")   
        #st.warning("⚠️ File crypted with pwd. Ensure to use the `mandatoryInternet=True` option in quiz init")    
    
    return data_out, data_only_out

# Exports possibles (dans la sidebar)
@st.dialog(_("Configure & Export"))
def export_config_dialog(selected_qids, format_type):
    st.subheader(f"Format : {format_type}")
    
    # Common field: Filename
    default_name = _("my_quiz")
    file_name = st.text_input(_("File name (without extension)"), value=default_name)
    reindex_labels = st.checkbox(_("Reindex question labels"), 
                    help=_("Reindex to ensure continuity of labels, e.g.: quiz1, quiz2, etc."), value=False)

    export_data = {"title": data.get('title', _('Untitled'))}    
    if reindex_labels:
        for i, old_id in enumerate(selected_qids):
            export_data[f"quiz{i+1}"] = copy.deepcopy(data[old_id])
    else:
        for old_id in selected_qids:
            export_data[old_id] = copy.deepcopy(data[old_id])

    # Initialisation des variables  
    output_content = ""
    output_qo_content = ""
    extension = ""
    mime_type = ""

    # Options spécifiques selon le format
    if format_type == _("Extract (YAML)"):
        fmt = st.radio("Type d'export", [_("Encrypted YAML"), _("Encoded YAML"), _("Unencoded YAML")])
        pwd = ""
        if fmt == _("Encrypted YAML"):
            mode = "crypt"
        elif fmt == _("Encoded YAML"):
            mode = "enc"
        else:
            mode = "yml"
        if mode == "crypt":
            col_crypt1, col_crypt2  = st.columns([6, 4])
            with col_crypt1:
                pwd = st.text_input(_("Password"), type="password", help=_("💡 This pwd participates in encryption"))
        outdata, outdata_only = prepare_data(export_data, file_name, mode=mode, pwd=pwd)
        stream = StringIO()
        yaml.dump(outdata, stream)
        output_content = stream.getvalue()
        stream2 = StringIO()
        yaml.dump(outdata_only, stream2)
        output_qo_content = stream2.getvalue()
        extension = ".yaml"
        mime_type = "text/plain"
        st.info(_("💡 This mode allows you to save all or part of the questions in a new file, ") \
        + _("with optional encryption."))

    if format_type == _("Interactive (self-assessment)"):
        from convert_to_interactive_html import convert_to_interactive_html
        output_content = convert_to_interactive_html(export_data, lang=st.session_state.lang)
        extension = ".html"
        mime_type = "text/html"
        st.info(_("💡 This mode allows immediate self-correction for students."))

    elif format_type == _("Exam (Server)"):
        server_url = st.text_input(_("Receiving server URL"), placeholder="https://script.google.com/...")
        if server_url:
            from convert_to_html_exam import convert_to_server_quiz
            output_content = convert_to_server_quiz(export_data, server_url, lang=st.session_state.lang)
            extension = ".html"
            mime_type = "text/html"
        else:
            st.warning(_("Please enter the server URL to continue."))

    elif format_type == "AMC (LaTeX)":
        neg_points = st.checkbox(_("Negative points (-1 malus)"), value=True)
        from amc_exporter import convert_to_amc_latex
        output_content = convert_to_amc_latex(export_data, use_negative_points=neg_points)
        extension = ".tex"
        mime_type = "text/x-tex"
        st.info(_("💡 Extraction in LaTeX-AMC format."))

    # Bouton de téléchargement final
    if output_content:
        st.divider()
        if not format_type == _("Extract (YAML)"):
            st.download_button(
                label=_("⬇️ Download {file_name}{extension}").format(file_name=file_name, extension=extension),
                data=output_content,
                file_name=f"{file_name}{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                #on_click=st.rerun # To refresh after action
            )
        else:
            st.session_state.output_content = str(output_content)
            st.session_state.output_qo_content = str(output_qo_content)
            if mode == "yml": 
                mode = ""
            else:
                mode = f"_{mode}"
            st.download_button(
                label=_("⬇️ Download {file_name}{mode}{extension}").format(file_name=file_name, mode=mode, extension=extension),
                data=st.session_state.output_content,
                file_name=f"{file_name}{mode}{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                key="download_full"
                #on_click=st.rerun # To refresh after action
            )

            st.download_button(
                label=_("⬇️ Download {file_name}_qo{mode}{extension} (questions only)").format(file_name=file_name, mode=mode, extension=extension),
                data=st.session_state.output_qo_content,
                file_name=f"{file_name}_qo{mode}{extension}",
                mime=mime_type,
                use_container_width=True,
                type="primary",
                key="download_qo"
                #on_click=st.rerun # To refresh after action
            )


# --- SIDEBAR ---
data = st.session_state.data


st.sidebar.title(_("📂 Browse"))

## --- IMPORT A YAML 

st.sidebar.divider()
st.sidebar.subheader(_("📥 Import new file"))
#st.sidebar.caption(f"(Fichier en cours : `{st.session_state['shared_fn']}`)")

uploaded_file = st.sidebar.file_uploader(
    _("Choose file"), 
    type=["yaml", "yml"],
    help=_("Loads the contents of a YAML file into the editor")
)

if uploaded_file is not None:
    #if st.sidebar.button("🚀 Charger ce fichier", use_container_width=True):
    if uploaded_file.name != st.session_state.last_uploaded_file:
        try:
            data = yaml.load(uploaded_file)
            data = convert_quiz_data_v1_to_v2(data) #precaution
            
            # 2. updatesession_state
            st.session_state.data = data
            st.session_state.data['title'] = data.get('title', _('📖 Enter a title here'))
            st.session_state["quiz_title"] = st.session_state.data["title"]

            # 3. Updating filename for future save
            
            st.session_state["shared_fn"] = uploaded_file.name
            st.session_state.last_uploaded_file = uploaded_file.name

            # 4. Success message and refresh
            st.toast(_("File `{file_name}` loaded successfully!").format(file_name=st.session_state['shared_fn']))
            st.rerun()
            
        except Exception as e:
            st.sidebar.error(_("Read Error:") + f"{e}")

## -- CHOICE OF A QUESTION
st.sidebar.divider()
st.sidebar.subheader(_("🎰🎲♠ Quiz management"))

quiz_ids = [k for k in data.keys() if k != 'title']

# ------- adding categories -------

# 3. Filtering widget in sidebar

# -----
# --- In the sidebar, calculation of counters ---
quiz_ids_all = [k for k in data.keys() if k != 'title']

# Category filter (uses sorted_cats)
cat_options = [_("All ({len_all})").format(len_all=len(quiz_ids_all))] + [f"{c} ({cat_counts[c]})" for c in sorted_cats]
selected_cat_ui = st.sidebar.selectbox(_("Category"), cat_options)
all_cat_name =  _("All ({len_all})").split(" (")[0] #
selected_cat = selected_cat_ui.split(" (")[0] if selected_cat_ui != all_cat_name else all_cat_name

# Filtre Tags (utilise sorted_tags préparé plus haut)
selected_tags = st.sidebar.multiselect(_("Filter by Tags"), 
                            placeholder=_("Choose a tag"), options=sorted_tags)

# 4. Join filtering
filtered_ids = []

for qid in quiz_ids_all:
    q_cat = data[qid].get('category', _('None'))
    q_tags = data[qid].get('tags', [])
    
    # Category check
    match_cat = (selected_cat == all_cat_name or q_cat == selected_cat)
    # Tag verification (the question must contain ALL selected tags)
    match_tags = all(tag in q_tags for tag in selected_tags)
 
    if match_cat and match_tags:
        filtered_ids.append(qid)

# 5. Displaying final result in navigation
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


# Position of current question in list
idx = filtered_ids.index(st.session_state.current_quiz) if st.session_state.current_quiz in filtered_ids else 0

selected_quiz = st.sidebar.selectbox(
    _("Choose a question from {lenf}").format(lenf=len(filtered_ids)), 
    quiz_ids, 
    index=quiz_ids.index(st.session_state.current_quiz) if st.session_state.current_quiz in quiz_ids else 0
    )
# The session is updated ONLY if the user has clicked on the menu
if selected_quiz != st.session_state.current_quiz:
    st.session_state.current_quiz = selected_quiz
    st.rerun()
# -------------------------------------


# --- ACTIONS ON SELECTED QUIZ ---

col1, col2 = st.sidebar.columns(2)

with col1:
    # 1. BOUTON CLONER
    if st.button(_("👯 Duplicate"), use_container_width=True, help="Copier ce quiz"):
        import copy
        numbers = [int(re.findall(r'\d+', k)[0]) for k in quiz_ids if re.findall(r'\d+', k)]
        next_num = max(numbers) + 1 if numbers else 1
        new_id = f"quiz{next_num}"
        st.session_state.data[new_id] = copy.deepcopy(data[selected_quiz])
        st.session_state.current_quiz = new_id
        st.rerun()

with col2:
    # 2. DELETE BUTTON WITH CONFIRMATION
    confirm_key = f"confirm_del_{selected_quiz}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        if st.button(_("🗑️ Delete"), use_container_width=True, help="Supprimer ce quiz"):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        # Confirmation request
        if st.button(_("❗ Confirm?"), use_container_width=True, type="primary"):
            if len(quiz_ids) > 1:
                del st.session_state.data[selected_quiz]
                remaining_ids = [k for k in st.session_state.data.keys() if k != 'title']
                st.session_state.current_quiz = remaining_ids[0]
                st.session_state[confirm_key] = False
                st.rerun()
            else:
                st.sidebar.error(_("Last quiz!"))
                st.session_state[confirm_key] = False
        # Cancel button
        if st.button(_("Cancel"), use_container_width=True):
            st.session_state[confirm_key] = False
            st.rerun()


# 4. BUTTON NEW QUIZ
OldNewQuiz = '''if st.sidebar.button(_("➕ New Quiz"), use_container_width=True):
    numbers = [int(re.findall(r'\d+', k)[0]) for k in quiz_ids if re.findall(r'\d+', k)]
    next_num = max(numbers) + 1 if numbers else 1
    new_id = f"quiz{next_num}"
    st.session_state.data[new_id] = {
        "type": "numeric",
        "question": _("New question"),
        "propositions": [{"proposition": _("Choice 1"), "expected": 3.14}]
    }
    st.session_state.current_quiz = new_id
    st.rerun()'''

# NEW NEW QUIZ

# Available quiz types
available_types = ["mcq", "numeric", "mcq-template", "numeric-template"]

# Popover replaces the previous "New Quiz" button + state flag
with st.sidebar.popover(_("➕ New Quiz"), use_container_width=True):

    selected_type = st.selectbox(
        _("Select quiz type"),
        available_types,
        help=_("Defines the validation behavior of the quiz.")
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(_("Create"), use_container_width=True):

            # Compute next quiz ID
            numbers = [
                int(re.findall(r'\d+', k)[0])
                for k in quiz_ids
                if re.findall(r'\d+', k)
            ]
            next_num = max(numbers) + 1 if numbers else 1
            new_id = f"quiz{next_num}"

            # Create quiz structure depending on selected type
            if selected_type in ["numeric", "numeric-template"]:
                expval = 3.14 if selected_type == "numeric" else "f'{a+b:.4f}'"
                new_data = {
                    "type": selected_type,
                    "question": _("New question"),
                    "propositions": [
                        {"proposition": _("Choice 1"), "expected": expval}
                    ]
                }

            elif selected_type in ["mcq", "mcq-template"]:
                expval = False if selected_type == "mcq" else "f'{a} in {b}'"
                new_data = {
                    "type": selected_type,
                    "question": _("New question"),
                    "propositions": [
                        {"proposition": _("Choice 1"), "expected": expval}
                    ]
                }

            # Store quiz and update current selection
            st.session_state.data[new_id] = new_data
            st.session_state.current_quiz = new_id

            st.rerun()

    with col2:
        st.write("")  # Optional spacer (keeps layout symmetrical)

# END NEW NEW QUIZ


#st.sidebar.divider()


# --- EXPORT SECTION (New version)---
st.sidebar.divider()
st.sidebar.title(_("📤 Export"))

# Initialization of the selection dictionary
if 'selected_for_export' not in st.session_state:
    st.session_state.selected_for_export = {qid: False for qid in quiz_ids}

# 1. CHECK/UNCHECK ALL BUTTONS
col_all1, col_all2 = st.sidebar.columns(2)
if col_all1.button(_("✅ Select all"), use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = True
        # Force updating of widget keys
        st.session_state[f"check_side_{qid}"] = True
        st.session_state[f"check_main_{qid}"] = True
    st.rerun()

if col_all2.button(_("❌ Deselect all"), use_container_width=True):
    for qid in quiz_ids:
        st.session_state.selected_for_export[qid] = False
        st.session_state[f"check_side_{qid}"] = False
        st.session_state[f"check_main_{qid}"] = False
    st.rerun()

# 2. SELECTION AREA (Checkboxes)
with st.sidebar.expander(_("Select questions"), expanded=False):
    for qid in quiz_ids:
        side_key = f"check_side_{qid}"
        # We ensure that the widget key exists 
        if side_key not in st.session_state:
            st.session_state[side_key] = st.session_state.selected_for_export.get(qid, False)

        st.checkbox(
            qid, 
            key=side_key,
            on_change=sync_export,
            args=(qid, side_key)
        )
        

# 2. Format choice menu
selected_qids = [qid for qid in quiz_ids if st.session_state.selected_for_export.get(qid, False)]

if selected_qids:
    st.sidebar.markdown(_("**{lsq} question(s) selected**").format(lsq=len(selected_qids)))
    
    # Preparing the export_data
    export_data = {"title": data.get('title', 'Sans titre')}
    for i, old_id in enumerate(selected_qids):
        export_data[f"quiz{i+1}"] = copy.deepcopy(data[old_id])

    # Export drop-down menu
    export_format = st.sidebar.selectbox(
        _("Choose export format"),
        ["---", _("Extract (YAML)"), _("Interactive (self-assessment)"), _("Exam (Server)"), "AMC (LaTeX)"]
    )

    if export_format != "---":
        if st.sidebar.button(_("Configure & Export"), use_container_width=True):
            export_config_dialog(selected_qids, export_format)
            


else:
    st.sidebar.info(_("Check questions to export."))



wzz = """ #Commenté car double emploi zone centrale
# ----- PARAMETRES GENERAUX -----
st.sidebar.title("⚙️ Paramètres Généraux")
data['title'] = st.sidebar.text_input(
    "Titre du document", 
    data.get('title', ''), 
    help="Le titre principal du fichier YAML (clé 'title')."
)
"""

# --- PRINCIPAL AREA ---
#st.title(f"📖 {data.get('title', 'Quiz sans titre')}")
#st.subheader(f"📖 {data.get('title', 'Quiz sans titre')}")
with st.container():
    st.markdown(
        """
        <style>
        .block-container > div:first-child {
            margin-top: 1.0rem !important;
            padding-top: 1.0rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    title = st.text_input(
        _("Document Title"), 
        #value=f"📖 {st.session_state.data.get('title', 'Quiz sans titre')}",
        key="quiz_title",
        help=_("The main title of the YAML file (key ‘title’) - Editable here."),
        #label_visibility="collapsed",
    )
data["title"] = title.lstrip("📖 ").strip()
st.session_state.data["title"] = title.lstrip("📖 ").strip()
#st.session_state["quiz_title"] = st.session_state.data["title"]
st.caption(_("Current file: `{shared_fn}`").format(shared_fn=st.session_state['shared_fn']))
col_save1, col_save2 = st.columns([6, 4])

with col_save1:

    st.text_input(
    _("Edit to ‘Save As’."), 
    key="fn_main", 
    on_change=update_from_main,
    help=_("‘Save As’.")
    )


with col_save2:
    st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)

    def build_yaml(fname):
        data_to_save = save_my_yaml(fname)
        stream = StringIO()
        yaml.dump(data_to_save, stream)
        return stream.getvalue()

    btn_save, btn_download = st.columns([1, 1], gap="small")

    with btn_save:
        if st.button(_("💾 Save"), key="btn_main_save_final",width="stretch"):
            fname = st.session_state.get("fn_main") or st.session_state["shared_fn"]
            st.session_state.output_content = build_yaml(fname)
            st.toast(_("YAML cleaned and saved ✔️"))

    with btn_download:
        if st.session_state.output_content is not None:
            fname = st.session_state.get("fn_main") or st.session_state["shared_fn"]
            st.download_button(
                label=_("Download!"),
                data=st.session_state.output_content,
                file_name=fname,
                mime="text/yaml",
                width="stretch",
                help=_("Only AFTER saving the YAML")
            )


if st.session_state.current_quiz:
    q_id = st.session_state.current_quiz
    q_data = data[q_id]
    
    st.divider()
    #st.subheader(f"Édition de : {q_id}")

## with arrows before/after
if st.session_state.current_quiz and filtered_ids:
    current_idx = filtered_ids.index(st.session_state.current_quiz)
    
    # We create 4 columns: [Prev Button, Title, Next Button, Checkbox] 
    # The ratios [0.5, 4, 0.5, 1.5] keep the buttons small and the title wide
    col_prev, col_title, col_next, col_check = st.columns([0.5, 3, 0.5, 1.5], vertical_alignment="center")

    with col_prev:
        if st.button("⬅️", disabled=(current_idx == 0)):
            st.session_state.current_quiz = filtered_ids[current_idx - 1]
            st.rerun()

    with col_next:
        if st.button("➡️", disabled=(current_idx == len(filtered_ids) - 1)):
            st.session_state.current_quiz = filtered_ids[current_idx + 1]
            st.rerun()
    def get_new_quiz_title():
        st.session_state.current_quiz = st.session_state.current_quiz_edit.split()[-1]

    with col_title:
        temp = '''st.session_state.current_quiz_edit = _("Editing {current_quiz}").format(current_quiz=st.session_state.current_quiz)
        edit_current_quiz = st.text_input(
        _("Editing {current_quiz}").format(current_quiz=st.session_state.current_quiz), 
        #value=f"📖 {st.session_state.data.get('title', 'Quiz sans titre')}",
        key="current_quiz_edit",
        help=_("The main title of the YAML file (key ‘title’) - Editable here."),
        on_change=get_new_quiz_title,
        #label_visibility="collapsed",
        )'''
        st.subheader(_("Editing {current_quiz}").format(current_quiz=st.session_state.current_quiz))


    with col_check:
        main_key = f"check_main_{st.session_state.current_quiz}"
        # We ensure that the state is correctly initialized
        st.session_state[main_key] = st.session_state.selected_for_export.get(st.session_state.current_quiz, False)

        st.checkbox(
            _("Export"), 
            key=main_key,
            on_change=sync_export,
            args=(st.session_state.current_quiz, main_key),
            help=_("Check to include this question in future YAML exports")
        )
    
   # st.divider()
## end of before/after arrows

#end add sync export

# ----- Add categories -----

#    st.subheader(f"Édition de {st.session_state.current_quiz}")
    
    # Category field with suggestion of existing categories
    # We use a text_input to allow the addition of new categories
   # Preparation of existing categories 
# Menu options: None, existing, and create option
    current_cat = q_data.get('category', _('None'))
    all_cats = sorted(list(set(data[qid].get('category', _('None')) for qid in quiz_ids_all if data[qid].get('category', _('None')) != _("None"))))
    menu_options = [_("None")] + all_cats + [_("➕ New category...")]
    
    # We define a default index
    default_idx = menu_options.index(current_cat) if current_cat in menu_options else 0

    # 2. Page layout
    col_cat1, col_cat2 = st.columns([4,6])
    
    with col_cat1:
        selected_from_menu = st.selectbox(
            _("🗂️ Category"),
            options=menu_options,
            index=default_idx,
            key=f"select_cat_{st.session_state.current_quiz}",
            help=_("Question category"),
        )

        # Si l'utilisateur veut créer une nouvelle catégorie
        if selected_from_menu == _("➕ New category..."):
            new_cat_name = st.text_input(
                _("Name of the new category"),
                placeholder=_("Enter the name here..."),
                key=f"new_cat_input_{st.session_state.current_quiz}",
                help=_("Type to add the categor"),
            )
            if new_cat_name: 
                if new_cat_name != current_cat:
                    q_data['category'] = new_cat_name
                    st.rerun()
        else:
            if selected_from_menu != current_cat:
                q_data['category'] = selected_from_menu
                st.rerun()

    # end one more
    with col_cat2:
        current_tags = q_data.get('tags', [])

        widget_key = f"tags_widget_{st.session_state.current_quiz}"
        state_key  = f"tags_state_{st.session_state.current_quiz}"

        # Init 
        if state_key not in st.session_state:
            st.session_state[state_key] = current_tags.copy()

        # ⚠️ IMPORTANT: include existing + selected tags
        all_tags = sorted(set(sorted_tags) | set(st.session_state[state_key]))

        updated_tags = st.multiselect(
            _("🏷️ Tags (Difficulty, Sub-theme...)"),
            options=all_tags,
            default=st.session_state[state_key],   
            accept_new_options=True,
            placeholder=_("Choose or enter a new tag"),
            key=widget_key
        )

        if updated_tags != st.session_state[state_key]:
            st.session_state[state_key] = updated_tags
            q_data["tags"] = updated_tags


    # ----- end adding categories -----

    # End adding tags --------------------

    # 1. Question and Type
    col_q1, col_q2 = st.columns([4, 1])

    with col_q1:
        q_data['question'] = st.text_area(
            _("Question text"), 
            q_data.get('question', ''), 
            height=80,
            help=_("Supports Markdown and LaTeX (e.g., $x^2$).")
        )
        render_preview("Question", q_data['question'])

    types_dispo = ["mcq", "numeric", "mcq-template", "numeric-template"]
    current_type = q_data.get('type', 'mcq')
    with col_q2:
        with st.container(border=True):
            q_data['type'] = st.selectbox(
                "Type", 
                types_dispo, 
                index=types_dispo.index(current_type) if current_type in types_dispo else 0,
                help=_("Defines the validation behavior of the quiz.")
            )

            q_data['label'] =  st.text_input(_("Label"), 
                                value=q_data.get('label', f'q:{q_id}'), 
                                help=_("Question label."))

    # IF TEMPLATE EDIT TEMPLATE VARIABLES FOR SIMULATION
    if q_data['type'] in ['mcq-template', 'numeric-template']:
        import numpy as np
        import pandas as pd


        # Local RNG instance (not stored in session_state)
        rng = np.random.default_rng()

        # --- Minimal UI state: store only row identifiers ---
        if "rows" not in st.session_state:
            st.session_state.rows = [0]  # List of row IDs

        def is_valid_identifier(name):
            """Check whether a string is a valid Python variable name."""
            return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name)

        def safe_eval(expr):
            """
            Evaluate expression in a restricted namespace.
            Only rng, numpy and pandas are allowed.
            """
            return eval(expr, {"__builtins__": {}}, {"rng": rng, "np": np, "pd": pd})
        
        # --- 1. Suggestion Helper ---
        def get_default_suggestion(var_type, var_structure, engine_display):
            """Logic to suggest a default string based on type/structure/engine."""
            #print("default_suggestion", "var_type", var_type, "var_structure", var_structure, "engine_display", engine_display)
            size = 1 if var_structure == "scalar" else 3
            if engine_display == "numpy rng.":
                if var_type == "int":
                    if size==1:
                        return f"integers(0, 10)"
                    return f"integers(0, 10, size={size})"
                elif var_type == "float":
                    if size==1:
                        return f"normal(0, 1)"
                    return f"normal(0, 1, size={size})"
                return f"normal(0, 1, size={size})"
            else:  # pandas
                if "DataFrame" in var_structure:
                    return "DataFrame(rng.normal(0, 1, (3,2)))"
                return "Series(rng.normal(0, 1, 3))"

        # --- 2. Callback for Automatic Updates ---
        def update_suggestion_callback(q_id, row_id):
            """Triggered when Type, Structure, or Engine changes to update the Call field."""
            type_key = f"type_{q_id}_{row_id}"
            struct_key = f"struct_{q_id}_{row_id}"
            engine_key = f"engine_{q_id}_{row_id}"
            call_key = f"call_{q_id}_{row_id}"
            
            # Update the call value in session_state immediately
            st.session_state[call_key] = get_default_suggestion(
                st.session_state[type_key],
                st.session_state[struct_key],
                st.session_state[engine_key]
            )

        # --- 3. Initialization ---
        # Ensure the session state for this question is initialized
        if q_id not in st.session_state:
            st.session_state[q_id] = types.SimpleNamespace()
        
        variables_dict = q_data.get("variables", {})
        # Initialize the row list
        st.session_state[q_id].rows = list(range(len(variables_dict)))
        
        # Pre-populate session_state with LOADED data so widgets find their values
        variables_dict = {k: variables_dict[k] for k in sorted(variables_dict)}
        for idx, (name, config) in enumerate(variables_dict.items()):
            st.session_state[f"name_{q_id}_{idx}"] = name
            st.session_state[f"name_{q_id}_{idx}_old"] = name
            st.session_state[f"type_{q_id}_{idx}"] = config.get("type", "int")
            st.session_state[f"struct_{q_id}_{idx}"] = config.get("structure", "scalar")
            st.session_state[f"engine_{q_id}_{idx}"] = config.get("engine", "numpy rng.")
            st.session_state[f"call_{q_id}_{idx}"] = config.get("call", 
                get_default_suggestion(
                    st.session_state[f"type_{q_id}_{idx}"],
                    st.session_state[f"struct_{q_id}_{idx}"],
                    st.session_state[f"engine_{q_id}_{idx}"]
                )
            )

        st.subheader(_("Template variables"))
        
        def on_change_update_and_save(q_id, row_id, update_suggestion=True):
            if update_suggestion: update_suggestion_callback(q_id, row_id)
            varname = st.session_state[f"name_{q_id}_{row_id}"]
            old_varname = st.session_state[f"name_{q_id}_{row_id}_old"]
            if varname != old_varname:
                # varname has changed - delete the old one
                st.session_state[f"name_{q_id}_{row_id}_old"] = varname
                if old_varname in q_data.get("variables", {}):
                    del q_data["variables"][old_varname]
            if is_valid_identifier(varname):
                var_dict = {
                'type' : st.session_state.get(f"type_{q_id}_{row_id}", "int"),
                "structure": st.session_state.get(f"struct_{q_id}_{row_id}", "scalar"),
                "engine": st.session_state.get(f"engine_{q_id}_{row_id}", "numpy rng."),
                }
                var_dict["call"] = st.session_state.get(f"call_{q_id}_{row_id}",
                    get_default_suggestion( var_dict["type"], var_dict["structure"], var_dict["engine"]))
                if q_data.get("variables") is None:
                    q_data["variables"] = {}
                q_data["variables"][varname] = var_dict


        # --- Add Variable Button ---
        cols_header = st.columns([0.04, 1], gap="small")
        with cols_header[0]:
            help_button(
                _("Template variables"),
                _("""
                In the case of templates, define the *names* of variables, and 
                define how to generate values for html or $\LaTeX$-AMC exports.
                - size is ajustable,
                - default values are generated corresponding to type and size, but these can be edited. In particular, all distributions from [numpy Generator](https://numpy.org/doc/stable/reference/random/generator.html) can be used.
                """), 
                key="add_variable"
                )
        with cols_header[1]:
            if st.button(_("➕ Add variable"), key=f"btn_add_{q_id}"):
                new_id = max(st.session_state[q_id].rows) + 1 if st.session_state[q_id].rows else 0
                st.session_state[q_id].rows.append(new_id)
                # When adding a row, initialize its call to the default suggestion
                st.session_state[f"call_{q_id}_{new_id}"] = get_default_suggestion("int", "scalar", "numpy rng.")

                #st.rerun()

        # Temporary storage for the current script run
        active_variables = {}

        # --- 4. Render Rows ---
        for row_id in st.session_state[q_id].rows:
            cols = st.columns([1.5, 1, 1.2, 1.2, 2.5, 0.6])
            
            # Use keys directly. Streamlit will look into session_state[key] 
            # to find the value to display.
            key_name = f"name_{q_id}_{row_id}"
            # Key for storing the old value
            if f"{key_name}_old" not in st.session_state:
                st.session_state[f"{key_name}_old"] = ""
            var_name = cols[0].text_input("Name", 
                            key=f"name_{q_id}_{row_id}", 
                            label_visibility="collapsed",
                            on_change=on_change_update_and_save,
                            args=(q_id, row_id)
                            ) 
            
            var_type = cols[1].selectbox(
                "Type", ["int", "float"], 
                key=f"type_{q_id}_{row_id}",
                on_change=on_change_update_and_save, args=(q_id, row_id),
                label_visibility="collapsed"
            )
            
            var_struct = cols[2].selectbox(
                "Structure", ["scalar", "list", "numpy array", "pandas Series", "pandas DataFrame"],
                key=f"struct_{q_id}_{row_id}",
                on_change=on_change_update_and_save, args=(q_id, row_id),
                label_visibility="collapsed"
            )
            
            engine_disp = cols[3].selectbox(
                "Engine", ["numpy rng.", "pandas."],
                key=f"engine_{q_id}_{row_id}",
                on_change=on_change_update_and_save, args=(q_id, row_id),
                label_visibility="collapsed"
            )
            
            engine_call = cols[4].text_input("Call", 
                            key=f"call_{q_id}_{row_id}", 
                            on_change=on_change_update_and_save, args=(q_id, row_id, False),
                            label_visibility="collapsed")

            # Delete Row
            if cols[5].button("❌", key=f"del_{q_id}_row{row_id}"):
                st.session_state[q_id].rows.remove(row_id)
                q_data["variables"].pop(var_name, None)
                st.rerun()

            # --- 5. Capture Valid Data ---
            # Only store if the variable has a name
            if var_name:
                active_variables[var_name] = {
                    "type": var_type,
                    "structure": var_struct,
                    "engine": engine_disp,
                    "call": engine_call
                }

            if var_name:
                if not is_valid_identifier(var_name):
                    st.error(_("'{name}' is not a valid Python identifier").format(name=var_name))
                else:
                    active_variables[var_name] = {
                        "type": var_type,
                        "structure": var_struct,
                        "engine": engine_disp,
                        "call": engine_call
                    }
                    # Map display engine to code prefix
                    engine_prefix = "rng." if engine_disp == "numpy rng." else "pd."
                    expression = f"{engine_prefix}{engine_call}"
                # Try to evaluate for preview
                try:
                    #print("expression", expression)
                    result = safe_eval(expression) # Replace with your actual eval logic
                    #print("result", result)
                    st.caption(f"Preview: `{var_name} = {expression}`; eg {result}")
                except Exception as e:
                    st.error(f"Error: {e}")

                # 3. PERSISTENCE: Save the accumulated rows into your main data structure
                # This ensures data[q_id] is always up to date with the UI
                q_data['variables'] = active_variables
                data[q_id]['variables'] = active_variables
                st.session_state.data = data

                # Debug print (optional)
                #print(f"Current State for {q_id}: {data[q_id]['variables']}")

    # END "IF TEMPLATE" 

    # 2. CONSTRAINTS
    with st.expander(_("🔗 Logical constraints (XOR, IMPLY...)"), expanded=False):
        if 'constraints' not in q_data: q_data['constraints'] = []
        
        # Retrieving labels for multiselect
        available_labels = [p.get('label', f'p{i}') for i, p in enumerate(q_data.get('propositions', []))]
        constraints_types = ["XOR", "SAME", "IMPLY", "IMPLYFALSE"]
        
        for idx, c in enumerate(q_data['constraints']):
            cc1, cc2, cc3, cc4 = st.columns([1, 2, 1, 0.5])
            
            c['type'] = cc1.selectbox("Type", constraints_types, index=constraints_types.index(c.get('type', 'XOR')) if c.get('type') in constraints_types else 0, key=f"ct_{q_id}_{idx}")
            c['indices'] = cc2.multiselect("Labels (max 2)", available_labels, default=[i for i in c.get('indices', []) if i in available_labels], max_selections=2, key=f"ci_{q_id}_{idx}")
            c['malus'] = cc3.number_input("Malus", value=int(c.get('malus', 1)), key=f"cm_{q_id}_{idx}")
            
            cc4.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
            if cc4.button("🗑️", key=f"cdel_{q_id}_{idx}", help=_("Remove this constraint")):
                q_data['constraints'].pop(idx)
                st.rerun()
        
        if st.button(_("➕ Add constraint")):
            q_data['constraints'].append({"indices": [], "type": "XOR", "malus": 1})
            st.rerun()

    # 3. PROPOSITIONS
    st.write("---")
    st.subheader(_("Propositions"))
    if 'propositions' not in q_data: q_data['propositions'] = []
    
    for i, p in enumerate(q_data['propositions']):
        with st.expander(f"Proposition {i+1} : {p.get('label', '...')}", expanded=True):
            # Ligne 1 : Label et Correct/Expected
            c1, c2, c3 = st.columns([2, 2, 1])
            p['label'] = c1.text_input(_("Label"), p.get('label', ''), key=f"l_{q_id}_{i}", help=_("Short identifier for the proposition."))
            
            if q_data['type'] in ['mcq']:
                exp_val = p.get('expected', False)
            #if isinstance(exp_val, bool) or str(exp_val).lower() in ['true', 'false']:
                c3.markdown("<div style='padding-top: 35px;'></div>", unsafe_allow_html=True)
                p['expected'] = c3.checkbox(_("Correct?"), value=(str(exp_val).lower() == 'true'), key=f"e_{q_id}_{i}")
            else:   # Here we are in numeric or qcm-template, thus we display a text-input
                # We use on_change to trigger the script as soon as the field is modified
                exp_val = p.get('expected', 3.14)
                new_val = c3.text_input(
                    _("Expected value"), 
                    value=str(exp_val), 
                    key=f"e_{q_id}_{i}",
                    on_change=trigger_rerun  # <---FORCE THE UPDATE
                )

                # Direct validation of New_val
                val_error = validate_fstring(new_val)

                if val_error:
                    st.error(val_error)
                else:
                    p['expected'] = new_val

            p['proposition'] = st.text_area(_("Text"), p.get('proposition', ''), key=f"p_{q_id}_{i}", height=68)
            render_preview(_("Proposition"), p['proposition'])

            p['answer'] = st.text_area(_("Explanation (answer)"), p.get('answer', ''), key=f"r_{q_id}_{i}", height=68, help=_("Message displayed after validation."))
            p['tip'] = st.text_area(_("Hint (tip)"), p.get('tip', ''), key=f"t_{q_id}_{i}", height=68, help=_("Optional hint."))

            # 
            cb1, cb2, cb3 = st.columns([2, 2, 1])
            res_b = cb1.text_input(_("Bonus"), str(p.get('bonus', '')), key=f"b_{q_id}_{i}", help=_("Points added (default = 1)."))
            res_m = cb2.text_input(_("Penalty"), str(p.get('malus', '')), key=f"m_{q_id}_{i}", help=_("Points deducted (default = 0)."))
            
            if q_data['type'] in ['numeric', 'numeric-template']:
                res_tol = cb1.text_input(_("Tolerance %"), str(p.get('tolerance', '')), key=f"tp_{q_id}_{i}", help=_("Tolerance in % (default = 0)."))
                res_tolm = cb2.text_input(_("Tolerance Abs"), str(p.get('tolerance_abs', '')), key=f"ta_{q_id}_{i}", help=_("Tolerance in absolute value (default = 0.01)."))
            
            # --- BUTTONS SPACE (Delete + Duplicate) ---
            with cb3:
                # We move the first button up a little 
                st.markdown("<div style='padding-top: 28px;'></div>", unsafe_allow_html=True)
                
                if st.button(_("🗑️ Delete"), key=f"del_{q_id}_{i}", use_container_width=True):
                    q_data['propositions'].pop(i) 
                    st.rerun()

                # Duplicate button just below, with no extra space
                if st.button(_("👯 Duplicate"), key=f"dup_prop_{q_id}_{i}", use_container_width=True):
                    import copy
                    new_prop = copy.deepcopy(p)
                    new_prop['label'] = f"{p.get('label', '')} " + _("copy") 
                    q_data['propositions'].insert(i + 1, new_prop)
                    st.rerun()

            # Cleaning Bonus/Malus keys for YAML
            if res_b.strip(): p['bonus'] = int(res_b) if res_b.lstrip('-').isdigit() else res_b
            elif 'bonus' in p: del p['bonus']
            if res_m.strip(): p['malus'] = int(res_m) if res_m.lstrip('-').isdigit() else res_m
            elif 'malus' in p: del p['malus']

    if st.button(_("➕ Add a proposal")):
        q_data['propositions'].append({"label": f"p{len(q_data['propositions'])+1}", "proposition": "", "expected": False})
        st.rerun()

else:
    st.info(_("Use the sidebar to navigate or create a new quiz."))