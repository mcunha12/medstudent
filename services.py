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

@st.cache_data(ttl=2592000) # Cache de 1 mês
def load_concepts_df():
    """
    Carrega toda a tabela 'concepts' do SQLite para um DataFrame cacheado.
    O cache dura 1 mês, mas é invalidado por _save_concept.
    """
    try:
        conn = get_db_connection()
        return pd.read_sql_query("SELECT * FROM concepts", conn)
    except Exception as e:
        st.error(f"Não foi possível carregar os conceitos do banco de dados: {e}")
        return pd.DataFrame()

def _save_concept(concept_name, explanation):
    """Salva um novo conceito no banco de dados SQLite e invalida o cache."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO concepts (concept, explanation) VALUES (?, ?)", (concept_name, explanation))
        conn.commit()
        # Limpa o cache para forçar o recarregamento com o novo dado
        load_concepts_df.clear()
    except Exception as e:
        print(f"ERRO: Falha ao salvar o conceito '{concept_name}' no SQLite. Erro: {e}")

def _generate_concept_with_gemini(concept_name):
    """Gera a explicação de um conceito médico usando a API do Gemini."""
    prompt = f"""
Você é um médico especialista e educador, criando material de estudo para um(a) estudante de medicina em preparação para a residência.
**Tópico Principal:** "{concept_name}"
**Instruções de Geração:**
Gere uma explicação clara e aprofundada sobre o tópico acima, seguindo estritamente a estrutura de formatação Markdown abaixo. Seja denso, técnico e preciso.
---
### 1. Definição Rápida
* **Conceito:** [Definição concisa do {concept_name} em uma ou duas frases.]
* **Relevância Clínica:** [Breve explicação de por que este conceito é crucial na prática médica e em provas de residência.]
### 2. Aprofundamento Técnico e Integração
[Desenvolva o conceito de forma detalhada. Evite isolar o assunto. Conecte-o com a fisiopatologia, farmacologia, semiologia e outras áreas correlatas. Se aplicável, discuta a abordagem diagnóstica (exames de imagem, laboratoriais), opções de tratamento (incluindo classes de medicamentos e posologias comuns), prognóstico e manejo de complicações. Use termos técnicos.]
### 3. Análise 5W2H
* **What (O quê):** O que é exatamente {concept_name}?
* **Why (Por quê):** Por que ocorre ou por que é importante?
* **Who (Quem):** Quem é o grupo de risco ou a população mais afetada?
* **Where (Onde):** Onde no corpo ou em que contexto clínico se manifesta?
* **When (Quando):** Quando os sintomas aparecem ou quando a intervenção é necessária?
* **How (Como):** Como é diagnosticado e tratado?
* **How Much (Quanto custa):** Qual o impacto (custo para o sistema de saúde, impacto na qualidade de vida)?
### 4. Análise dos 5 Porquês
[Aplique a técnica dos 5 Porquês para explorar a causa raiz do problema ou da sua principal manifestação clínica. Comece com uma pergunta simples e aprofunde a cada "porquê".]
* **1. Por que [Pergunta inicial sobre o problema]?**
    * Porque [Resposta 1].
* **2. Por que [Pergunta sobre a Resposta 1]?**
    * Porque [Resposta 2].
* **3. Por que [Pergunta sobre a Resposta 2]?**
    * ... e assim por diante até o quinto porquê.
### 5. Pontos-Chave e Analogias
[Liste 2-3 conceitos mais complexos dentro do tópico e explique-os de forma simplificada, usando analogias se possível.]
* **Ponto-Chave 1:** [Nome do conceito complexo]
    * **Explicação:** [Explicação detalhada]
    * **Analogia:** [Analogia para facilitar o entendimento]
* **Ponto-Chave 2:** [Nome do conceito complexo]
    * **Explicação:** [Explicação detalhada]
    * **Analogia:** [Analogia para facilitar o entendimento]
### 6. Referências
[Cite de forma indireta 2-3 fontes de alta qualidade (ex: UpToDate, Harrison's Principles of Internal Medicine, diretrizes de sociedades médicas como AHA, SBC, etc.) que embasam as informações. Ex: "De acordo com as diretrizes mais recentes da Sociedade Brasileira de Cardiologia..." ou "O tratamento de primeira linha, conforme consolidado em revisões como o UpToDate..."]
---
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

def get_concept_explanation(concept_name: str):
    """
    Busca a explicação de um conceito a partir do DataFrame cacheado.
    Se não encontrar, gera com a IA e salva no SQLite.
    """
    concepts_df = load_concepts_df() # Usa a função cacheada
    
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
    """Busca todos os subtópicos únicos da tabela 'questions' no SQLite."""
    try:
        conn = get_db_connection()
        questions_df = pd.read_sql_query("SELECT subtopicos FROM questions", conn)
        if 'subtopicos' not in questions_df.columns or questions_df.empty: return []
        subtopics = questions_df['subtopicos'].dropna().str.split(',').explode()
        unique_subtopics = sorted(list(subtopics.str.strip().unique()))
        return [topic for topic in unique_subtopics if topic]
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de subtópicos: {e}")
        return []

def get_relevant_concepts(user_query: str, all_concepts: list[str]) -> list[str]:
    """Usa a IA para encontrar os conceitos mais relevantes. (Sem alterações)"""
    if not user_query or not all_concepts:
        return all_concepts
    concept_list_str = "\n- ".join(all_concepts)
    prompt = f"""
Você é um assistente de busca inteligente para uma Wiki médica...
**Pergunta do Usuário:** "{user_query}"
**Lista de Conceitos Disponíveis:**
- {concept_list_str}
... (prompt completo)
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