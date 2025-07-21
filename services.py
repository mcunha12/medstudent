import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta
import unicodedata
import bcrypt

DB_FILE = 'medstudent.db'

# --- GERENCIAMENTO DE CONEXÃO COM O BANCO DE DADOS ---
@st.cache_resource
def get_db_connection():
    """Cria e gerencia a conexão com o banco de dados SQLite."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    return conn

def normalize_for_search(text: str) -> str:
    """(Função auxiliar) Normaliza texto para buscas."""
    if not isinstance(text, str): return ""
    nfkd_form = unicodedata.normalize('NFD', text)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower()

# --- GERENCIAMENTO DE CONEXÃO COM A IA (GEMINI) ---
_gemini_model = None
def get_gemini_model():
    """Cria e gerencia a conexão com a API do Gemini."""
    global _gemini_model
    if _gemini_model is None:
        try:
            genai.configure(api_key=st.secrets.google_ai.api_key)
            _gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        except Exception as e:
            st.error(f"Falha na conexão com a API do Gemini: {e}")
            st.stop()
    return _gemini_model

# --- AUTHENTICATION & USER FUNCTIONS (SQLite Version) ---

def authenticate_or_register_user(email, password):
    try:
        email = email.strip().lower()
        conn = get_db_connection()
        query = "SELECT * FROM users WHERE email = ?"
        user_record = pd.read_sql_query(query, conn, params=(email,))
        
        if user_record.empty:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, user_id, created_at, password) VALUES (?, ?, ?, ?)",
                (email, user_id, created_at, hashed_password)
            )
            conn.commit()
            return {'status': 'success', 'message': 'Cadastro realizado com sucesso!', 'user_id': user_id}

        user_id = user_record['user_id'].iloc[0]
        stored_password_hash = user_record['password'].iloc[0]

        if pd.isna(stored_password_hash) or stored_password_hash == '':
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
            conn.commit()
            return {'status': 'success', 'message': 'Senha cadastrada com sucesso!', 'user_id': user_id}
        
        if bcrypt.checkpw(password.encode('utf-8'), str(stored_password_hash).encode('utf-8')):
            return {'status': 'success', 'message': 'Login realizado com sucesso!', 'user_id': user_id}
        else:
            return {'status': 'error', 'message': 'Senha incorreta. Tente novamente.', 'user_id': None}
    except Exception as e:
        st.error(f"Ocorreu um erro durante a autenticação: {e}")
        return {'status': 'error', 'message': 'Erro de sistema. Tente novamente mais tarde.', 'user_id': None}

# --- SIMULADO & QUESTIONS FUNCTIONS (SQLite Version) ---

def save_answer(user_id, question_id, user_answer, is_correct):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT is_correct FROM answers WHERE user_id = ? AND question_id = ?"
        params = (str(user_id), str(question_id))
        existing_answer_df = pd.read_sql_query(query, conn, params=params)
        timestamp = datetime.now().isoformat()
        is_correct_str = 'TRUE' if is_correct else 'FALSE'

        if existing_answer_df.empty:
            answer_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO answers (answer_id, user_id, question_id, user_answer, is_correct, answered_at) VALUES (?, ?, ?, ?, ?, ?)",
                (answer_id, str(user_id), str(question_id), user_answer, is_correct_str, timestamp)
            )
        else:
            old_is_correct = str(existing_answer_df['is_correct'].iloc[0]).upper() == 'TRUE'
            if not old_is_correct and is_correct:
                cursor.execute(
                    "UPDATE answers SET user_answer = ?, is_correct = ?, answered_at = ? WHERE user_id = ? AND question_id = ?",
                    (user_answer, is_correct_str, timestamp, str(user_id), str(question_id))
                )
        conn.commit()
    except Exception as e:
        st.error(f"Não foi possível salvar sua resposta: {e}")

def get_simulado_questions(user_id, count=20, status_filters=['nao_respondidas'], specialty=None, provas=None, keywords=None):
    try:
        conn = get_db_connection()
        questions_df = pd.read_sql_query("SELECT * FROM questions", conn)
        answers_df = pd.read_sql_query("SELECT question_id, is_correct FROM answers WHERE user_id = ?", conn, params=(str(user_id),))
        if questions_df.empty: return []
        
        list_of_pools = []
        if 'nao_respondidas' in status_filters:
            if not answers_df.empty:
                answered_ids = answers_df['question_id'].unique().tolist()
                pool = questions_df[~questions_df['question_id'].isin(answered_ids)]
            else:
                pool = questions_df.copy()
            list_of_pools.append(pool)
        if not answers_df.empty and ('corretas' in status_filters or 'incorretas' in status_filters):
            answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
            if 'corretas' in status_filters:
                correct_ids = answers_df[answers_df['is_correct'] == True]['question_id'].unique().tolist()
                list_of_pools.append(questions_df[questions_df['question_id'].isin(correct_ids)])
            if 'incorretas' in status_filters:
                incorrect_ids = answers_df[answers_df['is_correct'] == False]['question_id'].unique().tolist()
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
    except Exception as e:
        st.warning(f"Não foi possível buscar as questões do simulado: {e}")
        return []

# --- WIKI/CONCEPTS FUNCTIONS (SQLite Version) ---

@st.cache_data(ttl=3600)
def get_all_concepts_from_questions():
    """Busca todos os subtópicos únicos e suas áreas principais da tabela 'questions'."""
    try:
        conn = get_db_connection()
        query = "SELECT areas_principais, subtopicos FROM questions"
        df = pd.read_sql_query(query, conn)
        df.dropna(subset=['subtopicos'], inplace=True)
        df['subtopicos'] = df['subtopicos'].str.split(',')
        df['areas_principais'] = df['areas_principais'].fillna('').str.split(',')
        df = df.explode('subtopicos')
        df = df.explode('areas_principais')
        df['subtopicos'] = df['subtopicos'].str.strip()
        df['areas_principais'] = df['areas_principais'].str.strip()
        df.dropna(subset=['subtopicos', 'areas_principais'], inplace=True)
        df = df[df['subtopicos'] != '']
        df = df[df['areas_principais'] != '']
        concept_areas = df.groupby('subtopicos')['areas_principais'].apply(lambda x: ', '.join(sorted(x.unique()))).reset_index()
        concept_areas.rename(columns={'subtopicos': 'concept', 'areas_principais': 'areas'}, inplace=True)
        return concept_areas
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de conceitos com áreas: {e}")
        return pd.DataFrame(columns=['concept', 'areas'])

def _save_concept(concept_name, explanation, areas_str):
    """Salva um novo conceito no banco de dados SQLite. (Não invalida mais o cache)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO concepts (concept, explanation, areas) VALUES (?, ?, ?)", (concept_name, explanation, areas_str))
        conn.commit()
    except Exception as e:
        print(f"ERRO: Falha ao salvar o conceito '{concept_name}' no SQLite. Erro: {e}")

def _generate_concept_with_gemini(concept_name):
    """Gera a explicação de um conceito médico usando a API do Gemini."""
    prompt = f"""
Você é um médico especialista e educador, criando material de estudo para um(a) estudante de medicina em preparação para a residência.
**Tópico Principal:** "{concept_name}"
... (o prompt completo que você definiu) ...
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

@st.cache_data(ttl=31536000) # Cache de 1 ano (365 dias * 24h * 60m * 60s)
def get_concept_explanation(concept_name: str):
    """
    Busca a explicação de um conceito diretamente no banco. 
    Se não existir, gera com a IA e salva.
    Esta é a abordagem mais otimizada em termos de memória.
    """
    conn = get_db_connection()
    # 1. Faz uma busca pontual e rápida pela explicação de um único conceito
    query = "SELECT explanation FROM concepts WHERE concept = ?"
    result_df = pd.read_sql_query(query, conn, params=(concept_name,))
    
    # 2. Se a explicação for encontrada, retorna imediatamente
    if not result_df.empty:
        return result_df['explanation'].iloc[0]
    
    # 3. Se não for encontrada, gera com a IA, salva e retorna
    else:
        # Busca as áreas do conceito para poder salvá-lo corretamente
        all_concepts_df = get_all_concepts_from_questions()
        concept_info = all_concepts_df[all_concepts_df['concept'] == concept_name]
        areas_str = concept_info['areas'].iloc[0] if not concept_info.empty else "Geral"
        
        # Gera a nova explicação
        explanation = _generate_concept_with_gemini(concept_name)
        
        # Salva no banco para que na próxima vez a busca encontre
        if not explanation.startswith("**Erro:**"):
            _save_concept(concept_name, explanation, areas_str)
            
        return explanation
    
@st.cache_data(ttl=600)
def get_wiki_data(user_id):
    """
    Função principal e OTIMIZADA para carregar os dados da Wiki.
    1. Pega todos os conceitos e suas áreas diretamente da tabela 'concepts'.
    2. Pega os conceitos que o usuário errou.
    3. Junta tudo em um único DataFrame com a flag 'user_has_error'.
    """
    conn = get_db_connection()
    
    # Passo 1: Leitura super rápida da tabela 'concepts' já processada
    concepts_df = pd.read_sql_query("SELECT concept, areas FROM concepts", conn)
    if concepts_df.empty:
        return pd.DataFrame(columns=['concept', 'areas', 'user_has_error'])

    # Passo 2: Pega os conceitos que o usuário errou
    query = """
    SELECT DISTINCT q.subtopicos
    FROM answers a JOIN questions q ON a.question_id = q.question_id
    WHERE a.user_id = ? AND a.is_correct = 'FALSE'
    """
    incorrect_df = pd.read_sql_query(query, conn, params=(str(user_id),))
    
    incorrect_list = []
    if not incorrect_df.empty:
        incorrect_list = incorrect_df['subtopicos'].dropna().str.split(',').explode().str.strip().unique().tolist()

    # Passo 3: Adiciona a flag 'user_has_error'
    concepts_df['user_has_error'] = concepts_df['concept'].isin(incorrect_list)
    return concepts_df

def get_relevant_concepts(user_query: str, all_concepts: list[str]) -> list[str]:
    """Usa a IA para encontrar os conceitos mais relevantes."""
    if not user_query or not all_concepts: return all_concepts
    concept_list_str = "\n- ".join(all_concepts)
    prompt = f"""
Você é um assistente de busca inteligente para uma Wiki médica...
**Pergunta do Usuário:** "{user_query}"
... (resto do prompt)
"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        relevant_list = json.loads(response.text)
        if isinstance(relevant_list, list) and all(isinstance(item, str) for item in relevant_list):
            return relevant_list
        else:
            return [c for c in all_concepts if user_query.lower() in c.lower()]
    except Exception:
        return [c for c in all_concepts if user_query.lower() in c.lower()]

# --- PERFORMANCE ANALYSIS & OTHER FUNCTIONS (SQLite Version) ---

@st.cache_data(ttl=600)
def get_performance_data(user_id):
    try:
        conn = get_db_connection()
        query = """
        SELECT a.*, q.enunciado, q.alternativas, q.comentarios, q.alternativa_correta,
               q.areas_principais, q.subtopicos, q.prova
        FROM answers a LEFT JOIN questions q ON a.question_id = q.question_id
        WHERE a.user_id = ?
        """
        merged_df = pd.read_sql_query(query, conn, params=(str(user_id),))
        if merged_df.empty: return None

        merged_df['is_correct'] = merged_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        merged_df['answered_at'] = pd.to_datetime(merged_df['answered_at'])
        
        all_answers_for_ranking = pd.read_sql_query("SELECT user_id, is_correct, answered_at FROM answers", conn)
        all_answers_for_ranking['is_correct'] = all_answers_for_ranking['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')

        merged_df['areas_principais'] = merged_df['areas_principais'].fillna('').str.split(',')
        merged_df['subtopicos'] = merged_df['subtopicos'].fillna('').str.split(',')
        
        areas_df = merged_df.explode('areas_principais')
        areas_df['areas_principais'] = areas_df['areas_principais'].str.strip()
        
        subtopicos_df = merged_df.explode('subtopicos')
        subtopicos_df['subtopicos'] = subtopicos_df['subtopicos'].str.strip()
        
        return {
            "all_answers": merged_df, "areas_exploded": areas_df, 
            "subtopicos_exploded": subtopicos_df, "all_answers_for_ranking": all_answers_for_ranking
        }
    except Exception as e:
        st.warning(f"Não foi possível processar seus dados de performance: {e}")
        return None

def calculate_metrics(df):
    """(Sem alterações) Calcula métricas básicas de um DataFrame de respostas."""
    if df is None or df.empty: return {"answered": 0, "correct": 0, "accuracy": 0.0}
    answered = len(df)
    correct = df['is_correct'].sum()
    accuracy = (correct / answered * 100) if answered > 0 else 0.0
    return {"answered": answered, "correct": correct, "accuracy": accuracy}

def get_time_window_metrics(all_answers_df, days=None):
    """(Sem alterações) Calcula métricas para uma janela de tempo específica."""
    if all_answers_df is None: return calculate_metrics(None)
    if days is None: return calculate_metrics(all_answers_df)
    
    if all_answers_df['answered_at'].dt.tz:
        cutoff_date = datetime.now(all_answers_df['answered_at'].dt.tz) - timedelta(days=days)
    else:
        cutoff_date = datetime.now() - timedelta(days=days)

    window_df = all_answers_df[all_answers_df['answered_at'] >= cutoff_date]
    return calculate_metrics(window_df)

def get_temporal_performance(all_answers_df, period='W'):
    """(Sem alterações) Agrega a performance por período (Semana 'W' ou Dia 'D')."""
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
    """(Sem alterações) Calcula a performance por área principal."""
    if areas_exploded_df is None or areas_exploded_df.empty: return pd.DataFrame()
    areas_summary = areas_exploded_df.groupby('areas_principais').agg(
        total_respondidas=('question_id', 'count'), 
        total_acertos=('is_correct', 'sum')
    ).reset_index()
    areas_summary['taxa_de_acerto'] = (areas_summary['total_acertos'] / areas_summary['total_respondidas'] * 100).fillna(0)
    return areas_summary

def get_subtopics_for_review(subtopicos_exploded_df, days=7):
    """(Sem alterações) Identifica os subtópicos com mais erros nos últimos dias."""
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
    """(Sem alterações) Calcula o ranking de performance de um usuário."""
    if all_answers_df.empty: return None
    df = all_answers_df.copy()
    df['answered_at'] = pd.to_datetime(df['answered_at'])
    now = datetime.now(df['answered_at'].dt.tz if df['answered_at'].dt.tz else None)
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
    """Busca o histórico de um usuário no SQLite."""
    try:
        conn = get_db_connection()
        query = """
        SELECT *
        FROM answers a
        LEFT JOIN questions q ON a.question_id = q.question_id
        WHERE a.user_id = ?
        ORDER BY a.answered_at DESC
        """
        merged_df = pd.read_sql_query(query, conn, params=(str(user_id),))
        if merged_df.empty:
            return pd.DataFrame()
        merged_df['is_correct'] = merged_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        return merged_df
    except Exception as e:
        st.error(f"Erro ao buscar histórico de revisão: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_all_provas():
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT DISTINCT prova FROM questions WHERE prova IS NOT NULL", conn)
        return sorted(list(df['prova'].unique()))
    except Exception as e:
        st.warning(f"Não foi possível carregar la lista de provas: {e}")
        return []

@st.cache_data(ttl=3600)
def get_global_platform_stats():
    default_stats = {'total_students': 0, 'active_this_week': 0, 'answered_last_7_days': 0, 'accuracy_last_7_days': 0.0}
    try:
        conn = get_db_connection()
        users_df = pd.read_sql_query("SELECT count(user_id) as total_students FROM users", conn)
        answers_df = pd.read_sql_query("SELECT user_id, is_correct, answered_at FROM answers", conn)
        
        total_students = users_df['total_students'].iloc[0]
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
            'total_students': total_students, 'active_this_week': active_this_week,
            'answered_last_7_days': answered_last_7_days, 'accuracy_last_7_days': accuracy_last_7_days
        }
    except Exception as e:
        print(f"Erro ao calcular estatísticas globais: {e}")
        return default_stats
    
@st.cache_data(ttl=3600)
def get_all_concepts_with_areas():
    """
    Busca todos os subtópicos únicos e suas áreas principais associadas.
    Retorna um DataFrame com as colunas ['subtopic', 'area'].
    """
    try:
        conn = get_db_connection()
        # Seleciona apenas as colunas necessárias
        query = "SELECT areas_principais, subtopicos FROM questions"
        df = pd.read_sql_query(query, conn)
        
        # Remove linhas onde os subtopicos são nulos
        df.dropna(subset=['subtopicos'], inplace=True)
        
        # Transforma as strings separadas por vírgula em listas
        df['subtopicos'] = df['subtopicos'].str.split(',')
        df['areas_principais'] = df['areas_principais'].fillna('').str.split(',')
        
        # "Explode" para ter uma linha por combinação de área/subtópico
        df = df.explode('subtopicos')
        df = df.explode('areas_principais')
        
        # Limpa os dados
        df['subtopicos'] = df['subtopicos'].str.strip()
        df['areas_principais'] = df['areas_principais'].str.strip()
        df.dropna(subset=['subtopicos', 'areas_principais'], inplace=True)
        df = df[df['subtopicos'] != '']
        df = df[df['areas_principais'] != '']
        
        # Renomeia as colunas para um nome mais claro
        df.rename(columns={'subtopicos': 'concept', 'areas_principais': 'area'}, inplace=True)
        
        # Remove duplicatas e ordena
        return df.drop_duplicates().sort_values(by=['area', 'concept']).reset_index(drop=True)
        
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de conceitos com áreas: {e}")
        return pd.DataFrame(columns=['concept', 'area'])

@st.cache_data(ttl=600)
def get_subtopics_from_incorrect_answers(user_id):
    """
    Busca uma lista de subtópicos únicos de questões que um usuário específico errou.
    """
    try:
        conn = get_db_connection()
        query = """
        SELECT DISTINCT q.subtopicos
        FROM answers a
        JOIN questions q ON a.question_id = q.question_id
        WHERE a.user_id = ? AND a.is_correct = 'FALSE'
        """
        df = pd.read_sql_query(query, conn, params=(str(user_id),))
        
        if df.empty or 'subtopicos' not in df.columns:
            return []
            
        # Processamento para extrair a lista única
        subtopics = df['subtopicos'].dropna().str.split(',').explode()
        unique_subtopics = subtopics.str.strip().unique().tolist()
        return [topic for topic in unique_subtopics if topic]
        
    except Exception as e:
        st.warning(f"Não foi possível carregar os subtópicos de questões incorretas: {e}")
        return []

    
@st.cache_data(ttl=3600)
def get_all_specialties():
    """Busca todas as áreas principais únicas do SQLite."""
    try:
        conn = get_db_connection()
        df = pd.read_sql_query("SELECT areas_principais FROM questions", conn)
        if df.empty or 'areas_principais' not in df.columns:
            return []
        specialties = df['areas_principais'].dropna().str.split(',').explode()
        unique_specialties = sorted(list(specialties.str.strip().unique()))
        return [spec for spec in unique_specialties if spec]
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de especialidades: {e}")
        return []