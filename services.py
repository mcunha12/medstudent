import streamlit as st
import gspread
import pandas as pd
import google.generativeai as genai
import json
import uuid
from datetime import datetime, timedelta
import unicodedata

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

def get_or_create_user(email):
    """Busca um usuário pelo email ou cria um novo se não existir."""
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

    # --- LÓGICA REESCRITA PARA MÚLTIPLOS STATUS ---
    list_of_pools = []
    
    # Pega as respostas do usuário uma única vez
    user_answers_df = pd.DataFrame()
    if not answers_df.empty:
        answers_df['user_id'] = answers_df['user_id'].astype(str)
        user_answers_df = answers_df[answers_df['user_id'] == user_id].copy()

    # Para cada status selecionado, cria um pool de questões correspondente
    if 'nao_respondidas' in status_filters:
        if not user_answers_df.empty:
            answered_ids = user_answers_df['question_id'].unique().tolist()
            pool = questions_df[~questions_df['question_id'].isin(answered_ids)]
        else:
            pool = questions_df.copy() # Todas as questões estão não respondidas
        list_of_pools.append(pool)

    if not user_answers_df.empty and ('corretas' in status_filters or 'incorretas' in status_filters):
        user_answers_df['is_correct'] = user_answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')
        
        if 'corretas' in status_filters:
            correct_ids = user_answers_df[user_answers_df['is_correct'] == True]['question_id'].unique().tolist()
            list_of_pools.append(questions_df[questions_df['question_id'].isin(correct_ids)])
        
        if 'incorretas' in status_filters:
            incorrect_ids = user_answers_df[user_answers_df['is_correct'] == False]['question_id'].unique().tolist()
            list_of_pools.append(questions_df[questions_df['question_id'].isin(incorrect_ids)])

    # Se nenhum pool foi selecionado, não há o que buscar
    if not list_of_pools:
        return None

    # Concatena todos os pools selecionados e remove duplicatas
    initial_pool = pd.concat(list_of_pools).drop_duplicates(subset=['question_id']).reset_index(drop=True)

    if initial_pool.empty:
        return None

    # --- Aplica os outros filtros no pool de questões já selecionado ---
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
    """
    Salva ou atualiza uma resposta, com lógica para não sobrescrever acertos com erros.
    """
    _ensure_connected()
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    all_answers = pd.DataFrame(answers_sheet.get_all_records())

    # Procura por uma resposta existente para esta questão e usuário
    existing_answer = all_answers[
        (all_answers['user_id'] == str(user_id)) & 
        (all_answers['question_id'] == str(question_id))
    ]

    if existing_answer.empty:
        # Se não existe, é uma nova resposta. Adiciona a linha.
        answer_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        new_answer_data = [answer_id, str(user_id), str(question_id), user_answer, 'TRUE' if is_correct else 'FALSE', timestamp]
        answers_sheet.append_row(new_answer_data)
    else:
        # Se já existe, aplica a lógica de atualização
        old_is_correct = str(existing_answer['is_correct'].iloc[0]).upper() == 'TRUE'
        
        # REGRA: Se a resposta antiga era correta e a nova é errada, não faz nada.
        if old_is_correct and not is_correct:
            print(f"INFO: Resposta para a questão {question_id} já era correta. Nenhuma alteração feita.")
            return

        # Para todos os outros casos (errada->certa, errada->errada, certa->certa), atualiza.
        # Encontra a linha na planilha para atualizar
        try:
            cell = answers_sheet.find(existing_answer['answer_id'].iloc[0])
            row_index = cell.row
            
            # Monta a linha com os dados atualizados
            updated_row = [
                existing_answer['answer_id'].iloc[0],
                str(user_id),
                str(question_id),
                user_answer,
                'TRUE' if is_correct else 'FALSE',
                datetime.now().isoformat()
            ]
            # Atualiza a linha específica
            answers_sheet.update(f'A{row_index}:F{row_index}', [updated_row])
        except Exception as e:
            print(f"ERRO: Não foi possível encontrar ou atualizar a linha da resposta. Erro: {e}")
            
    st.cache_data.clear() # Limpa o cache para refletir a mudança

def generate_question_with_gemini():
    """Gera uma nova questão usando a API do Gemini."""
    model = get_gemini_model()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    prompt = """
    Crie uma nova questão de múltipla escolha para a prova de residência médica (ENAMED) no Brasil...
    """
    # ... (lógica de geração e salvamento da questão)
    pass

# Adicione esta função ao seu services.py. Ela pode ir antes de get_performance_data.
@st.cache_data(ttl=3600) # Cache por 1 hora para não ler a planilha toda vez
def get_all_specialties():
    """
    Busca todas as áreas principais (especialidades) únicas da planilha de questões.
    """
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    
    # Retorna uma lista vazia se a coluna não existir ou o DF estiver vazio
    if 'areas_principais' not in questions_df.columns or questions_df.empty:
        return []
    
    # Pega a coluna, trata valores nulos, separa por vírgula, e "explode" para ter uma área por linha
    specialties = questions_df['areas_principais'].dropna().str.split(',').explode()
    
    # Remove espaços em branco, pega valores únicos, converte para lista e ordena
    unique_specialties = sorted(list(specialties.str.strip().unique()))
    
    return unique_specialties


# Modifique a função get_next_question para aceitar o filtro de especialidade
def get_next_question(user_id, specialty=None): # Adicionado o parâmetro 'specialty'
    """Busca a próxima questão não respondida, com um filtro opcional de especialidade."""
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    answers_df = pd.DataFrame(answers_sheet.get_all_records())
    
    if questions_df.empty: return None

    # --- NOVO BLOCO DE FILTRO POR ESPECIALIDADE ---
    if specialty and specialty != "Todas":
        # Filtra o DataFrame para questões que contenham a string da especialidade
        # na=False ignora NaNs, case=False torna a busca case-insensitive
        questions_df = questions_df[questions_df['areas_principais'].str.contains(specialty, na=False, case=False)]
        
        # Se o filtro não retornar nenhuma questão, encerra a busca
        if questions_df.empty:
            return None
    # --- FIM DO NOVO BLOCO ---

    if not answers_df.empty:
        answers_df['user_id'] = answers_df['user_id'].astype(str)
        answered_questions_ids = answers_df[answers_df['user_id'] == user_id]['question_id'].tolist()
        unanswered_questions_df = questions_df[~questions_df['question_id'].isin(answered_questions_ids)]
    else:
        unanswered_questions_df = questions_df
        
    return unanswered_questions_df.sample(n=1).to_dict('records')[0] if not unanswered_questions_df.empty else None


@st.cache_data(ttl=600)
def get_performance_data(user_id):
    """
    Busca todos os dados de performance.

    Retorna um dicionário contendo:
    - Dados de performance do usuário logado (merged_df, areas_exploded, etc.)
    - Um DataFrame com TODAS as respostas de TODOS os usuários para o ranking.
    """
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    answers_sheet = _connections["spreadsheet"].worksheet("answers")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    answers_df = pd.DataFrame(answers_sheet.get_all_records())

    if answers_df.empty or questions_df.empty: return None
    
    # MODIFICAÇÃO: Converte 'is_correct' para booleano em todo o DataFrame de uma vez
    answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')

    # MODIFICAÇÃO: Guarda o DF completo para o ranking antes de filtrar
    all_answers_for_ranking = answers_df.copy()

    user_answers_df = answers_df[answers_df['user_id'].astype(str) == str(user_id)].copy()
    if user_answers_df.empty: return None

    user_answers_df['answered_at'] = pd.to_datetime(user_answers_df['answered_at'])
    
    merged_df = pd.merge(user_answers_df, questions_df, on='question_id', how='left')
    merged_df['areas_principais'] = merged_df['areas_principais'].fillna('').str.split(',')
    merged_df['subtopicos'] = merged_df['subtopicos'].fillna('').str.split(',')
    
    areas_df = merged_df.explode('areas_principais')
    areas_df['areas_principais'] = areas_df['areas_principais'].str.strip()
    
    subtopicos_df = merged_df.explode('subtopicos')
    subtopicos_df['subtopicos'] = subtopicos_df['subtopicos'].str.strip()
    
    # MODIFICAÇÃO: Adiciona o DF de ranking ao retorno
    return {
        "all_answers": merged_df, 
        "areas_exploded": areas_df, 
        "subtopicos_exploded": subtopicos_df,
        "all_answers_for_ranking": all_answers_for_ranking
    }

def calculate_metrics(df):
    """Calcula métricas básicas de um DataFrame de respostas."""
    if df is None or df.empty: return {"answered": 0, "correct": 0, "accuracy": 0.0}
    answered = len(df)
    correct = df['is_correct'].sum()
    accuracy = (correct / answered * 100) if answered > 0 else 0.0
    return {"answered": answered, "correct": correct, "accuracy": accuracy}

def get_time_window_metrics(all_answers_df, days=None):
    """Calcula métricas para uma janela de tempo específica."""
    if all_answers_df is None: return calculate_metrics(None)
    if days is None: return calculate_metrics(all_answers_df)
    
    # Garante que a data de corte tenha o mesmo fuso horário (ou falta de) que os dados
    if all_answers_df['answered_at'].dt.tz:
        cutoff_date = datetime.now(all_answers_df['answered_at'].dt.tz) - timedelta(days=days)
    else:
        cutoff_date = datetime.now() - timedelta(days=days)

    window_df = all_answers_df[all_answers_df['answered_at'] >= cutoff_date]
    return calculate_metrics(window_df)

def get_temporal_performance(all_answers_df, period='W'):
    """Agrega a performance por período (Semana 'W' ou Dia 'D')."""
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
    """Calcula a performance por área principal."""
    if areas_exploded_df is None or areas_exploded_df.empty: return pd.DataFrame()
    areas_summary = areas_exploded_df.groupby('areas_principais').agg(
        total_respondidas=('question_id', 'count'), 
        total_acertos=('is_correct', 'sum')
    ).reset_index()
    areas_summary['taxa_de_acerto'] = (areas_summary['total_acertos'] / areas_summary['total_respondidas'] * 100).fillna(0)
    return areas_summary

def get_subtopics_for_review(subtopicos_exploded_df, days=7):
    """Identifica os subtópicos com mais erros nos últimos dias."""
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


# --- FUNÇÃO NOVA ADICIONADA ---
def get_ranking_data(all_answers_df, period_code, current_user_id):
    """
    Calcula o ranking de performance de um usuário em relação a todos os outros.
    """
    if all_answers_df.empty:
        return None

    df = all_answers_df.copy()
    df['answered_at'] = pd.to_datetime(df['answered_at'])
    now = datetime.now(df['answered_at'].dt.tz) # Garante fuso horário consistente

    if period_code == 'D': # Hoje
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period_code == 'W': # Esta semana (Segunda como início)
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        return None
        
    recent_answers = df[df['answered_at'] >= start_date]

    if recent_answers.empty:
        return None

    performance = recent_answers.groupby('user_id').agg(
        total_corretas=('is_correct', 'sum'),
        total_respondidas=('is_correct', 'count')
    ).reset_index()
    
    performance['taxa_de_acerto'] = (performance['total_corretas'] / performance['total_respondidas']) * 100
    
    ranked_users = performance.sort_values(
        by=['taxa_de_acerto', 'total_respondidas'],
        ascending=[False, False]
    ).reset_index(drop=True)

    ranked_users['rank'] = ranked_users.index + 1

    user_rank_info = ranked_users[ranked_users['user_id'].astype(str) == str(current_user_id)]

    if user_rank_info.empty:
        return {'rank': None, 'total_users': len(ranked_users), 'percentile': None}

    user_rank = int(user_rank_info['rank'].iloc[0])
    total_users = len(ranked_users)
    percentile = (user_rank / total_users) * 100

    return {
        'rank': user_rank,
        'total_users': total_users,
        'percentile': percentile
    }

# Adicione esta função ao final do seu arquivo services.py
@st.cache_data(ttl=600) # Cache de 10 minutos para os dados de revisão
def get_user_answered_questions_details(user_id):
    """
    Busca todas as respostas de um usuário e as combina com os detalhes das questões.
    
    Returns:
        pd.DataFrame: Um DataFrame com os dados combinados e ordenado do mais recente para o mais antigo.
                      Retorna um DataFrame vazio se não houver respostas.
    """
    _ensure_connected() # Garante que a conexão com o Google Sheets está ativa
    try:
        answers_sheet = _connections["spreadsheet"].worksheet("answers")
        questions_sheet = _connections["spreadsheet"].worksheet("questions")
        
        answers_df = pd.DataFrame(answers_sheet.get_all_records())
        questions_df = pd.DataFrame(questions_sheet.get_all_records())

        if answers_df.empty or questions_df.empty:
            return pd.DataFrame()

        # Filtra apenas as respostas do usuário logado
        user_answers = answers_df[answers_df['user_id'].astype(str) == str(user_id)].copy()

        if user_answers.empty:
            return pd.DataFrame()

        # Converte tipos para garantir consistência
        user_answers['answered_at'] = pd.to_datetime(user_answers['answered_at'])
        user_answers['is_correct'] = user_answers['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')

        # Combina os dados das respostas com os detalhes das questões
        merged_df = pd.merge(user_answers, questions_df, on='question_id', how='left')

        # Ordena da resposta mais recente para a mais antiga
        merged_df = merged_df.sort_values(by='answered_at', ascending=False)
        
        return merged_df
    except Exception as e:
        st.error(f"Erro ao buscar histórico de revisão: {e}")
        return pd.DataFrame()
    
@st.cache_data(ttl=3600) # Cache por 1 hora
def get_all_provas():
    """Busca todas as provas únicas da planilha de questões."""
    _ensure_connected()
    questions_sheet = _connections["spreadsheet"].worksheet("questions")
    questions_df = pd.DataFrame(questions_sheet.get_all_records())
    
    if 'prova' not in questions_df.columns or questions_df.empty:
        return []
    
    unique_provas = sorted(list(questions_df['prova'].dropna().unique()))
    return unique_provas

@st.cache_data(ttl=3600) # Armazena o resultado em cache por 1 hora
def get_global_platform_stats():
    """
    Calcula as estatísticas globais da plataforma para exibir na Home.
    """
    _ensure_connected()
    try:
        users_sheet = _connections["spreadsheet"].worksheet("users")
        answers_sheet = _connections["spreadsheet"].worksheet("answers")

        users_df = pd.DataFrame(users_sheet.get_all_records())
        answers_df = pd.DataFrame(answers_sheet.get_all_records())

        # Métrica 1: Total de alunos
        total_students = len(users_df) if not users_df.empty else 0

        # Se não houver respostas, retorna os valores padrão
        if answers_df.empty:
            return {
                'total_students': total_students,
                'active_this_week': 0,
                'answered_last_7_days': 0,
                'accuracy_last_7_days': 0.0
            }

        answers_df['answered_at'] = pd.to_datetime(answers_df['answered_at'])
        answers_df['is_correct'] = answers_df['is_correct'].apply(lambda x: str(x).upper() == 'TRUE')

        # Garante que 'now' tenha o mesmo fuso horário dos dados
        now = datetime.now(answers_df['answered_at'].dt.tz)

        # Métrica 2: Alunos ativos na semana corrente (de Segunda a Domingo)
        start_of_week = now - timedelta(days=now.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        this_week_answers = answers_df[answers_df['answered_at'] >= start_of_week]
        active_this_week = this_week_answers['user_id'].nunique()

        # Métricas 3 e 4: Respostas e acertos nos últimos 7 dias
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
        return {'total_students': 0, 'active_this_week': 0, 'answered_last_7_days': 0, 'accuracy_last_7_days': 0.0}
