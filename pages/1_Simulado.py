# Arquivo: simulado.py (versão completa e atualizada)

import streamlit as st
import json
import pandas as pd
import math
# Importe as novas funções de serviço necessárias
from services import (
    get_simulado_questions, 
    save_answer, 
    get_all_specialties, 
    get_all_provas, 
    normalize_for_search,
    _generate_ai_question_based_on_seed,  # <-- Importar
    _save_new_question                    # <-- Importar
)

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Simulado - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- Funções Auxiliares da Página ---
def reset_simulado_state():
    """Limpa o estado do simulado para voltar à tela de configuração."""
    st.session_state.simulado_stage = 'config'
    # Limpa todas as chaves relacionadas ao simulado
    keys_to_clear = [
        'db_questions', 'ai_questions_generated', 'seed_pool', 
        'simulado_answers', 'current_question_index', 'answer_submitted',
        'num_db_questions', 'total_questions_target'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def render_question(question_data):
    """Renderiza a interface de uma única questão."""
    st.write(question_data.get('enunciado', ''))
    
    alternativas_str = question_data.get('alternativas')
    alternativas = json.loads(alternativas_str) if alternativas_str and isinstance(alternativas_str, str) and alternativas_str.strip() else {}
    
    selected_answer = None
    for key, value in alternativas.items():
        if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True):
            selected_answer = key
    
    if selected_answer:
        is_correct = (selected_answer == question_data['alternativa_correta'])
        
        save_answer(st.session_state.user_id, question_data['question_id'], selected_answer, is_correct)
        
        st.session_state.simulado_answers.append({
            'question_id': question_data['question_id'],
            'user_answer': selected_answer,
            'is_correct': is_correct
        })
        
        st.session_state.answer_submitted = True
        st.rerun()

def render_feedback(question_data):
    """Renderiza o feedback após uma resposta."""
    comentarios_str = question_data.get('comentarios')
    comentarios = json.loads(comentarios_str) if comentarios_str and isinstance(comentarios_str, str) and comentarios_str.strip() else {}
    user_answer = st.session_state.simulado_answers[-1]['user_answer']
    
    st.subheader("Comentários das Alternativas")
    for key, comment in comentarios.items():
        if key == question_data['alternativa_correta']:
            st.success(f"**{key} (Correta):** {comment}")
        elif key == user_answer:
            st.error(f"**{key} (Sua Resposta):** {comment}")
        else:
            st.info(f"**{key}:** {comment}")

    current_total_questions = st.session_state.num_db_questions + len(st.session_state.ai_questions_generated)
    is_last_question = (st.session_state.current_question_index == st.session_state.total_questions_target - 1) or \
                       (st.session_state.current_question_index == current_total_questions - 1 and current_total_questions < st.session_state.total_questions_target)

    button_text = "Ver Resultado Final" if is_last_question else "Próxima Questão"
    
    if st.button(button_text, type="primary", use_container_width=True):
        st.session_state.answer_submitted = False
        if is_last_question:
            st.session_state.simulado_stage = 'results'
        else:
            # --- NOVA LÓGICA DE GERAÇÃO "JUST-IN-TIME" ---
            st.session_state.current_question_index += 1
            next_index = st.session_state.current_question_index
            num_db = st.session_state.num_db_questions
            num_generated = len(st.session_state.ai_questions_generated)
            
            # Precisamos gerar uma nova questão?
            if next_index >= num_db and (num_db + num_generated) < st.session_state.total_questions_target:
                with st.spinner("Preparando a próxima questão com IA..."):
                    seed_pool = st.session_state.seed_pool
                    if not seed_pool.empty:
                        seed_question = seed_pool.sample(n=1).iloc[0].to_dict()
                        new_question = _generate_ai_question_based_on_seed(seed_question)
                        
                        if new_question and _save_new_question(new_question):
                            st.session_state.ai_questions_generated.append(new_question)
                            st.toast("Questão gerada pela IA!", icon="✨")
                        else:
                            st.error("Falha ao gerar a próxima questão. Finalizando o simulado.")
                            st.session_state.simulado_stage = 'results' # Termina o simulado se a IA falhar
        st.rerun()

def render_results():
    """Renderiza a página de resultados do simulado."""
    st.balloons()
    st.title("Resultado do Simulado")

    # Combina as questões do DB e da IA para a revisão
    all_questions_in_simulado = st.session_state.db_questions + st.session_state.ai_questions_generated

    total_questions_answered = len(st.session_state.simulado_answers)
    correct_answers = sum(1 for ans in st.session_state.simulado_answers if ans['is_correct'])
    accuracy = (correct_answers / total_questions_answered * 100) if total_questions_answered > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Questões Respondidas", f"{total_questions_answered}")
    col2.metric("Acertos", f"{correct_answers}")
    col3.metric("Taxa de Acerto", f"{accuracy:.1f}%")

    st.markdown("---")
    st.subheader("Revisão das Questões do Simulado")

    answers_map = {ans['question_id']: ans for ans in st.session_state.simulado_answers}

    for question in all_questions_in_simulado:
        q_id = question['question_id']
        user_answer_data = answers_map.get(q_id)

        if user_answer_data:
            icon = '✅' if user_answer_data['is_correct'] else '❌'
            expander_title = f"{icon} **{question.get('prova', 'N/A')}** | {question.get('enunciado', '')[:80]}..."

            with st.expander(expander_title):
                st.markdown(f"**Prova:** {question.get('prova', 'N/A')} | **Áreas:** {question.get('areas_principais', 'N/A')}")
                st.markdown("---")
                st.write(question.get('enunciado', ''))
                
                alternativas_str = question.get('alternativas')
                alternativas = json.loads(alternativas_str) if alternativas_str and isinstance(alternativas_str, str) and alternativas_str.strip() else {}
                comentarios_str = question.get('comentarios')
                comentarios = json.loads(comentarios_str) if comentarios_str and isinstance(comentarios_str, str) and comentarios_str.strip() else {}
                
                for key, value in alternativas.items():
                    full_text = f"**{key}:** {value}"
                    if key == question['alternativa_correta']:
                        st.success(f"**{full_text} (Correta)**")
                    elif key == user_answer_data['user_answer']:
                        st.error(f"**{full_text} (Sua Resposta)**")
                    else:
                        st.info(f"{full_text}")
                    st.caption(f"Comentário: {comentarios.get(key, 'Sem comentário.')}")
    
    if st.button("Fazer Novo Simulado", use_container_width=True):
        reset_simulado_state()

# --- LÓGICA PRINCIPAL DA PÁGINA ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar o simulado.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

if 'simulado_stage' not in st.session_state:
    st.session_state.simulado_stage = 'config'
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'keywords' not in st.session_state:
    st.session_state.keywords = []

# --- Estágio de Configuração ---
if st.session_state.simulado_stage == 'config':
    st.title("📝 Simulador de Provas")
    st.markdown("Selecione os filtros abaixo e clique em 'Gerar Simulado' para começar a praticar.")
    with st.container(border=True):
        # ... (O código dos filtros permanece o mesmo) ...
        st.subheader("Filtros do Simulado")
        st.markdown("**Buscar em:**")
        filter_cols = st.columns(3)
        with filter_cols[0]: status_nao_respondidas = st.checkbox("Questões não respondidas", value=True)
        with filter_cols[1]: status_corretas = st.checkbox("Questões que acertei")
        with filter_cols[2]: status_incorretas = st.checkbox("Questões que errei")
        col1, col2 = st.columns(2)
        with col1: selected_specialty = st.selectbox("Área Principal:", ["Todas"] + get_all_specialties())
        with col2: selected_provas = st.multiselect("Prova(s):", get_all_provas())
        def add_keyword():
            keyword_input = st.session_state.get("keyword_input", "")
            if keyword_input and keyword_input.strip():
                keyword_set = set(st.session_state.keywords)
                keyword_set.add(keyword_input.strip().lower())
                st.session_state.keywords = list(keyword_set)
            st.session_state.keyword_input = ""
        st.text_input("Buscar por palavras-chave:", placeholder="Digite uma palavra e pressione Enter...", on_change=add_keyword, key="keyword_input")
        if st.session_state.keywords:
            st.caption("Palavras-chave ativas (clique para remover):")
            cols_per_row = 7 
            for i in range(0, len(st.session_state.keywords), cols_per_row):
                cols = st.columns(cols_per_row)
                chunk = st.session_state.keywords[i:i + cols_per_row]
                for j, keyword in enumerate(chunk):
                    with cols[j]:
                        if st.button(f"❌ {keyword}", key=f"kw_{keyword}", use_container_width=True):
                            st.session_state.keywords.remove(keyword)
                            st.rerun()
            st.markdown("""<hr style="height:1px;border:none;color:#333;background-color:#333;" /> """, unsafe_allow_html=True)
            if st.button("Limpar todas as palavras-chave"):
                st.session_state.keywords = []
                st.rerun()
        st.markdown("---")
        
        TOTAL_QUESTOES_SIMULADO = 20
        st.info(f"O simulado buscará questões existentes e, se necessário, gerará novas com IA até atingir **{TOTAL_QUESTOES_SIMULADO} questões**.")
        
        if st.button("Gerar Simulado", type="primary", use_container_width=True):
            selected_status_values = []
            if status_nao_respondidas: selected_status_values.append("nao_respondidas")
            if status_corretas: selected_status_values.append("corretas")
            if status_incorretas: selected_status_values.append("incorretas")
            
            if not selected_status_values:
                st.warning("Por favor, selecione pelo menos um status de questão para buscar.")
            else:
                with st.spinner("Buscando questões no banco de dados..."):
                    response = get_simulado_questions(
                        user_id=st.session_state.user_id, status_filters=selected_status_values,
                        specialty=selected_specialty, provas=selected_provas, keywords=st.session_state.keywords
                    )
                
                if response and response['found_questions']:
                    # Configura o estado para o início do simulado
                    st.session_state.db_questions = response['found_questions']
                    st.session_state.seed_pool = response['seed_pool']
                    st.session_state.ai_questions_generated = []
                    st.session_state.simulado_answers = []
                    st.session_state.current_question_index = 0
                    st.session_state.num_db_questions = len(response['found_questions'])
                    st.session_state.total_questions_target = TOTAL_QUESTOES_SIMULADO
                    st.session_state.simulado_stage = 'in_progress'
                    st.rerun()
                else:
                    st.error("Nenhuma questão encontrada com os filtros selecionados. Tente usar filtros menos restritivos.")

# --- Estágio "Em Progresso" ---
elif st.session_state.simulado_stage == 'in_progress':
    all_available_questions = st.session_state.db_questions + st.session_state.ai_questions_generated
    current_index = st.session_state.current_question_index
    
    if current_index >= len(all_available_questions):
         st.session_state.simulado_stage = 'results'
         st.rerun()

    current_question_data = all_available_questions[current_index]
    total_target = st.session_state.total_questions_target
    
    st.title(f"Questão {current_index + 1} de {total_target}")
    if st.button("✖️ Cancelar e Gerar Novo Simulado", type="secondary"):
        reset_simulado_state()
    
    st.progress((current_index + 1) / total_target)
    st.markdown("---")
    
    if st.session_state.answer_submitted:
        render_feedback(current_question_data)
    else:
        render_question(current_question_data)

# --- Estágio de Resultados ---
elif st.session_state.simulado_stage == 'results':
    render_results()