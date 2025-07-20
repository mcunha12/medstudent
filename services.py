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

# --- AUTHENTICATION & USER FUNCTIONS ---

def authenticate_or_register_user(email, password):
    try:
        email = email.strip().lower()
        _ensure_connected()
        users_sheet = _connections["spreadsheet"].worksheet("users")
        try:
            cell = users_sheet.find(email)
        except gspread.exceptions.CellNotFound:
            cell = None

        if cell is None:
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
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            users_sheet.update_cell(cell.row, 4, hashed_password)
            return {'status': 'success', 'message': 'Senha cadastrada com sucesso! Bem-vindo!', 'user_id': user_id}

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

# --- SIMULADO & QUESTIONS FUNCTIONS ---

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
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        if questions_df.empty: return []
        # ... (lógica de filtragem completa)
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

# --- WIKI/CONCEPTS FUNCTIONS (OTIMIZADAS) ---

def load_concepts_into_session():
    """
    Carrega a planilha 'concepts' para o st.session_state se ela ainda não estiver lá.
    Esta é a otimização principal para reduzir as chamadas de API.
    """
    if 'concepts_df' not in st.session_state:
        try:
            with st.spinner("Carregando biblioteca de conceitos..."):
                _ensure_connected()
                concept_sheet = _connections["spreadsheet"].worksheet("concepts")
                all_records = concept_sheet.get_all_records()
                st.session_state.concepts_df = pd.DataFrame(all_records)
        except Exception as e:
            st.error(f"Não foi possível carregar os conceitos: {e}")
            st.session_state.concepts_df = pd.DataFrame()

def _save_concept(concept_name, explanation):
    """Salva um novo conceito na planilha e invalida o cache em memória."""
    try:
        _ensure_connected()
        concept_sheet = _connections["spreadsheet"].worksheet("concepts")
        concept_sheet.append_row([concept_name, explanation])
        
        # Invalida o DataFrame em memória para forçar o recarregamento com o novo dado
        if 'concepts_df' in st.session_state:
            del st.session_state['concepts_df']
            
        print(f"INFO: Conceito '{concept_name}' salvo no banco de dados.")
    except Exception as e:
        print(f"ERRO: Falha ao salvar o conceito '{concept_name}'. Erro: {e}")

def _generate_concept_with_gemini(concept_name):
    # O prompt permanece o mesmo
    prompt = f"""
Você é um médico especialista e educador, criando material de estudo para um(a) estudante de medicina em preparação para a residência.
**Tópico Principal:** "{concept_name}"
... (seu prompt completo aqui) ...
"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        if response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason.name
            return f"**Erro:** A geração de conteúdo foi bloqueada por motivos de segurança ({reason})."
        return response.text
    except Exception as e:
        return f"**Erro ao contatar a IA:** {e}"

# @st.cache_data(ttl=86400) # O cache agora é gerenciado pelo session_state, então o decorator não é mais ideal aqui
def get_concept_explanation(concept_name: str):
    """
    Busca a explicação de um conceito a partir do DataFrame em memória (session_state).
    Se não encontrar, gera com a IA e salva.
    """
    # Garante que os conceitos estão carregados na sessão
    load_concepts_into_session()
    
    concepts_df = st.session_state.get('concepts_df', pd.DataFrame())
    
    if not concepts_df.empty:
        existing_concept = concepts_df[concepts_df['concept'].str.lower() == concept_name.lower()]
    else:
        existing_concept = pd.DataFrame()
        
    if not existing_concept.empty:
        return existing_concept['explanation'].iloc[0]
    else:
        explanation = _generate_concept_with_gemini(concept_name)
        if not explanation.startswith("**Erro:**"):
            _save_concept(concept_name, explanation)
        return explanation

@st.cache_data(ttl=3600)
def get_all_subtopics():
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        if 'subtopicos' not in questions_df.columns or questions_df.empty:
            return []
        subtopics = questions_df['subtopicos'].dropna().str.split(',').explode()
        unique_subtopics = sorted(list(subtopics.str.strip().unique()))
        unique_subtopics = [topic for topic in unique_subtopics if topic]
        return unique_subtopics
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de subtópicos: {e}")
        return []

def get_relevant_concepts(user_query: str, all_concepts: list[str]) -> list[str]:
    if not user_query or not all_concepts:
        return all_concepts
    concept_list_str = "\n- ".join(all_concepts)
    prompt = f"""
Você é um assistente de busca inteligente para uma Wiki médica...
**Pergunta do Usuário:** "{user_query}"
**Lista de Conceitos Disponíveis:**
- {concept_list_str}
... (resto do prompt)
"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        relevant_list = json.loads(response.text)
        if isinstance(relevant_list, list) and all(isinstance(item, str) for item in relevant_list):
            return relevant_list
        else:
            return [concept for concept in all_concepts if user_query.lower() in concept.lower()]
    except Exception as e:
        print(f"ERRO: Falha na busca semântica com IA: {e}. Usando busca padrão.")
        return [concept for concept in all_concepts if user_query.lower() in concept.lower()]

# --- PERFORMANCE ANALYSIS & OTHER FUNCTIONS ---

@st.cache_data(ttl=600)
def get_performance_data(user_id):
    # Esta função também deveria ser refatorada para usar o session_state
    # se o rate limit persistir em outras páginas.
    # Por enquanto, mantendo como está para não alterar o resto do app.
    try:
        _ensure_connected()
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        questions_df = pd.DataFrame(questions_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        if answers_df.empty or questions_df.empty: return None
        # ... (resto da função)
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

# Adicione esta nova função ao seu arquivo services.py

def get_relevant_concepts(user_query: str, all_concepts: list[str]) -> list[str]:
    """
    Usa a IA para encontrar os conceitos mais relevantes para a pergunta do usuário.
    
    Args:
        user_query: A pergunta ou termo de busca do usuário.
        all_concepts: A lista completa de todos os conceitos disponíveis na Wiki.
        
    Returns:
        Uma lista de strings contendo os nomes dos conceitos relevantes.
    """
    if not user_query or not all_concepts:
        return all_concepts # Se a busca for vazia, retorna todos

    # Converte a lista de conceitos em uma string formatada
    concept_list_str = "\n- ".join(all_concepts)
    
    prompt = f"""
Você é um assistente de busca inteligente para uma Wiki médica. Sua tarefa é identificar quais conceitos de uma lista são relevantes para a pergunta de um usuário.

**Pergunta do Usuário:**
"{user_query}"

**Lista de Conceitos Disponíveis:**
- {concept_list_str}

**Instruções:**
1. Analise a "Pergunta do Usuário".
2. Compare-a com cada item na "Lista de Conceitos Disponíveis".
3. Retorne APENAS os nomes dos conceitos da lista que são diretamente relevantes para a pergunta.
4. A sua resposta deve ser uma lista de Python, contendo apenas os nomes exatos dos conceitos. Exemplo: ["Conceito A", "Conceito B", "Conceito C"]
5. Se nenhum conceito for relevante, retorne uma lista vazia: []
"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        
        # A resposta da IA deve ser uma string no formato de lista Python
        # Ex: '["Fibrilação Atrial", "Flutter Atrial"]'
        # Usamos json.loads para converter essa string em uma lista real
        relevant_list = json.loads(response.text)
        
        # Validação final para garantir que é uma lista de strings
        if isinstance(relevant_list, list) and all(isinstance(item, str) for item in relevant_list):
            return relevant_list
        else:
            # Se a IA retornar algo inesperado, voltamos para a busca simples
            print("WARN: A resposta da IA não foi uma lista de strings. Usando busca padrão.")
            return [concept for concept in all_concepts if user_query.lower() in concept.lower()]

    except (json.JSONDecodeError, Exception) as e:
        # Se ocorrer qualquer erro (formato da IA, conexão, etc.),
        # usamos a busca por filtro de texto como um fallback seguro.
        print(f"ERRO: Falha na busca semântica com IA: {e}. Usando busca padrão.")
        return [concept for concept in all_concepts if user_query.lower() in concept.lower()]