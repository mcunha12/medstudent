import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta
import unicodedata
import bcrypt
from st_supabase_connection import SupabaseConnection

DB_FILE = 'medstudent.db'

# --- GERENCIAMENTO DE CONEXÃO COM O BANCO DE DADOS ---
@st.cache_resource
def get_supabase_conn():
    """
    Cria e retorna uma conexão com o Supabase, reutilizando-a se já existir.
    As credenciais (SUPABASE_URL, SUPABASE_KEY) são lidas de st.secrets.
    """
    if 'supabase_conn' not in st.session_state:
        try:
            st.session_state.supabase_conn = st.connection(
                "supabase", 
                type=SupabaseConnection
            )
        except Exception as e:
            st.error(f"Erro ao conectar com o Supabase: {e}")
            st.stop()
    return st.session_state.supabase_conn


# --- FUNÇÕES AUXILIARES ---

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
            _gemini_model = genai.GenerativeModel('gemini-2.5-pro')
        except Exception as e:
            st.error(f"Falha na conexão com a API do Gemini: {e}")
            st.stop()
    return _gemini_model

# --- AUTHENTICATION & USER FUNCTIONS (SQLite Version) ---

def authenticate_or_register_user(email, password):
    try:
        email = email.strip().lower()
        conn = get_supabase_conn()
        
        # Verifica se o usuário já existe
        response = conn.table("users").select("*").eq("email", email).execute()
        
        # Se não existe, cadastra um novo usuário
        if not response.data:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            user_id = str(uuid.uuid4())
            created_at = datetime.now().isoformat()
            
            insert_response = conn.table("users").insert({
                "email": email,
                "user_id": user_id,
                "created_at": created_at,
                "password": hashed_password,
                "active": True
            }).execute()

            if insert_response.data:
                return {'status': 'success', 'message': 'Cadastro realizado com sucesso!', 'user_id': user_id}
            else:
                 raise Exception("Falha ao inserir usuário no banco de dados.")

        # Se o usuário existe, verifica a senha
        user_record = response.data[0]
        user_id = user_record['user_id']
        stored_password_hash = user_record.get('password')

        # Se não há senha cadastrada, define a senha
        if not stored_password_hash:
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.table("users").update({"password": hashed_password}).eq("email", email).execute()
            return {'status': 'success', 'message': 'Senha cadastrada com sucesso!', 'user_id': user_id}

        # Verifica se a senha fornecida corresponde à senha armazenada
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
        conn = get_supabase_conn()
        timestamp = datetime.now().isoformat()
        is_correct_str = 'TRUE' if is_correct else 'FALSE'
        
        # Verifica se já existe uma resposta para essa questão e usuário
        response = conn.table("answers").select("answer_id, is_correct").eq("user_id", str(user_id)).eq("question_id", str(question_id)).execute()
        
        existing_answer = response.data
        
        if not existing_answer:
            # Insere nova resposta
            answer_id = str(uuid.uuid4())
            conn.table("answers").insert({
                "answer_id": answer_id,
                "user_id": str(user_id),
                "question_id": str(question_id),
                "user_answer": user_answer,
                "is_correct": is_correct_str,
                "answered_at": timestamp
            }).execute()
        else:
            # Atualiza se a resposta anterior estava errada e a nova está correta
            old_is_correct = str(existing_answer[0]['is_correct']).upper() == 'TRUE'
            if not old_is_correct and is_correct:
                conn.table("answers").update({
                    "user_answer": user_answer,
                    "is_correct": is_correct_str,
                    "answered_at": timestamp
                }).eq("user_id", str(user_id)).eq("question_id", str(question_id)).execute()
                
    except Exception as e:
        st.error(f"Não foi possível salvar sua resposta: {e}")

def get_simulado_questions(user_id, count=20, status_filters=['nao_respondidas'], specialty=None, provas=None, keywords=None):
    try:
        conn = get_supabase_conn()
        questions_response = conn.table("questions").select("*").execute()
        answers_response = conn.table("answers").select("question_id, is_correct").eq("user_id", str(user_id)).execute()
        
        questions_df = pd.DataFrame(questions_response.data)
        answers_df = pd.DataFrame(answers_response.data)
        
        if questions_df.empty: return []

        # O restante da lógica de filtragem em pandas permanece o mesmo
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

# --- WIKI IA FUNCTIONS ---

def _extract_concept_from_query(user_query: str) -> str:
    """Usa a IA para identificar o conceito médico central em uma pergunta."""
    if len(user_query.split()) < 5: # Se for uma query curta, provavelmente já é o conceito
        return user_query

    prompt = f"""
    Analise a seguinte pergunta de um estudante de medicina e extraia o tópico ou conceito médico central.
    Sua resposta deve ser APENAS o nome do conceito, de forma concisa e direta.

    Exemplos:
    - Pergunta: "Qual o melhor tratamento para insuficiência cardíaca com fração de ejeção reduzida?" -> Resposta: "Tratamento da Insuficiência Cardíaca com Fração de Ejeção Reduzida"
    - Pergunta: "Como diagnosticar endocardite infecciosa?" -> Resposta: "Diagnóstico de Endocardite Infecciosa"
    - Pergunta: "fisiopatologia da cetoacidose diabética" -> Resposta: "Fisiopatologia da Cetoacidose Diabética"

    Pergunta para analisar: "{user_query}"
    """
    try:
        model = get_gemini_model(model_name="gemini-1.5-flash-latest") # Modelo rápido para tarefas simples
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        # Em caso de erro, apenas usa a query original
        return user_query


# --- NOVA FUNÇÃO ---
def _find_similar_concept(embedding: list[float]):
    """Busca por um conceito similar no DB usando a função RPC."""
    try:
        conn = get_supabase_conn()
        # Chama a função SQL que criamos, passando o embedding e um limiar de similaridade
        SIMILARITY_THRESHOLD = 0.8
        response = conn.rpc('match_concepts', {
            'query_embedding': embedding,
            'match_threshold': SIMILARITY_THRESHOLD,
            'match_count': 1
        }).execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Erro ao buscar conceito similar: {e}")
        return None

# --- NOVA FUNÇÃO ---
def _add_user_to_concept(concept_id: str, user_id: str):
    """Adiciona um user_id ao array de um conceito existente."""
    try:
        conn = get_supabase_conn()
        # Usa a função array_append do postgres para evitar race conditions
        response = conn.from_("ai_concepts").select("user_ids").eq("id", concept_id).single().execute()
        
        existing_users = response.data['user_ids'] or []
        if user_id not in existing_users:
            existing_users.append(user_id)
            conn.from_("ai_concepts").update({"user_ids": existing_users}).eq("id", concept_id).execute()
        return True
    except Exception as e:
        print(f"Erro ao adicionar usuário ao conceito: {e}")
        return False

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
### 3. Entendendo a aplicação e ocorrência
* **What (O quê):** O que é?
* **Why (Por quê):** Por que ocorre/é importante?
* **Who (Quem)::** Quem afeta?
* **Where (Onde):** Onde se manifesta?
* **When (Quando):** Quando ocorre?
* **How (Como):** Como é o manejo?
* **How Much (Quanto custa):** Qual o impacto?
### 4. Investigação de causa-raiz
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
        # Garante que os delimitadores existem antes de tentar dividir
        if '<title>' in full_text and '</title>' in full_text and \
           '<explanation>' in full_text and '</explanation>' in full_text:
            title = full_text.split('<title>')[1].split('</title>')[0].strip()
            explanation = full_text.split('<explanation>')[1].split('</explanation>')[0].strip()
            return {'title': title, 'explanation': explanation}
        else:
            return {'title': 'Erro', 'explanation': "**Erro:** Formato de resposta da IA inesperado. Tente novamente."}
    except Exception as e:
        return {'title': 'Erro', 'explanation': f"**Erro ao contatar a IA:** {e}. Verifique sua conexão e configurações do Gemini."}

def _save_ai_concept(concept_data: dict, user_id: str):
    """ Salva um novo conceito, agora com o 'user_ids' como um array. """
    try:
        conn = get_supabase_conn()
        concept_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Gera o embedding ANTES de salvar
        text_to_embed = f"Título: {concept_data['title']}\n\nExplicação: {concept_data['explanation']}"
        embedding_result = genai.embed_content(
            model="models/embedding-001",
            content=text_to_embed,
            task_type="RETRIEVAL_DOCUMENT"
        )
        
        response = conn.table("ai_concepts").insert({
            "id": concept_id,
            "user_ids": [user_id],  # Salva como um array com o primeiro usuário
            "title": concept_data['title'],
            "explanation": concept_data['explanation'],
            "created_at": created_at,
            "embedding": embedding_result['embedding'] # Salva o embedding
        }).execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao salvar o conceito no banco de dados: {e}")
        return None
    
def find_or_create_ai_concept(user_query: str, user_id: str):
    """
    Orquestra o fluxo e retorna um dicionário com o resultado e uma mensagem.
    """
    # 1. Extrai o conceito-chave da query
    core_concept = _extract_concept_from_query(user_query)
    
    # 2. Gera um embedding para a busca
    query_embedding = genai.embed_content(
        model="models/embedding-001",
        content=core_concept,
        task_type="RETRIEVAL_QUERY"
    )['embedding']
    
    # 3. Busca por um conceito similar existente
    similar_concept = _find_similar_concept(query_embedding)

    # 4. Decide o que fazer e retorna o resultado para a UI
    if similar_concept:
        _add_user_to_concept(similar_concept['id'], user_id)
        # Retorna o conceito encontrado e uma mensagem para o toast
        return {
            "concept": similar_concept, 
            "message": "Encontramos um conceito similar já existente!", 
            "status": "found"
        }
    else:
        # Gera um novo conceito
        new_concept_data = _generate_title_and_explanation(core_concept)

        if new_concept_data and new_concept_data['title'] != 'Erro':
            saved_concept = _save_ai_concept(new_concept_data, user_id)
            return {
                "concept": saved_concept, 
                "message": "Novo conceito gerado e salvo com sucesso!", 
                "status": "created"
            }
        else:
            return {
                "concept": None, 
                "message": "A IA não conseguiu gerar uma resposta.", 
                "status": "error"
            }

def get_user_search_history(user_id: str):
    """Busca conceitos onde o user_id está no array 'user_ids'."""
    try:
        conn = get_supabase_conn()
        # O operador 'cs' significa 'contains' (contém) para arrays
        response = conn.table("ai_concepts").select("id, title").filter("user_ids", "cs", f"{{{user_id}}}").order("created_at", desc=True).limit(10).execute()
        return response.data
    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return []

def get_concept_by_id(concept_id: str):
    """ Busca um único conceito de IA pelo seu ID no Supabase. """
    try:
        conn = get_supabase_conn()
        response = conn.table("ai_concepts").select("id, title, explanation").eq("id", concept_id).limit(1).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        st.error(f"Erro ao buscar o conceito por ID: {e}")
        return None


# --- PERFORMANCE ANALYSIS & OTHER FUNCTIONS (SQLite Version) ---
def get_performance_data(user_id: str):
    """
    Busca e processa todos os dados de performance de um usuário de forma robusta.
    """
    try:
        conn = get_supabase_conn()
        
        # Busca na tabela 'answers' e junta com 'questions'
        response = conn.table("answers").select("*, questions(*)").eq("user_id", user_id).execute()

        if not response.data:
            return None

        # Processamento seguro para evitar colunas duplicadas
        flat_data = []
        for row in response.data:
            question_details = row.pop('questions', {})
            if question_details:
                if 'question_id' in question_details:
                    del question_details['question_id']
                row.update(question_details)
            flat_data.append(row)

        if not flat_data:
            return None

        all_answers = pd.DataFrame(flat_data)
        
        # Converte coluna de data com tratamento de erro
        if 'answered_at' in all_answers.columns:
            all_answers['answered_at'] = pd.to_datetime(all_answers['answered_at'], errors='coerce')
        else:
            all_answers['answered_at'] = pd.to_datetime(all_answers['created_at'], errors='coerce')
        
        all_answers.dropna(subset=['answered_at'], inplace=True)

        # --- CORREÇÃO: Processamento robusto de 'areas_principais' ---
        areas_df = all_answers[['question_id', 'is_correct', 'areas_principais']].copy()
        areas_df.dropna(subset=['areas_principais'], inplace=True)
        areas_df['areas_list'] = areas_df['areas_principais'].astype(str).str.replace(r'[\[\]"]', '', regex=True).str.split(',')
        
        areas_exploded = areas_df.explode('areas_list')
        areas_exploded = areas_exploded.drop(columns=['areas_principais']) # Remove a coluna original
        areas_exploded.rename(columns={'areas_list': 'areas_principais'}, inplace=True) # Renomeia para o nome final
        areas_exploded['areas_principais'] = areas_exploded['areas_principais'].str.strip()
        areas_exploded = areas_exploded[areas_exploded['areas_principais'].astype(bool)]

        # --- CORREÇÃO: Processamento robusto de 'subtopicos' ---
        subtopicos_df = all_answers[['question_id', 'is_correct', 'subtopicos', 'answered_at']].copy()
        subtopicos_df.dropna(subset=['subtopicos'], inplace=True)
        subtopicos_df['subtopicos_list'] = subtopicos_df['subtopicos'].astype(str).str.split(',')
        
        subtopicos_exploded = subtopicos_df.explode('subtopicos_list')
        subtopicos_exploded = subtopicos_exploded.drop(columns=['subtopicos']) # Remove a coluna original
        subtopicos_exploded.rename(columns={'subtopicos_list': 'subtopicos'}, inplace=True) # Renomeia para o nome final
        subtopicos_exploded['subtopicos'] = subtopicos_exploded['subtopicos'].str.strip()
        subtopicos_exploded = subtopicos_exploded[subtopicos_exploded['subtopicos'].astype(bool)]
        
        return {
            "all_answers": all_answers,
            "all_answers_for_ranking": all_answers.copy(),
            "areas_exploded": areas_exploded,
            "subtopicos_exploded": subtopicos_exploded
        }

    except Exception as e:
        print(f"ERRO EM GET_PERFORMANCE_DATA: {e}")
        raise Exception("Não foi possível processar seus dados de performance. Verifique os logs do app.")

    except Exception as e:
        print(f"ERRO EM GET_PERFORMANCE_DATA: {e}")
        raise Exception("Não foi possível processar seus dados de performance. Verifique os logs do app.")

def calculate_metrics(df):
    """
    Calculates performance metrics from a DataFrame, ensuring correct data types.
    This is a helper function for get_time_window_metrics.
    """
    if df.empty:
        return {'answered': 0, 'correct': 0, 'accuracy': 0.0}

    # --- THE CORRECTION IS HERE ---
    # Securely convert 'is_correct' from string ('TRUE') to integer (1)
    df['is_correct'] = (
        df['is_correct'].astype(str).str.lower() == 'true'
    ).astype(int)

    answered = len(df)
    correct = df['is_correct'].sum()
    accuracy = (correct / answered * 100) if answered > 0 else 0.0
    
    return {
        'answered': answered,
        'correct': int(correct),
        'accuracy': accuracy
    }

def get_time_window_metrics(all_answers_df, days=None):
    """
    Calculates performance metrics for a specific time window (e.g., last 7 days).
    """
    if all_answers_df.empty:
        return {'answered': 0, 'correct': 0, 'accuracy': 0.0}

    # Create a copy to ensure the original DataFrame is not modified
    df = all_answers_df.copy()

    if days is None:
        return calculate_metrics(df)
    
    # Filter DataFrame for the specified time window
    df['answered_at'] = pd.to_datetime(df['answered_at'], errors='coerce')
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_df = df[df['answered_at'] >= cutoff_date]
    
    return calculate_metrics(filtered_df)

def get_temporal_performance(all_answers_df, period='W'):
    """
    Calcula a performance temporal, tratando corretamente os tipos de dados
    da coluna 'is_correct'.
    """
    if all_answers_df.empty:
        return pd.DataFrame()

    df = all_answers_df.copy()
    
    df['answered_at'] = pd.to_datetime(df['answered_at'], errors='coerce')
    df.dropna(subset=['answered_at'], inplace=True)

    # --- A CORREÇÃO ESTÁ AQUI ---
    # 1. Garante que a coluna é do tipo string e converte para minúsculas.
    # 2. Compara com a string 'true' para criar uma coluna booleana (True/False).
    # 3. Converte a coluna booleana para inteiros (1/0).
    df['is_correct'] = (
        df['is_correct'].astype(str).str.lower() == 'true'
    ).astype(int)

    # Agrupa os dados por período
    summary = df.set_index('answered_at').resample(period).agg(
        questoes_respondidas=('question_id', 'count'),
        acertos=('is_correct', 'sum')
    ).reset_index()

    summary.rename(columns={'answered_at': 'periodo'}, inplace=True)
    
    # Converte colunas de resultado para numérico para segurança
    summary['acertos'] = pd.to_numeric(summary['acertos'], errors='coerce').fillna(0)
    summary['questoes_respondidas'] = pd.to_numeric(summary['questoes_respondidas'], errors='coerce').fillna(0)

    # Calcula a taxa de acerto de forma segura
    summary['taxa_de_acerto'] = 0.0
    mask = summary['questoes_respondidas'] > 0
    summary.loc[mask, 'taxa_de_acerto'] = \
        (summary.loc[mask, 'acertos'] / summary.loc[mask, 'questoes_respondidas']) * 100

    return summary

def get_areas_performance(areas_exploded_df):
    """
    Calcula a performance por área de conhecimento, tratando os tipos de dados
    de forma robusta.
    """
    if areas_exploded_df.empty:
        return pd.DataFrame()

    df = areas_exploded_df.copy()

    # --- A CORREÇÃO FINAL ESTÁ AQUI ---
    # Garante que a coluna 'is_correct' seja numérica (1 para True, 0 para False)
    # antes de qualquer cálculo.
    df['is_correct'] = (
        df['is_correct'].astype(str).str.lower() == 'true'
    ).astype(int)

    # Agrupa por área para calcular as métricas
    areas_summary = df.groupby('areas_principais').agg(
        total_respondidas=('question_id', 'count'),
        total_acertos=('is_correct', 'sum')
    ).reset_index()
    
    # Calcula a taxa de acerto de forma segura
    areas_summary['taxa_de_acerto'] = 0.0
    mask = areas_summary['total_respondidas'] > 0
    areas_summary.loc[mask, 'taxa_de_acerto'] = \
        (areas_summary.loc[mask, 'total_acertos'] / areas_summary.loc[mask, 'total_respondidas']) * 100

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

def get_ranking_data(all_answers_df, period='W', current_user_id=None):
    """
    Calcula a performance de todos os usuários para o ranking,
    tratando corretamente os tipos de dados.
    """
    if all_answers_df.empty:
        return {}

    df = all_answers_df.copy()
    
    # Filtra os dados para o período selecionado
    df['answered_at'] = pd.to_datetime(df['answered_at'], errors='coerce')
    cutoff_date = datetime.now() - timedelta(days={'D': 1, 'W': 7, 'M': 30}[period[0]])
    filtered_df = df[df['answered_at'] >= cutoff_date]

    if filtered_df.empty:
        return {'total_users': df['user_id'].nunique()}

    # --- A CORREÇÃO ESTÁ AQUI ---
    # Converte a coluna 'is_correct' de string ('TRUE') para inteiro (1/0)
    filtered_df['is_correct'] = (
        filtered_df['is_correct'].astype(str).str.lower() == 'true'
    ).astype(int)

    # Agrupa por usuário para calcular o ranking
    performance = filtered_df.groupby('user_id').agg(
        total_respondidas=('question_id', 'count'),
        total_corretas=('is_correct', 'sum')
    ).reset_index()

    # Calcula a taxa de acerto de forma segura
    performance['taxa_de_acerto'] = 0.0
    mask = performance['total_respondidas'] > 0
    performance.loc[mask, 'taxa_de_acerto'] = \
        (performance.loc[mask, 'total_corretas'] / performance.loc[mask, 'total_respondidas']) * 100

    # Ordena para criar o ranking
    ranked_performance = performance.sort_values(
        by=['taxa_de_acerto', 'total_respondidas'],
        ascending=[False, False]
    ).reset_index(drop=True)
    
    ranked_performance['rank'] = ranked_performance.index + 1

    # Encontra os dados do usuário atual
    user_rank_info = ranked_performance[ranked_performance['user_id'] == current_user_id]

    if user_rank_info.empty:
        return {
            'rank': None,
            'percentile': None,
            'total_users': len(ranked_performance)
        }

    user_rank = user_rank_info.iloc[0]
    total_users = len(ranked_performance)
    percentile = (1 - (user_rank['rank'] / total_users)) * 100 if total_users > 0 else 100

    return {
        'rank': int(user_rank['rank']),
        'percentile': percentile,
        'total_users': total_users
    }

@st.cache_data(ttl=1)
def get_user_answered_questions_details(user_id):
    """ Busca o histórico de um usuário no Supabase com join. """
    try:
        conn = get_supabase_conn()
        # Join otimizado via Supabase
        response = conn.table("answers").select("*, questions(*)").eq("user_id", str(user_id)).order("answered_at", desc=True).execute()
        
        merged_df = pd.json_normalize(response.data, sep='_')
        if merged_df.empty:
            return pd.DataFrame()
        
        merged_df.rename(columns=lambda x: x.replace('questions_', ''), inplace=True)
        merged_df['is_correct'] = merged_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        return merged_df
        
    except Exception as e:
        st.error(f"Erro ao buscar histórico de revisão: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=1)
def get_all_provas():
    """Busca todos os nomes de provas únicos do Supabase, tratando múltiplos formatos."""
    try:
        conn = get_supabase_conn()
        response = conn.table("questions").select("prova").execute()

        if not response.data:
            return []

        df = pd.DataFrame(response.data)

        if df.empty or 'prova' not in df.columns:
            return []

        # Lógica de limpeza e extração de valores únicos
        provas = (
            df['prova']
            .dropna()
            .astype(str)
            .str.replace(r'[\[\]"]', '', regex=True) # Remove caracteres indesejados
            .str.strip()
        )
        
        unique_provas = sorted(list(provas[provas != ''].unique()))
        
        return unique_provas
        
    except Exception as e:
        st.warning("Não foi possível carregar a lista de provas.")
        return []

@st.cache_data(ttl=1)
def get_global_platform_stats():
    """Calcula estatísticas globais usando dados do Supabase."""
    default_stats = {'total_students': 0, 'active_this_week': 0, 'answered_last_7_days': 0, 'accuracy_last_7_days': 0.0}
    try:
        conn = get_supabase_conn()
        # 'count='exact'' é a forma eficiente de contar no Supabase
        users_response = conn.table("users").select("user_id", count='exact').execute()
        answers_response = conn.table("answers").select("user_id, is_correct, answered_at").execute()
        
        total_students = users_response.count
        answers_df = pd.DataFrame(answers_response.data)

        if answers_df.empty:
            default_stats['total_students'] = total_students
            return default_stats
        
        # O resto da lógica é em pandas e permanece igual
        answers_df['answered_at'] = pd.to_datetime(answers_df['answered_at'])
        answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        
        now = datetime.now(answers_df['answered_at'].dt.tz)
        start_of_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
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
    
@st.cache_data(ttl=1)
def get_all_concepts_with_areas():
    """
    Busca todos os conceitos e suas áreas de conhecimento, tratando os formatos.
    (Função criada com base na necessidade)
    """
    try:
        # Supondo que você tenha uma tabela 'concepts'
        conn = get_supabase_conn()
        response = conn.table("concepts").select("concept_title, areas_principais").execute()

        if not response.data:
            return pd.DataFrame()

        df = pd.DataFrame(response.data)
        
        if df.empty or 'areas_principais' not in df.columns:
            return pd.DataFrame()

        # Aplica a limpeza na coluna de áreas
        df['areas_principais'] = df['areas_principais'].astype(str).str.replace(r'[\[\]"]', '', regex=True)
        
        return df

    except Exception as e:
        st.warning("Não foi possível carregar os conceitos e suas áreas.")
        return pd.DataFrame()

@st.cache_data(ttl=1)
def get_subtopics_from_incorrect_answers(user_id: str):
    """
    Busca subtópicos de questões que o usuário errou, tratando os formatos da coluna.
    """
    try:
        conn = get_supabase_conn()
        
        # Busca apenas as respostas incorretas do usuário com os detalhes das questões
        response = conn.table("answers") \
            .select("is_correct, questions(subtopicos)") \
            .eq("user_id", user_id) \
            .eq("is_correct", False) \
            .execute()

        if not response.data:
            return []

        # Extrai e achata os dados dos subtópicos
        subtopics_list = []
        for row in response.data:
            question_data = row.get('questions')
            if question_data and 'subtopicos' in question_data and question_data['subtopicos']:
                # Aplica a limpeza aqui
                subtopicos_str = str(question_data['subtopicos']).replace('[', '').replace(']', '').replace('"', '')
                subtopics_list.extend([s.strip() for s in subtopicos_str.split(',')])

        # Retorna uma lista de subtópicos únicos e não vazios
        unique_subtopics = sorted(list(set(filter(None, subtopics_list))))
        
        return unique_subtopics

    except Exception as e:
        st.warning("Não foi possível carregar os subtópicos para revisão.")
        return []

@st.cache_data(ttl=1)
def get_all_specialties():
    """Busca todas as especialidades únicas do Supabase, tratando múltiplos formatos."""
    try:
        conn = get_supabase_conn()
        # Seleciona apenas a coluna necessária para otimizar a consulta
        response = conn.table("questions").select("areas_principais").execute()

        # Retorna uma lista vazia se a consulta não retornar dados
        if not response.data:
            return []

        df = pd.DataFrame(response.data)

        if df.empty or 'areas_principais' not in df.columns:
            return []
        
        # Lógica de processamento com pandas:
        specialties = (
            df['areas_principais']
            .dropna()
            .astype(str)  # Garante que todos os valores sejam tratados como string
            .str.replace(r'[\[\]"]', '', regex=True)  # Remove colchetes e aspas da string
            .str.split(',')  # Divide as especialidades pela vírgula
            .explode()       # Transforma cada item da lista em uma nova linha
            .str.strip()     # Remove espaços em branco no início e no fim
        )
        
        # Pega os valores únicos, remove strings vazias, converte para lista e ordena
        unique_specialties = sorted(list(specialties[specialties != ''].unique()))
        
        return unique_specialties
        
    except Exception as e:
        st.warning(f"Não foi possível carregar a lista de especialidades.")
        # Para depuração, você pode descomentar a linha abaixo para ver o erro no console
        # print(f"Erro ao buscar especialidades: {e}")
        return []