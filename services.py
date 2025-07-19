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
    """
    Autentica um usuário ou registra um novo.
    Converte o e-mail para minúsculas para garantir consistência.
    """
    try:
        # Padroniza o e-mail
        email = email.strip().lower()
        
        _ensure_connected()
        users_sheet = _connections["spreadsheet"].worksheet("users")

        try:
            cell = users_sheet.find(email)
        except gspread.exceptions.CellNotFound:
            cell = None

        # Cenário 1: Novo Usuário (email não encontrado)
        if cell is None:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            new_user_data = [email, user_id, created_at, hashed_password, '']
            users_sheet.append_row(new_user_data)
            return {'status': 'success', 'message': 'Cadastro realizado com sucesso!', 'user_id': user_id}

        # Cenário 2: Usuário Existente (email encontrado)
        user_row = users_sheet.row_values(cell.row)
        user_id = user_row[1]
        stored_password_hash = user_row[3] if len(user_row) > 3 else None

        # Cenário 2a: Usuário existe, mas não tem senha
        if not stored_password_hash:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users_sheet.update_cell(cell.row, 4, hashed_password)
            return {'status': 'success', 'message': 'Senha cadastrada com sucesso! Bem-vindo!', 'user_id': user_id}

        # Cenário 2b: Usuário existe e tem senha (tentativa de login)
        try:
            if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8')):
                return {'status': 'success', 'message': 'Login realizado com sucesso!', 'user_id': user_id}
            else:
                return {'status': 'error', 'message': 'Senha incorreta. Tente novamente.', 'user_id': None}
        
        except ValueError:
            st.info("Detectamos um formato de senha antigo. Atualizando sua conta para o novo formato seguro...")
            new_hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users_sheet.update_cell(cell.row, 4, new_hashed_password)
            return {'status': 'success', 'message': 'Sua conta foi atualizada com sucesso! Login realizado.', 'user_id': user_id}

    except Exception as e:
        st.error(f"Ocorreu um erro durante a autenticação: {e}")
        return {'status': 'error', 'message': 'Erro de sistema. Tente novamente mais tarde.', 'user_id': None}

def save_answer(user_id, question_id, user_answer, is_correct):
    """
    Salva uma resposta nova ou atualiza uma existente com a lógica restritiva.
    """
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
            
            if not old_is_correct and is_correct:
                try:
                    cell = answers_sheet.find(existing_answer['answer_id'].iloc[0])
                    row_index = cell.row
                    updated_row = [
                        existing_answer['answer_id'].iloc[0], str(user_id), str(question_id),
                        user_answer, 'TRUE', datetime.now().isoformat()
                    ]
                    answers_sheet.update(f'A{row_index}:F{row_index}', [updated_row])
                except Exception as e:
                    print(f"ERRO: Não foi possível encontrar ou atualizar a linha da resposta. Erro: {e}")
            else:
                return

        st.cache_data.clear()
        
    except Exception as e:
        st.error(f"Não foi possível salvar sua resposta: {e}")

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
        
        if questions_df.empty: return []

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
        
        num_available = len(final_pool)
        sample_size = min(count, num_available)
        
        return final_pool.sample(n=sample_size, replace=False).to_dict('records')

    except (KeyError, Exception) as e:
        st.warning(f"Não foi possível buscar as questões do simulado devido a um erro: {e}")
        return []

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

def get_time_window_metrics(all_answers_df, days=None):
    if all_answers_df is None: return calculate_metrics(None)
    if days is None: return calculate_metrics(all_answers_df)
    
    if all_answers_df['answered_at'].dt.tz:
        cutoff_date = datetime.now(all_answers_df['answered_at'].dt.tz) - timedelta(days=days)
    else:
        cutoff_date = datetime.now() - timedelta(days=days)

    window_df = all_answers_df[all_answers_df['answered_at'] >= cutoff_date]
    return calculate_metrics(window_df)

def get_temporal_performance(all_answers_df, period='W'):
    if all_answers_df is None or all_answers_df.empty: return pd.DataFrame()
    df = all_answers_df.copy()
    df['periodo'] = df['answered_at'].dt.to_period(period).dt.start_time
    summary = df.groupby('periodo').agg(
        questoes_respondidas=('question_id', 'count'), 
        acertos=('is_correct', 'sum')
    ).reset_index()
    summary['taxa_de_acerto'] = (summary['acertos'] / summary['questoes_respondidas'] * 100).fillna(0)
    return summary

def get_areas_performance(areas_exploded_df):
    if areas_exploded_df is None or areas_exploded_df.empty: return pd.DataFrame()
    areas_summary = areas_exploded_df.groupby('areas_principais').agg(
        total_respondidas=('question_id', 'count'), 
        total_acertos=('is_correct', 'sum')
    ).reset_index()
    areas_summary['taxa_de_acerto'] = (areas_summary['total_acertos'] / areas_summary['total_respondidas'] * 100).fillna(0)
    return areas_summary

def get_subtopics_for_review(subtopicos_exploded_df, days=7):
    if subtopicos_exploded_df is None or subtopicos_exploded_df.empty: return []
    if subtopicos_exploded_df['answered_at'].dt.tz:
        cutoff_date = datetime.now(subtopicos_exploded_df['answered_at'].dt.tz) - timedelta(days=days)
    else:
         cutoff_date = datetime.now() - timedelta(days=days)
    recent_errors_df = subtopicos_exploded_df[
        (subtopicos_exploded_df['answered_at'] >= cutoff_date) & 
        (subtopicos_exploded_df['is_correct'] == False)
    ]
    if recent_errors_df.empty: return []
    return recent_errors_df['subtopicos'].value_counts().nlargest(5).index.tolist()

def get_ranking_data(all_answers_df, period_code, current_user_id):
    if all_answers_df.empty: return None
    df = all_answers_df.copy()
    df['answered_at'] = pd.to_datetime(df['answered_at'])
    now = datetime.now(df['answered_at'].dt.tz)
    if period_code == 'D':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_code == 'W':
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        return None
    recent_answers = df[df['answered_at'] >= start_date]
    if recent_answers.empty: return None
    performance = recent_answers.groupby('user_id').agg(
        total_corretas=('is_correct', 'sum'),
        total_respondidas=('is_correct', 'count')
    ).reset_index()
    performance['taxa_de_acerto'] = (performance['total_corretas'] / performance['total_respondidas']) * 100
    ranked_users = performance.sort_values(by=['taxa_de_acerto', 'total_respondidas'], ascending=[False, False]).reset_index(drop=True)
    ranked_users['rank'] = ranked_users.index + 1
    user_rank_info = ranked_users[ranked_users['user_id'].astype(str) == str(current_user_id)]
    if user_rank_info.empty:
        return {'rank': None, 'total_users': len(ranked_users), 'percentile': None}
    user_rank = int(user_rank_info['rank'].iloc[0])
    total_users = len(ranked_users)
    percentile = (user_rank / total_users) * 100
    return {'rank': user_rank, 'total_users': total_users, 'percentile': percentile}

@st.cache_data(ttl=600)
def get_user_answered_questions_details(user_id):
    try:
        _ensure_connected()
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        if answers_df.empty or questions_df.empty: return pd.DataFrame()
        user_answers = answers_df[answers_df['user_id'].astype(str) == str(user_id)].copy()
        if user_answers.empty: return pd.DataFrame()
        user_answers['answered_at'] = pd.to_datetime(user_answers['answered_at'])
        user_answers['is_correct'] = user_answers['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        merged_df = pd.merge(user_answers, questions_df, on='question_id', how='left')
        return merged_df.sort_values(by='answered_at', ascending=False)
    except Exception as e:
        st.error(f"Erro ao buscar histórico de revisão: {e}")
        return pd.DataFrame()

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