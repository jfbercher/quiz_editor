import random
import re

def evaluate_fstring_old(text, context):
    """Évalue les expressions f-string si un contexte est fourni."""
    if not context or text is None: return str(text) if text is not None else ""
    
    s = str(text).strip()
    s = re.sub(r"^[fF]?['\"]+", "", s)
    s = re.sub(r"['\"]+$", "", s)
    
    if '{' not in s: return s

    try:
        def replace_match(match):
            content = match.group(1).strip()
            expr = content.split(':')[0].strip()
            fmt = content.split(':')[1].strip() if ':' in content else ""
            val = eval(expr, {"__builtins__": None}, context)
            return f"{val:{fmt}}" if fmt else str(val)
        return re.sub(r'\{(.*?)\}', replace_match, s)
    except:
        return s

def evaluate_fstring(template, **context):
    return eval("f" + repr(template), {"__builtins__": {}}, context)

def convert_to_amc_latex(data, use_negative_points=True):
    latex_output = []
    
    
    for q_id, q_content in data.items():
        if q_id == "title" or not isinstance(q_content, dict): continue
        
        q_type = str(q_content.get('type', '')).lower()
        # RÈGLE : Uniquement les types -template passent en mode dynamique
        is_template = q_type.endswith('-template')
        
        context = {}
        if is_template:
            # On cherche les variables à calculer
            raw_text = str(q_content.get('question', '')) + str(q_content.get('propositions', ''))
            found_vars = set(re.findall(r'\{([a-zA-Z_][a-zA-Z0-9_]*)[\}:]', raw_text))
            
            if found_vars:
                latex_output.append(f"\n% --- Valeurs aléatoires pour {q_id} ---")
                params_config = q_content.get('parameters', {})
                for var in found_vars:
                    if isinstance(params_config, dict) and var in params_config:
                        p = params_config[var]
                        val = round(random.uniform(p.get('min', 0), p.get('max', 10)) / p.get('step', 1)) * p.get('step', 1)
                    else:
                        val = round(random.uniform(1, 10), 1) # Par défaut si non défini
                    context[var] = val
                    latex_output.append(f"% {var} = {val}")
        else:
            latex_output.append(f"\n% --- {q_id} ---")
        

        # Évaluation (ne fera rien si context est vide, donc respecte le texte statique)
        q_text = evaluate_fstring(q_content.get('question', ''), context)
        q_label = q_content.get('label', f'q:{q_id}')
        q_category = q_content.get('category', 'nocategory')
        
        # Détection question / questionmult
        props = q_content.get('propositions', [])
        is_mult = "multiple" in q_type or len([p for p in props if p.get('expected') is True]) > 1
        amc_tag = "questionmult" if is_mult else "question"

                # Construction du bloc question
        latex_output.append(f"\\element{{{q_category}}}{{")
        latex_output.append(f"  \\begin{{{amc_tag}}}{{{q_label}}}")
        latex_output.append(f"  {q_text}")

        if "numeric" in q_type:
            for p in props:
                val_eval = evaluate_fstring(p.get('expected', '0'), context)
                latex_output.append(f"  \\AMCNumericChoices{{{val_eval}}}{{digits=3,decimals=2,sign=true}}")
        else:
            latex_output.append("    \\begin{choices}")
            for p in props:
                is_correct = p.get('expected') is True
                cmd = "\\correctchoice" if is_correct else "\\wrongchoice"
                p_text = evaluate_fstring(p.get('label', p.get('proposition', '')), context)
                
                # Scoring logique
                bonus = 1 if is_correct else 0
                malus = -1 if (use_negative_points and not is_correct) else 0
                latex_output.append(f"      {cmd}{{{p_text}}} \\scoring{{b={bonus},m={malus}}}")
            latex_output.append("    \\end{choices}")

        latex_output.append(f"\\end{{{amc_tag}}}")
        latex_output.append(f"}}")
            
    return "\n".join(latex_output)