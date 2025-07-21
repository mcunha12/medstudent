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

# --- WIKI IA FUNCTIONS (SQLite Version - CORRIGIDA) ---

def _generate_title_and_explanation(user_query: str):
    """
    Usa a IA para gerar um título otimizado e uma explicação detalhada.
    """
    prompt = f"""
Você é um médico especialista e educador, criando material de estudo para um(a) estudante de medicina em preparação para a residência.
**Tópico da Pesquisa do Usuário:** "{user_query}"
**Sua Tarefa (em uma única resposta):**
1.  **Gerar um Título Otimizado:** Primeiro, crie um título claro, conciso e otimizado para busca sobre o tópico principal. O título deve ser autoexplicativo.
2.  **Gerar a Explicação:** Depois do título, gere uma explicação completa e aprofundada, seguindo a estrutura de formatação Markdown abaixo.
**Formato OBRIGATÓRIO da sua resposta:**
<title>Seu Título Otimizado Aqui</title>
<explanation>
### 1. Definição Rápida
* **Conceito:** [Definição concisa do tópico em uma ou duas frases.]
* **Relevância Clínica:** [Breve explicação de por que este conceito é crucial na prática médica e em provas de residência.]
### 2. Aprofundamento Técnico e Integração
[Desenvolva o conceito de forma detalhada. Conecte-o com a fisiopatologia, farmacologia, semiologia, etc. Discuta diagnóstico, tratamento (com posologias comuns), prognóstico e complicações.]
### 3. Análise 5W2H
* **What (O quê):** O que é?
* **Why (Por quê):** Por que ocorre/é importante?
* **Who (Quem):** Quem afeta?
* **Where (Onde):** Onde se manifesta?
* **When (Quando):** Quando ocorre?
* **How (Como):** Como é o manejo?
* **How Much (Quanto custa):** Qual o impacto?
### 4. Análise dos 5 Porquês
[Aplique a técnica dos 5 Porquês para explorar a causa raiz do problema.]
* **1. Por que...?**
    * Porque...
* **2. Por que...?**
    * Porque... (continue até 5)
### 5. Pontos-Chave e Analogias
[Liste 2-3 conceitos complexos e explique-os de forma simplificada, usando analogias.]
* **Ponto-Chave 1:** ...
* **Ponto-Chave 2:** ...
### 6. Referências
[Cite de forma indireta 2-3 fontes de alta qualidade (ex: UpToDate, Harrison's, diretrizes de sociedades médicas).]
</explanation>
"""
    try:
        model = get_gemini_model()
        response = model.generate_content(prompt)
        if response.prompt_feedback.block_reason:
            reason = response.prompt_feedback.block_reason.name
            return {'title': 'Erro', 'explanation': f"**Erro:** A geração de conteúdo foi bloqueada ({reason})."}
        
        full_text = response.text
        title = full_text.split('<title>')[1].split('</title>')[0].strip()
        explanation = full_text.split('<explanation>')[1].split('</explanation>')[0].strip()
        
        return {'title': title, 'explanation': explanation}
    except Exception as e:
        return {'title': 'Erro', 'explanation': f"**Erro ao contatar a IA:** {e}"}

def get_user_search_history(user_id: str):
    """
    Função melhorada para buscar histórico com debug completo
    """
    conn = None
    try:
        # Cria nova conexão para esta função
        conn = get_db_connection()
        
        # Debug: Mostra informações no Streamlit
        st.write(f"🔍 **Buscando histórico para User ID:** `{user_id}`")
        
        # 1. Verifica se há registros na tabela
        total_query = "SELECT COUNT(*) as total FROM ai_concepts"
        total_result = pd.read_sql_query(total_query, conn)
        total_registros = total_result.iloc[0]['total']
        
        st.write(f"📊 **Total de conceitos na tabela:** {total_registros}")
        
        if total_registros == 0:
            st.warning("⚠️ Tabela ai_concepts está vazia!")
            return []
        
        # 2. Mostra todos os registros para debug
        all_concepts = pd.read_sql_query(
            "SELECT id, title, users, created_at FROM ai_concepts ORDER BY created_at DESC", 
            conn
        )
        st.write("🗃️ **Todos os registros na tabela:**")
        st.dataframe(all_concepts)
        
        # 3. Testa diferentes tipos de busca
        search_results = {}
        
        # Busca exata
        query_exact = "SELECT id, title FROM ai_concepts WHERE users = ?"
        result_exact = pd.read_sql_query(query_exact, conn, params=(user_id,))
        search_results['Busca Exata'] = len(result_exact)
        
        # Busca início
        query_start = "SELECT id, title FROM ai_concepts WHERE users LIKE ?"
        result_start = pd.read_sql_query(query_start, conn, params=(f"{user_id},%",))
        search_results['Busca Início'] = len(result_start)
        
        # Busca meio
        query_middle = "SELECT id, title FROM ai_concepts WHERE users LIKE ?"
        result_middle = pd.read_sql_query(query_middle, conn, params=(f"%,{user_id},%",))
        search_results['Busca Meio'] = len(result_middle)
        
        # Busca final
        query_end = "SELECT id, title FROM ai_concepts WHERE users LIKE ?"
        result_end = pd.read_sql_query(query_end, conn, params=(f"%,{user_id}",))
        search_results['Busca Final'] = len(result_end)
        
        # Busca genérica (LIKE)
        query_like = "SELECT id, title FROM ai_concepts WHERE users LIKE ?"
        result_like = pd.read_sql_query(query_like, conn, params=(f"%{user_id}%",))
        search_results['Busca LIKE'] = len(result_like)
        
        st.write("🔎 **Resultados dos diferentes tipos de busca:**")
        for tipo, quantidade in search_results.items():
            st.write(f"- **{tipo}:** {quantidade} resultados")
        
        # 4. Determina qual resultado retornar
        final_result = []
        if len(result_exact) > 0:
            st.success("✅ Usando busca exata")
            final_result = result_exact.to_dict('records')
        elif len(result_like) > 0:
            st.success("✅ Usando busca LIKE")
            final_result = result_like.to_dict('records')
        else:
            st.warning("⚠️ Nenhum resultado encontrado em nenhuma busca")
            final_result = []
        
        # Fecha a conexão antes de retornar
        if conn:
            conn.close()
            
        return final_result
            
    except Exception as e:
        st.error(f"❌ Erro na função get_user_search_history: {e}")
        # Garante que a conexão seja fechada mesmo em caso de erro
        if conn:
            try:
                conn.close()
            except:
                pass
        return []
    
def find_or_create_ai_concept(user_query: str, user_id: str):
    """
    Versão melhorada com debug para rastrear problemas de salvamento.
    """
    try:
        conn = get_db_connection()
        all_ai_concepts = pd.read_sql_query("SELECT id, title, explanation FROM ai_concepts", conn)
        
        print(f"[DEBUG] Processando query: '{user_query}' para user_id: {user_id}")
        
        if not all_ai_concepts.empty:
            search_corpus = "\n".join(
                [f"ID: {row['id']}\nTítulo: {row['title']}\nExplicação: {row['explanation'][:200]}\n---" 
                 for index, row in all_ai_concepts.iterrows()]
            )
            prompt = f"""
Você é um motor de busca semântica. Analise a "Pergunta do Usuário" e o "Conteúdo Existente".
Sua tarefa é encontrar o ID do conteúdo mais relevante para a pergunta.
**Pergunta do Usuário:** "{user_query}"
**Conteúdo Existente:**
{search_corpus}
**Instruções:**
- Se encontrar um conteúdo altamente relevante, retorne APENAS o seu ID. Exemplo: "abc-123-def-456"
- Se nada for relevante, retorne a palavra "NENHUM".
"""
            model = get_gemini_model()
            response = model.generate_content(prompt)
            found_id = response.text.strip().replace("ID:", "").strip()
            
            print(f"[DEBUG] IA encontrou ID: {found_id}")
            
            if found_id != "NENHUM":
                concept_data_list = all_ai_concepts[all_ai_concepts['id'] == found_id]
                if not concept_data_list.empty:
                    concept_data = concept_data_list.iloc[0]
                    cursor = conn.cursor()
                    
                    # Busca os usuários atuais
                    current_users_result = pd.read_sql_query("SELECT users FROM ai_concepts WHERE id = ?", conn, params=(found_id,))
                    users_str = current_users_result.iloc[0]['users'] if not current_users_result.empty else ""
                    
                    print(f"[DEBUG] Usuários atuais no conceito {found_id}: '{users_str}'")
                    
                    # Processa a lista de usuários
                    user_list = []
                    if users_str and users_str.strip():
                        user_list = [u.strip() for u in users_str.split(',') if u.strip()]
                    
                    if user_id not in user_list:
                        user_list.append(user_id)
                        new_users_str = ','.join(user_list)
                        print(f"[DEBUG] Adicionando usuário. Nova lista: '{new_users_str}'")
                        
                        cursor.execute("UPDATE ai_concepts SET users = ? WHERE id = ?", (new_users_str, found_id))
                        conn.commit()
                        print(f"[DEBUG] Usuário adicionado com sucesso")
                    else:
                        print(f"[DEBUG] Usuário {user_id} já estava na lista")
                        
                    conn.close()
                    return {'id': found_id, 'title': concept_data['title'], 'explanation': concept_data['explanation']}

        # Se não encontrou conceito existente, cria um novo
        print(f"[DEBUG] Criando novo conceito para: '{user_query}'")
        
        with st.spinner(f"Nenhum conceito encontrado. Gerando uma nova explicação para '{user_query}'..."):
            ai_result = _generate_title_and_explanation(user_query)
        
        if ai_result['title'] == 'Erro':
            return {'id': None, 'title': 'Erro na Geração', 'explanation': ai_result['explanation']}
            
        new_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        cursor = conn.cursor()
        
        print(f"[DEBUG] Salvando novo conceito com ID: {new_id}")
        print(f"[DEBUG] Título: {ai_result['title']}")
        print(f"[DEBUG] User ID: {user_id}")
        
        cursor.execute(
            "INSERT INTO ai_concepts (id, title, explanation, users, created_at) VALUES (?, ?, ?, ?, ?)",
            (new_id, ai_result['title'], ai_result['explanation'], user_id, created_at)
        )
        conn.commit()
        
        print(f"[DEBUG] Conceito salvo com sucesso!")
        conn.close()
        
        return {'id': new_id, 'title': ai_result['title'], 'explanation': ai_result['explanation']}
        
    except Exception as e:
        print(f"[DEBUG] Erro geral em find_or_create_ai_concept: {e}")
        return {'id': None, 'title': 'Erro', 'explanation': f"Erro: {e}"}

def debug_ai_concepts_table():
    """
    Função para debugar a tabela ai_concepts - mostra toda a estrutura
    """
    try:
        conn = get_db_connection()
        
        # Mostra a estrutura da tabela
        table_info = pd.read_sql_query("PRAGMA table_info(ai_concepts)", conn)
        print(f"[DEBUG] Estrutura da tabela ai_concepts:")
        print(table_info)
        
        # Mostra todos os registros
        all_data = pd.read_sql_query("SELECT * FROM ai_concepts", conn)
        print(f"[DEBUG] Todos os registros na tabela:")
        print(all_data)
        
        conn.close()
        
    except Exception as e:
        print(f"[DEBUG] Erro ao inspecionar tabela: {e}")

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

@st.cache_data(ttl=1)
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