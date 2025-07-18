import streamlit as st
import gspread
import pandas as pd
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta
import unicodedata
import bcrypt

# --- LAZY CONNECTION SETUP ---
_connections = {"spreadsheet": None, "model": None}

def normalize_for_search(text: str) -> str:
    if not isinstance(text, str):
        return ""
    nfkd_form = unicodedata.normalize('NFD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

def _ensure_connected():
    if _connections["spreadsheet"] is None:
        try:
            creds_dict = dict(st.secrets["gcp_service_account"])
            gc = gspread.service_account_from_dict(creds_dict)
            spreadsheet = gc.open(st.secrets["gcs"]["sheet_name"])
            
            if "google_ai" not in st.secrets or "api_key" not in st.secrets.google_ai:
                raise ValueError("A chave 'google_ai' ou 'api_key' não foi encontrada em secrets.toml.")
            
            genai.configure(api_key=st.secrets.google_ai.api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            _connections["spreadsheet"] = spreadsheet
            _connections["model"] = model
        except Exception as e:
            st.error(f"Falha na conexão com os serviços: {e}")
            st.stop()

def get_gemini_model():
    _ensure_connected()
    return _connections["model"]

# --- FUNÇÕES DE DADOS ---

def authenticate_or_register_user(email, password):
    try:
        _ensure_connected()
        users_sheet = _connections["spreadsheet"].worksheet("users")

        try:
            cell = users_sheet.find(email)
        except gspread.exceptions.CellNotFound:
            cell = None

        if cell is None:
            if not password:
                return {'status': 'error', 'message': 'Senha é obrigatória para o cadastro.', 'user_id': None}
            
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            new_user_data = [email, user_id, created_at, hashed_password, '']
            users_sheet.append_row(new_user_data)
            return {'status': 'success', 'message': 'Cadastro realizado com sucesso!', 'user_id': user_id}

        user_row = users_sheet.row_values(cell.row)
        user_id = user_row[1]
        stored_password_hash = user_row[3] if len(user_row) > 3 else None

        if not stored_password_hash:
            if not password:
                return {'status': 'error', 'message': 'Por favor, crie uma senha para sua conta.', 'user_id': None}
            
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users_sheet.update_cell(cell.row, 4, hashed_password)
            return {'status': 'success', 'message': 'Senha cadastrada com sucesso! Bem-vindo!', 'user_id': user_id}

        if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8')):
            return {'status': 'success', 'message': 'Login realizado com sucesso!', 'user_id': user_id}
        else:
            return {'status': 'error', 'message': 'Senha incorreta. Tente novamente.', 'user_id': None}
    except Exception as e:
        st.error(f"Ocorreu um erro durante a autenticação: {e}")
        return {'status': 'error', 'message': 'Erro de sistema. Tente novamente mais tarde.', 'user_id': None}

def get_next_question(user_id, status_filters=['nao_respondidas'], specialty=None, provas=None, keywords=None):
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        
        if questions_df.empty:
            return None

        list_of_pools = []
        user_answers_df = pd.DataFrame()
        if not answers_df.empty:
            answers_df['user_id'] = answers_df['user_id'].astype(str)
            user_answers_df = answers_df[answers_df['user_id'] == user_id].copy()

        if 'nao_respondidas' in status_filters:
            if not user_answers_df.empty:
                answered_ids = user_answers_df['question_id'].unique().tolist()
                pool = questions_df[~questions_df['question_id'].isin(answered_ids)]
            else:
                pool = questions_df.copy()
            list_of_pools.append(pool)

        if not user_answers_df.empty and ('corretas' in status_filters or 'incorretas' in status_filters):
            user_answers_df['is_correct'] = user_answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
            if 'corretas' in status_filters:
                correct_ids = user_answers_df[user_answers_df['is_correct'] == True]['question_id'].unique().tolist()
                list_of_pools.append(questions_df[questions_df['question_id'].isin(correct_ids)])
            if 'incorretas' in status_filters:
                incorrect_ids = user_answers_df[user_answers_df['is_correct'] == False]['question_id'].unique().tolist()
                list_of_pools.append(questions_df[questions_df['question_id'].isin(incorrect_ids)])

        if not list_of_pools: return None
        initial_pool = pd.concat(list_of_pools).drop_duplicates(subset=['question_id']).reset_index(drop=True)
        if initial_pool.empty: return None

        final_pool = initial_pool.copy()
        if specialty and specialty != "Todas":
            final_pool = final_pool[final_pool['areas_principais'].str.contains(specialty, na=False, case=False)]
        if provas:
            final_pool = final_pool[final_pool['prova'].isin(provas)]
        if keywords:
            searchable_text = final_pool.apply(lambda row: normalize_for_search(' '.join(row.values.astype(str))), axis=1)
            normalized_keywords = [normalize_for_search(kw) for kw in keywords]
            keyword_regex = '|'.join(normalized_keywords)
            final_pool = final_pool[searchable_text.str.contains(keyword_regex, na=False)]

        if final_pool.empty: return None
        return final_pool.sample(n=1).to_dict('records')[0]
    except (KeyError, Exception) as e:
        st.warning(f"Não foi possível buscar a próxima questão devido a um erro: {e}")
        return None

def save_answer(user_id, question_id, user_answer, is_correct):
    try:
        _ensure_connected()
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        all_answers = pd.DataFrame(answers_sheet.get_all_records())

        existing_answer = all_answers[
            (all_answers['user_id'] == str(user_id)) & 
            (all_answers['question_id'] == str(question_id))
        ]

        if existing_answer.empty:
            answer_id = str(uuid.uuid4())
            timestamp = datetime.now().isoformat()
            new_answer_data = [answer_id, str(user_id), str(question_id), user_answer, 'TRUE' if is_correct else 'FALSE', timestamp]
            answers_sheet.append_row(new_answer_data)
        else:
            old_is_correct = str(existing_answer['is_correct'].iloc[0]).upper() == 'TRUE'
            if old_is_correct and not is_correct: return

            cell = answers_sheet.find(existing_answer['answer_id'].iloc[0])
            row_index = cell.row
            updated_row = [
                existing_answer['answer_id'].iloc[0], str(user_id), str(question_id),
                user_answer, 'TRUE' if is_correct else 'FALSE', datetime.now().isoformat()
            ]
            answers_sheet.update(f'A{row_index}:F{row_index}', [updated_row])
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Não foi possível salvar sua resposta: {e}")

@st.cache_data(ttl=3600)
def get_all_specialties():
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        if 'areas_principais' not in questions_df.columns or questions_df.empty:
            return []
        specialties = questions_df['areas_principais'].dropna().str.split(',').explode()
        return sorted(list(specialties.str.strip().unique()))
    except Exception as e:
        st.warning(f"Não foi possível carregar as especialidades: {e}")
        return []

@st.cache_data(ttl=600)
def get_performance_data(user_id):
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())

        if answers_df.empty or questions_df.empty: return None
        
        answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        all_answers_for_ranking = answers_df.copy()

        user_answers_df = answers_df[answers_df['user_id'].astype(str) == str(user_id)].copy()
        if user_answers_df.empty: return None

        user_answers_df['answered_at'] = pd.to_datetime(user_answers_df['answered_at'])
        merged_df = pd.merge(user_answers_df, questions_df, on='question_id', how='left')
        
        # Validação de colunas para evitar KeyError
        if 'areas_principais' not in merged_df.columns: merged_df['areas_principais'] = ''
        if 'subtopicos' not in merged_df.columns: merged_df['subtopicos'] = ''

        merged_df['areas_principais'] = merged_df['areas_principais'].fillna('').str.split(',')
        merged_df['subtopicos'] = merged_df['subtopicos'].fillna('').str.split(',')
        
        areas_df = merged_df.explode('areas_principais')
        areas_df['areas_principais'] = areas_df['areas_principais'].str.strip()
        subtopicos_df = merged_df.explode('subtopicos')
        subtopicos_df['subtopicos'] = subtopicos_df['subtopicos'].str.strip()
        
        return {
            "all_answers": merged_df, 
            "areas_exploded": areas_df, 
            "subtopicos_exploded": subtopicos_df,
            "all_answers_for_ranking": all_answers_for_ranking
        }
    except (KeyError, Exception) as e:
        st.warning(f"Não foi possível processar seus dados de performance: {e}")
        return None

def calculate_metrics(df):
    if df is None or df.empty: return {"answered": 0, "correct": 0, "accuracy": 0.0}
    answered = len(df)
    correct = df['is_correct'].sum()
    accuracy = (correct / answered * 100) if answered > 0 else 0.0
    return {"answered": answered, "correct": correct, "accuracy": accuracy}

@st.cache_data(ttl=3600)
def get_all_provas():
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        if 'prova' not in questions_df.columns or questions_df.empty:
            return []
        return sorted(list(questions_df['prova'].dropna().unique()))
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de provas: {e}")
        return []

@st.cache_data(ttl=3600)
def get_global_platform_stats():
    """
    Calcula as estatísticas globais da plataforma para exibir na Home.
    """
    default_stats = {'total_students': 0, 'active_this_week': 0, 'answered_last_7_days': 0, 'accuracy_last_7_days': 0.0}
    try:
        _ensure_connected()
        users_sheet = _connections["spreadsheet"].worksheet("users")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")

        users_df = pd.DataFrame(users_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())

        total_students = len(users_df) if not users_df.empty else 0
        if answers_df.empty:
            default_stats['total_students'] = total_students
            return default_stats

        answers_df['answered_at'] = pd.to_datetime(answers_df['answered_at'])
        answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        now = datetime.now(answers_df['answered_at'].dt.tz)

        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        this_week_answers = answers_df[answers_df['answered_at'] >= start_of_week]
        active_this_week = this_week_answers['user_id'].nunique()

        seven_days_ago = now - timedelta(days=7)
        last_7_days_answers = answers_df[answers_df['answered_at'] >= seven_days_ago]
        answered_last_7_days = len(last_7_days_answers)
        accuracy_last_7_days = (last_7_days_answers['is_correct'].mean() * 100) if not last_7_days_answers.empty else 0.0

        return {
            'total_students': total_students,
            'active_this_week': active_this_week,
            'answered_last_7_days': answered_last_7_days,
            'accuracy_last_7_days': accuracy_last_7_days
        }
    except Exception as e:
        print(f"Erro ao calcular estatísticas globais: {e}")
        return default_stats

# As demais funções (get_time_window_metrics, get_temporal_performance, etc.) podem ser mantidas como estão
# pois dependem dos DataFrames já tratados e retornados por get_performance_data.

def get_simulado_questions(user_id, count=20, status_filters=['nao_respondidas'], specialty=None, provas=None, keywords=None):
    """
    Busca um lote de questões para um simulado, com base nos filtros.
    """
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        
        if questions_df.empty:
            return []

        # A lógica de filtragem é a mesma de get_next_question
        list_of_pools = []
        user_answers_df = pd.DataFrame()
        if not answers_df.empty:
            answers_df['user_id'] = answers_df['user_id'].astype(str)
            user_answers_df = answers_df[answers_df['user_id'] == user_id].copy()

        if 'nao_respondidas' in status_filters:
            if not user_answers_df.empty:
                answered_ids = user_answers_df['question_id'].unique().tolist()
                pool = questions_df[~questions_df['question_id'].isin(answered_ids)]
            else:
                pool = questions_df.copy()
            list_of_pools.append(pool)

        if not user_answers_df.empty and ('corretas' in status_filters or 'incorretas' in status_filters):
            user_answers_df['is_correct'] = user_answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
            if 'corretas' in status_filters:
                correct_ids = user_answers_df[user_answers_df['is_correct'] == True]['question_id'].unique().tolist()
                list_of_pools.append(questions_df[questions_df['question_id'].isin(correct_ids)])
            if 'incorretas' in status_filters:
                incorrect_ids = user_answers_df[user_answers_df['is_correct'] == False]['question_id'].unique().tolist()
                list_of_pools.append(questions_df[questions_df['question_id'].isin(incorrect_ids)])

        if not list_of_pools: return []
        initial_pool = pd.concat(list_of_pools).drop_duplicates(subset=['question_id']).reset_index(drop=True)
        if initial_pool.empty: return []

        final_pool = initial_pool.copy()
        if specialty and specialty != "Todas":
            final_pool = final_pool[final_pool['areas_principais'].str.contains(specialty, na=False, case=False)]
        if provas:
            final_pool = final_pool[final_pool['prova'].isin(provas)]
        if keywords:
            searchable_text = final_pool.apply(lambda row: normalize_for_search(' '.join(row.values.astype(str))), axis=1)
            normalized_keywords = [normalize_for_search(kw) for kw in keywords]
            keyword_regex = '|'.join(normalized_keywords)
            final_pool = final_pool[searchable_text.str.contains(keyword_regex, na=False)]

        if final_pool.empty: return []
        
        # A principal diferença: buscar 'count' questões, não apenas 1.
        # Se houver menos questões disponíveis que o solicitado, pega todas.
        num_available = len(final_pool)
        sample_size = min(count, num_available)
        
        # Retorna uma LISTA de dicionários
        return final_pool.sample(n=sample_size, replace=False).to_dict('records')

    except (KeyError, Exception) as e:
        st.warning(f"Não foi possível buscar as questões do simulado devido a um erro: {e}")
        return []