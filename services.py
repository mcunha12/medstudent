import streamlit as st
import gspread
import pandas as pd
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta
import unicodedata
import bcrypt # Nova importação

# --- LAZY CONNECTION SETUP ---
_connections = {"spreadsheet": None, "model": None}

def normalize_for_search(text: str) -> str:
    """
    Normaliza um texto para busca: remove acentos e converte para minúsculas.
    """
    if not isinstance(text, str):
        return ""
    nfkd_form = unicodedata.normalize('NFD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

def _ensure_connected():
    """Garante que a conexão com Google Sheets e Gemini está ativa."""
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
    """Retorna a instância do modelo Gemini."""
    _ensure_connected()
    return _connections["model"]

# --- FUNÇÕES DE DADOS ---

# A função get_or_create_user foi substituída pela nova lógica de autenticação abaixo.

def authenticate_or_register_user(email, password):
    """
    Autentica um usuário ou registra um novo, incluindo a lógica de atualizar senha.
    Retorna um dicionário com status, mensagem e user_id.
    """
    _ensure_connected()
    users_sheet = _connections["spreadsheet"].worksheet("users")

    try:
        cell = users_sheet.find(email)
    except gspread.exceptions.CellNotFound:
        cell = None

    # Cenário 1: Novo Usuário (email não encontrado)
    if cell is None:
        if not password:
            return {'status': 'error', 'message': 'Senha é obrigatória para o cadastro.', 'user_id': None}
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Schema: [email, user_id, created_at, password, active]
        new_user_data = [email, user_id, created_at, hashed_password, ''] # 'active' inicia vazio
        users_sheet.append_row(new_user_data)
        
        return {'status': 'success', 'message': 'Cadastro realizado com sucesso!', 'user_id': user_id}

    # Cenário 2: Usuário Existente (email encontrado)
    user_row = users_sheet.row_values(cell.row)
    user_id = user_row[1] # Coluna user_id
    stored_password_hash = user_row[3] if len(user_row) > 3 else None # Coluna password

    # Cenário 2a: Usuário existe, mas não tem senha (primeiro cadastro de senha)
    if not stored_password_hash:
        if not password:
            return {'status': 'error', 'message': 'Por favor, crie uma senha para sua conta.', 'user_id': None}
        
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        users_sheet.update_cell(cell.row, 4, hashed_password) # Atualiza a coluna da senha (coluna D)
        
        return {'status': 'success', 'message': 'Senha cadastrada com sucesso! Bem-vindo!', 'user_id': user_id}

    # Cenário 2b: Usuário existe e tem senha (tentativa de login)
    if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash.encode('utf-8')):
        return {'status': 'success', 'message': 'Login realizado com sucesso!', 'user_id': user_id}
    else:
        return {'status': 'error', 'message': 'Senha incorreta. Tente novamente.', 'user_id': None}


# O restante das funções de 'services.py' permanece o mesmo
def get_next_question(user_id, status_filters=['nao_respondidas'], specialty=None, provas=None, keywords=None):
    """
    Busca a próxima questão, com suporte para múltiplos filtros de status.
    """
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

    if not list_of_pools:
        return None

    initial_pool = pd.concat(list_of_pools).drop_duplicates(subset=['question_id']).reset_index(drop=True)

    if initial_pool.empty:
        return None

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

    if final_pool.empty:
        return None
        
    return final_pool.sample(n=1).to_dict('records')[0]

def save_answer(user_id, question_id, user_answer, is_correct):
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
        
        if old_is_correct and not is_correct:
            return

        try:
            cell = answers_sheet.find(existing_answer['answer_id'].iloc[0])
            row_index = cell.row
            
            updated_row = [
                existing_answer['answer_id'].iloc[0],
                str(user_id),
                str(question_id),
                user_answer,
                'TRUE' if is_correct else 'FALSE',
                datetime.now().isoformat()
            ]
            answers_sheet.update(f'A{row_index}:F{row_index}', [updated_row])
        except Exception as e:
            print(f"ERRO: Não foi possível encontrar ou atualizar a linha da resposta. Erro: {e}")
            
    st.cache_data.clear()

# ... (o resto das funções, como get_performance_data, get_all_specialties, etc., continuam aqui sem alteração)
# ... (Para manter a resposta concisa, não vou repetir todas as outras funções que não foram alteradas)