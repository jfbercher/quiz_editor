import re
import random
import math
import html

# --- CONFIGURATION ---
NB_ESSAIS_MAX = 3

def evaluate_fstring(text, context):
    """Remplace les expressions entre accolades par leurs valeurs calculées."""
    if not context or text is None:
        return str(text) if text is not None else ""
    
    s = str(text).strip()
    s = re.sub(r"^[fF]?['\"]+", "", s)
    s = re.sub(r"['\"]+$", "", s)
    
    if '{' not in s:
        return s
        
    try:
        def replace_match(match):
            content = match.group(1).strip()
            expr = content.split(':')[0].strip()
            fmt = content.split(':')[1].strip() if ':' in content else ""
            val = eval(expr, {"__builtins__": None, "math": math}, context)
            if isinstance(val, bool): val = str(val).lower()
            return f"{val:{fmt}}" if fmt else str(val)
        
        return re.sub(r'\{(.*?)\}', replace_match, s)
    except Exception:
        return s
def evaluate_text(text, context):
    return html.escape(evaluate_fstring(text, context))

def convert_to_server_quiz(data, server_url):
    html_content = []

    html_content.append(f"""
    <script>
        const SERVER_URL = '{server_url}';
    </script>
    """)
    
    # --- HEADER & STYLE ---
    html_content.append(f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Quiz {data.get('title', '')}</title>
    <script>window.MathJax = {{ tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']] }} }};</script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; max-width: 850px; margin: auto; padding: 20px; background: #f0f4f8; color: #2d3436; }}
        #global-score-banner {{
            position: sticky; top: 0; background: #0984e3; color: white;
            padding: 15px; text-align: center; font-size: 1.4em; font-weight: bold;
            border-radius: 0 0 15px 15px; margin-bottom: 30px; z-index: 1000;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}
        .question-card {{ background: white; padding: 25px; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-left: 6px solid #0984e3; }}
        .question-text {{ font-size: 1.15em; font-weight: 600; margin-bottom: 20px; }}
        .option {{ display: flex; align-items: flex-start; margin: 10px 0; padding: 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; }}
        .option:hover {{ background: #f8f9fa; border-color: #eee; }}
        .numeric-input {{ padding: 10px; font-size: 1em; border: 2px solid #dfe6e9; border-radius: 6px; width: 160px; margin: 10px 0; }}
        .explanation-box {{ display: none; margin-top: 10px; padding: 15px; border-radius: 8px; background: #e0fbfa; border-left: 4px solid #00cec9; }}
        .btn-group {{ margin-top: 20px; display: flex; gap: 10px; border-top: 1px solid #eee; padding-top: 15px; }}
        .btn {{ padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; transition: 0.2s; }}
        .btn-validate {{ background: #2ecc71; color: white; }}
        .btn-correct {{ background: #00cec9; color: white; }}
        .btn-reset {{ background: #dfe6e9; color: #636e72; }}
        .disabled {{ opacity: 0.4; pointer-events: none; filter: grayscale(1); }}
        .match {{ background: #eafff0 !important; border-color: #2ecc71 !important; }}
        .mismatch {{ background: #fff0f0 !important; border-color: #e74c3c !important; }}
        .attempts-hint {{ font-size: 0.85em; color: #7f8c8d; margin-top: 5px; }}
    </style>
</head>
<body>
    <div id="global-score-banner">
        {data.get('title','')} 
    </div>    
<div id="student-login-container" style="background: white; padding: 20px; margin-bottom: 30px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-top: 6px solid #6c5ce7;">
    <h3 style="margin-top:0;">Identification</h3>
    <div style="display: flex; gap: 15px; align-items: flex-end; flex-wrap: wrap;">
        <div style="flex: 1; min-width: 200px;">
            <label style="display:block; font-weight:bold; margin-bottom:5px;">NOM (MAJUSCULES)</label>
            <input type="text" id="input_lastname" placeholder="Ex: DUPONT" style="width:100%; padding:10px; border:2px solid #dfe6e9; border-radius:6px; text-transform: uppercase;">
        </div>
        <div style="flex: 1; min-width: 200px;">
            <label style="display:block; font-weight:bold; margin-bottom:5px;">Prénom</label>
            <input type="text" id="input_firstname" placeholder="Ex: Jean" style="width:100%; padding:10px; border:2px solid #dfe6e9; border-radius:6px;">
        </div>
        <button class="btn btn-validate" style="background:#6c5ce7; height:42px;" onclick="confirmStudent()">Valider l'identité</button>
    </div>
    <div id="student-display" style="margin-top:15px; font-weight:bold; color:#6c5ce7; display:none;">
        Session de : <span id="student-fullname-label"></span>
    </div>
</div>
""")
    


    for q_id, q_content in data.items():
        if q_id == "title" or not isinstance(q_content, dict): continue
        
        # 1. GENERATION CONTEXTE (POUR TEMPLATES)
        context = {}
        q_type = str(q_content.get('type', 'qcm')).lower()
        if "template" in q_type:
            full_text = str(q_content.get('question', ''))
            found_vars = re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', full_text)
            for var in set(found_vars):
                context[var] = round(random.gauss(10, 2), 2) # Exemple Gaussienne

        # 2. DEBUT CARTE
        html_content.append(f"<div class='question-card' id='card_{q_id}' data-type='{q_type}' data-attempts='0'>")
        
        q_text = evaluate_text(q_content.get('question', ''), context)
        html_content.append(f"<div class='question-text'>{q_text}</div>")
        
        props = q_content.get('propositions', [])
        random.shuffle(props)

        # 3. CONTENU QUESTION
        if "numeric" in q_type:
            for i, p in enumerate(props):
                v_exp = evaluate_text(p.get('expected', ''), context)
                v_prop = evaluate_text(p.get('proposition', ''), context)
                v_rep = evaluate_text(p.get('reponse', ''), context)
                v_lab = evaluate_text(p.get('label', ''), context)
                html_content.append(f"""
                <div class='numeric-unit' data-label='{v_lab}'>
                    <label>{v_prop}</label><br>
                    <input type='number' step='any' class='numeric-input' id='input_{q_id}_{i}' 
                           data-expected='{v_exp}' data-tol-abs='{p.get('tolerance_abs', 0)}' data-tol-rel='{p.get('tolerance', 0.01)}'>
                    <div class='explanation-box' id='expl_{q_id}_{i}'><b>Réponse :</b> {v_exp}<br>{v_rep}</div>
                </div>""")


        else:
            html_content.append("<div class='options-container'>")
            for i, p in enumerate(props):
                v_prop = evaluate_text(p.get('proposition', ''), context)
                v_rep = evaluate_text(p.get('reponse', ''), context)
                v_lab = evaluate_text(p.get('label', ''), context)
                is_exp = "true" if p.get('expected') is True else "false"
                html_content.append(f"""
                <div class='option' id='opt_{q_id}_{i}' data-expected='{is_exp}' data-label='{v_lab}' onclick='toggleOption(this)'>
                    <input type='checkbox' style='margin-right:12px' onclick='event.stopPropagation()'>
                    <div>
                        <span>{v_prop}</span>
                        <div class='explanation-box' id='expl_{q_id}_{i}'>{v_rep}</div>
                    </div>
                </div>""")
            html_content.append("</div>")

        # 4. ACTIONS
        '''html_content.append(f"""
            <div id='feedback_{q_id}' style='margin-top:15px; font-weight:bold; color:#2c3e50;'></div>
            <div class='attempts-hint' id='hint_{q_id}'>Tentatives : 0 / {NB_ESSAIS_MAX}</div>
            <div class='btn-group' id='btns_{q_id}'>
                <button class='btn btn-validate' id='val_{q_id}' onclick='validate("{q_id}")'>Valider</button>
            </div>
        </div>""")'''

        '''html_content.append(f"""
        <div class='btn-group' id='btns_{q_id}' style='display: flex; align-items: center; gap: 20px; margin-top: 20px;'>
        <button class='btn btn-validate' id='val_{q_id}' onclick='validate("{q_id}")'>Valider</button>
        <div id='feedback_{q_id}' style='font-weight: bold; color: #2c3e50; min-height: 1.2em;'></div>
        </div>
        <div class='attempts-hint' id='hint_{q_id}' style='font-size: 0.8em; color: #7f8c8d; margin-top: 5px;'></div>
        """)'''

        html_content.append(f"""
            <div class='btn-group' id='btns_{q_id}' style='display: flex; align-items: center; gap: 20px; margin-top: 20px;'>
                <button class='btn btn-validate' id='val_{q_id}' onclick='validate("{q_id}")'>Valider</button>
                <div id='feedback_{q_id}' style='font-weight: bold; color: #2c3e50; min-height: 1.2em;'></div>
            </div>
        </div>""") # On ferme ici la 'question-card'

    # --- JAVASCRIPT ---
    html_content.append(f"""
    <script>

    let STUDENT_NAME = "Inconnu";
                        
    // Fonction utilitaire pour mettre à jour le message
    function setFeedback(q_id, message, color = "#2c3e50") {{
        const fb = document.getElementById('feedback_' + q_id);
        if (fb) {{
            fb.innerHTML = message;
            fb.style.color = color;
        }}
    }}

    // Gestion du toggle pour les QCM
    function toggleOption(el) {{
        const q_id = el.closest('.question-card').id.split('_')[1];
        
        // On affiche le message immédiatement
        setFeedback(q_id, "<i>Saisie modifiée...</i>", "#7f8c8d");

        const cb = el.querySelector('input');
        cb.checked = !cb.checked;
        
        // On déclenche manuellement l'événement 'change' si besoin
        cb.dispatchEvent(new Event('change'));
    }}

    // Initialisation des écouteurs pour les champs numériques
    document.addEventListener("DOMContentLoaded", () => {{
        document.querySelectorAll('.numeric-input').forEach(input => {{
            input.addEventListener('input', (e) => {{
                const q_id = e.target.closest('.question-card').id.split('_')[1];
                setFeedback(q_id, "<i>Saisie en cours...</i>", "#7f8c8d");
            }});
        }});
    }});



    // 2. Fonction de validation (clic sur le bouton)
    async function validate(q_id) {{
        if (STUDENT_NAME === "Inconnu") {{
            alert("Veuillez d'abord valider votre identité en haut de la page.");
            document.getElementById('student-login-container').scrollIntoView({{ behavior: 'smooth' }});
            return;
        }}

        const card = document.getElementById('card_' + q_id);
        let answers = {{}};

        // Collecte Numériques
        card.querySelectorAll('.numeric-input').forEach(input => {{
            const label = input.getAttribute('data-label') || input.id;
            answers[label] = input.value;
        }});

        // Collecte QCM
        card.querySelectorAll('.option').forEach(opt => {{
            const label = opt.getAttribute('data-label') || opt.id;
            answers[label] = opt.querySelector('input').checked;
        }});

        const now = new Date();
        const timestamp = now.toLocaleDateString('fr-FR') + ' ' + now.toLocaleTimeString('fr-FR');

        const payload = {{
            "notebook_id": "",
            "student": STUDENT_NAME,
            "quiz_title": q_id,
            "timestamp": timestamp,
            "event_type": "validate",
            "parameters": {{}},
            "answers": answers,
            "score": "0"
        }};

         try {{
            setFeedback(q_id, "<i>Transmission...</i>", "#0984e3");
            
            const response = await fetch(SERVER_URL, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'text/plain' }},
                body: JSON.stringify(payload)
            }});

            if (response.ok) {{
                setFeedback(q_id, "✅ Enregistré à " + new Date().toLocaleTimeString('fr-FR'), "#27ae60");
            }} else {{
                throw new Error("Erreur " + response.status);
            }}
        }} catch (error) {{
            setFeedback(q_id, "❌ Échec d'envoi", "#e74c3c");
        }}
    }}

    function toggleOption(el) {{
        const q_id = el.closest('.question-card').id.split('_')[1];
        if (document.getElementById('val_' + q_id).disabled) return;
        
        document.getElementById('feedback_' + q_id).innerHTML = "<i>Saisie modifiée...</i>";
        const cb = el.querySelector('input');
        cb.checked = !cb.checked;
    }}


    function confirmStudent() {{
        const ln = document.getElementById('input_lastname').value.trim().toUpperCase();
        const fn = document.getElementById('input_firstname').value.trim();
        
        if (ln === "" || fn === "") {{
            alert("Merci de saisir votre nom et votre prénom.");
            return;
        }}

        // Formatage : NOM Prénom
        STUDENT_NAME = ln + " " + fn;

        // Feedback visuel
        document.getElementById('student-fullname-label').innerText = STUDENT_NAME;
        document.getElementById('student-display').style.display = 'block';
        
        // On peut optionnellement griser les champs après validation
        document.getElementById('input_lastname').disabled = true;
        document.getElementById('input_firstname').disabled = true;
        
        console.log("Étudiant identifié : " + STUDENT_NAME);
    }}
    </script>
</body>
</html>""")
    return "\n".join(html_content)