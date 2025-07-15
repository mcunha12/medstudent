# ==============================================================================
# ARQUIVO 1: services.py (Adicionando uma nova função no final)
# ==============================================================================
import streamlit as st
import gspread
import pandas as pd
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta

# --- LAZY CONNECTION SETUP ---
_connections = {"spreadsheet": None, "model": None}

def _ensure_connected():
    if _connections["spreadsheet"] is None:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            spreadsheet = gc.open(st.secrets["gcs"]["sheet_name"])
            
            # Verifica se a API Key do Gemini existe nos segredos
            if "google_ai" not in st.secrets or "api_key" not in st.secrets.google_ai:
                raise ValueError("A chave 'google_ai' ou 'api_key' não foi encontrada em secrets.toml.")
            
            genai.configure(api_key=st.secrets.google_ai.api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            _connections["spreadsheet"] = spreadsheet
            _connections["model"] = model
        except Exception as e:
            st.error(f"Falha na conexão com os serviços: {e}")
            st.stop()

# --- FUNÇÃO NOVA ---
def get_gemini_model():
    """
    Garante que a conexão com a API do Gemini está ativa e retorna a instância do modelo.
    """
    _ensure_connected()
    return _connections["model"]

# --- FUNÇÕES DE DADOS (O restante do arquivo continua igual) ---
def get_or_create_user(email):
    _ensure_connected()
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
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    answers_df = pd.DataFrame(answers_sheet.get_all_records())
    if questions_df.empty: return None
    if not answers_df.empty:
        answers_df['user_id'] = answers_df['user_id'].astype(str)
        answered_questions_ids = answers_df[answers_df['user_id'] == user_id]['question_id'].tolist()
        unanswered_questions_df = questions_df[~questions_df['question_id'].isin(answered_questions_ids)]
    else:
        unanswered_questions_df = questions_df
    return unanswered_questions_df.sample(n=1).to_dict('records')[0] if not unanswered_questions_df.empty else None

def save_answer(user_id, question_id, user_answer, is_correct):
    _ensure_connected()
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    answer_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    new_answer_data = [answer_id, str(user_id), str(question_id), user_answer, is_correct, timestamp]
    answers_sheet.append_row(new_answer_data)
    st.cache_data.clear()

def generate_question_with_gemini():
    model = get_gemini_model() # Usa a nova função
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    prompt = """
    Crie uma nova questão de múltipla escolha para a prova de residência médica (ENAMED) no Brasil...
    """
    # ... (resto da função inalterado)
    pass

@st.cache_data(ttl=600)
def get_performance_data(user_id):
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    answers_df = pd.DataFrame(answers_sheet.get_all_records())
    if answers_df.empty or questions_df.empty: return None
    user_answers_df = answers_df[answers_df['user_id'].astype(str) == user_id].copy()
    if user_answers_df.empty: return None
    user_answers_df['answered_at'] = pd.to_datetime(user_answers_df['answered_at'])
    user_answers_df['is_correct'] = user_answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
    merged_df = pd.merge(user_answers_df, questions_df, on='question_id', how='left')
    merged_df['areas_principais'] = merged_df['areas_principais'].fillna('').str.split(',')
    merged_df['subtopicos'] = merged_df['subtopicos'].fillna('').str.split(',')
    areas_df = merged_df.explode('areas_principais')
    areas_df['areas_principais'] = areas_df['areas_principais'].str.strip()
    subtopicos_df = merged_df.explode('subtopicos')
    subtopicos_df['subtopicos'] = subtopicos_df['subtopicos'].str.strip()
    return {"all_answers": merged_df, "areas_exploded": areas_df, "subtopicos_exploded": subtopicos_df}

def calculate_metrics(df):
    if df is None or df.empty: return {"answered": 0, "correct": 0, "accuracy": 0.0}
    answered = len(df)
    correct = df['is_correct'].sum()
    accuracy = (correct / answered * 100) if answered > 0 else 0.0
    return {"answered": answered, "correct": correct, "accuracy": accuracy}

def get_time_window_metrics(all_answers_df, days=None):
    if all_answers_df is None: return calculate_metrics(None)
    if days is None: return calculate_metrics(all_answers_df)
    cutoff_date = datetime.now(all_answers_df['answered_at'].dt.tz) - timedelta(days=days)
    window_df = all_answers_df[all_answers_df['answered_at'] >= cutoff_date]
    return calculate_metrics(window_df)

def get_temporal_performance(all_answers_df, period='W'):
    if all_answers_df is None or all_answers_df.empty: return pd.DataFrame()
    df = all_answers_df.copy()
    df['periodo'] = df['answered_at'].dt.to_period(period).dt.start_time
    summary = df.groupby('periodo').agg(questoes_respondidas=('question_id', 'count'), acertos=('is_correct', 'sum')).reset_index()
    summary['taxa_de_acerto'] = (summary['acertos'] / summary['questoes_respondidas'] * 100).fillna(0)
    return summary

def get_areas_performance(areas_exploded_df):
    if areas_exploded_df is None or areas_exploded_df.empty: return pd.DataFrame()
    areas_summary = areas_exploded_df.groupby('areas_principais').agg(total_respondidas=('question_id', 'count'), total_acertos=('is_correct', 'sum')).reset_index()
    areas_summary['taxa_de_acerto'] = (areas_summary['total_acertos'] / areas_summary['total_respondidas'] * 100).fillna(0)
    return areas_summary

def get_subtopics_for_review(subtopicos_exploded_df, days=7):
    if subtopicos_exploded_df is None or subtopicos_exploded_df.empty: return []
    cutoff_date = datetime.now(subtopicos_exploded_df['answered_at'].dt.tz) - timedelta(days=days)
    recent_errors_df = subtopicos_exploded_df[(subtopicos_exploded_df['answered_at'] >= cutoff_date) & (subtopicos_exploded_df['is_correct'] == False)]
    if recent_errors_df.empty: return []
    return recent_errors_df['subtopicos'].value_counts().nlargest(5).index.tolist()