import streamlit as st
import gspread
import pandas as pd
import google.generativeai as genai
import json
import uuid
from datetime import datetime

# --- LAZY CONNECTION SETUP ---
# Usamos um dicionário para guardar o estado da conexão.
# Ele começa vazio e só é preenchido na primeira vez que uma função o utiliza.
_connections = {"spreadsheet": None, "model": None}

def _ensure_connected():
    """Função interna para conectar apenas se ainda não estiver conectado."""
    if _connections["spreadsheet"] is None:
        try:
            # Este bloco de código agora só roda quando uma função é chamada,
            # o que acontece DEPOIS do st.set_page_config() ter sido executado.
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            spreadsheet = gc.open(st.secrets["gcs"]["sheet_name"])
            
            genai.configure(api_key=st.secrets["google_ai"]["api_key"])
            model = genai.GenerativeModel('gemini-1.5-flash')

            _connections["spreadsheet"] = spreadsheet
            _connections["model"] = model
        except Exception as e:
            st.error(f"Falha na conexão com os serviços: {e}")
            st.stop()

# --- FUNÇÕES DE LÓGICA (com a chamada para garantir a conexão) ---

def get_or_create_user(email):
    _ensure_connected() # Garante que estamos conectados
    users_sheet = _connections["spreadsheet"].worksheet("users")
    users_df = pd.DataFrame(users_sheet.get_all_records())
    if not users_df.empty and email in users_df['email'].values:
        user_id = users_df[users_df['email'] == email]['user_id'].iloc[0]
    else:
        user_id = str(uuid.uuid4())
        new_user_data = [email, user_id, datetime.now().isoformat()]
        users_sheet.append_row(new_user_data)
    return user_id

def get_next_question(user_id):
    _ensure_connected() # Garante que estamos conectados
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    answers_df = pd.DataFrame(answers_sheet.get_all_records())

    if questions_df.empty:
        return None

    if not answers_df.empty:
        answers_df['user_id'] = answers_df['user_id'].astype(str)
        answered_questions_ids = answers_df[answers_df['user_id'] == user_id]['question_id'].tolist()
        unanswered_questions_df = questions_df[~questions_df['question_id'].isin(answered_questions_ids)]
    else:
        unanswered_questions_df = questions_df

    if not unanswered_questions_df.empty:
        return unanswered_questions_df.sample(n=1).to_dict('records')[0]
    else:
        return None

def save_answer(user_id, question_id, user_answer, is_correct):
    _ensure_connected() # Garante que estamos conectados
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    answer_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    new_answer_data = [answer_id, str(user_id), str(question_id), user_answer, is_correct, timestamp]
    answers_sheet.append_row(new_answer_data)

def get_user_stats(user_id):
    _ensure_connected() # Garante que estamos conectados
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    answers_df = pd.DataFrame(answers_sheet.get_all_records())
    if answers_df.empty or user_id not in answers_df['user_id'].astype(str).values:
        return {"total_answered": 0, "total_correct": 0, "accuracy": 0}

    user_answers_df = answers_df[answers_df['user_id'].astype(str) == user_id]
    if user_answers_df.empty:
        return {"total_answered": 0, "total_correct": 0, "accuracy": 0}
        
    total_answered = len(user_answers_df)
    total_correct = user_answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE').sum()
    accuracy = (total_correct / total_answered * 100) if total_answered > 0 else 0
    return {"total_answered": total_answered, "total_correct": total_correct, "accuracy": accuracy}

def generate_question_with_gemini():
    _ensure_connected() # Garante que estamos conectados
    model = _connections["model"]
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    prompt = """
    Crie uma nova questão de múltipla escolha para a prova de residência médica (ENAMED) no Brasil.
    A questão deve ser desafiadora e clinicamente relevante.
    Retorne a resposta EXCLUSIVAMENTE em formato JSON, seguindo esta estrutura:
    {
      "enunciado": "...",
      "alternativas": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
      "comentarios": {"A": "...", "B": "...", "C": "...", "D": "...", "E": "..."},
      "alternativa_correta": "Letra da alternativa correta (ex: 'C')",
      "areas_principais": ["Área 1", "Área 2"],
      "subtopicos": ["Subtópico 1", "Subtópico 2"]
    }
    Não inclua a palavra 'json' ou ``` no início ou no fim da sua resposta.
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        new_question = json.loads(cleaned_response)
        question_id = str(uuid.uuid4())
        new_question_data = [
            question_id, new_question["enunciado"], json.dumps(new_question["alternativas"]),
            json.dumps(new_question["comentarios"]), new_question["alternativa_correta"],
            ", ".join(new_question["areas_principais"]), ", ".join(new_question["subtopicos"])
        ]
        questions_sheet.append_row(new_question_data)
        new_question['question_id'] = question_id
        return new_question
    except Exception as e:
        st.error(f"Falha ao gerar ou processar questão da IA: {e}")
        return None