# Conteúdo para o novo arquivo: pages/2_Simulado.py
import streamlit as st
import json
from services import get_simulado_questions, save_answer, get_all_specialties, get_all_provas, normalize_for_search

# --- Funções Auxiliares da Página ---
def render_question(question_data):
    """Renderiza a interface de uma única questão."""
    st.write(question_data.get('enunciado', ''))
    
    alternativas = json.loads(question_data.get('alternativas', '{}'))
    
    selected_answer = None
    for key, value in alternativas.items():
        if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True):
            selected_answer = key
    
    if selected_answer:
        is_correct = (selected_answer == question_data['alternativa_correta'])
        
        # Salva a resposta no backend
        save_answer(st.session_state.user_id, question_data['question_id'], selected_answer, is_correct)
        
        # Armazena a resposta da sessão atual para o relatório final
        st.session_state.simulado_answers.append({
            'question_id': question_data['question_id'],
            'user_answer': selected_answer,
            'is_correct': is_correct
        })
        
        # Marca que a resposta foi enviada para mostrar o feedback
        st.session_state.answer_submitted = True
        st.rerun()

def render_feedback(question_data):
    """Renderiza o feedback (comentários) após uma resposta."""
    comentarios = json.loads(question_data.get('comentarios', '{}'))
    user_answer = st.session_state.simulado_answers[-1]['user_answer']
    
    st.subheader("Comentários das Alternativas")
    for key, comment in comentarios.items():
        if key == question_data['alternativa_correta']:
            st.success(f"**{key} (Correta):** {comment}")
        elif key == user_answer:
            st.error(f"**{key} (Sua Resposta):** {comment}")
        else:
            st.info(f"**{key}:** {comment}")

    # Botão para avançar
    is_last_question = (st.session_state.current_question_index == len(st.session_state.simulado_questions) - 1)
    button_text = "Ver Resultado Final" if is_last_question else "Próxima Questão"
    
    if st.button(button_text, type="primary", use_container_width=True):
        st.session_state.answer_submitted = False
        if is_last_question:
            st.session_state.simulado_stage = 'results'
        else:
            st.session_state.current_question_index += 1
        st.rerun()

def render_results():
    """Renderiza a página de resultados do simulado."""
    st.balloons()
    st.title("Resultado do Simulado")

    total_questions = len(st.session_state.simulado_answers)
    correct_answers = sum(1 for ans in st.session_state.simulado_answers if ans['is_correct'])
    accuracy = (correct_answers / total_questions * 100) if total_questions > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Questões Respondidas", f"{total_questions}")
    col2.metric("Acertos", f"{correct_answers}")
    col3.metric("Taxa de Acerto", f"{accuracy:.1f}%")

    st.markdown("---")
    st.subheader("Revisão das Questões do Simulado")

    # Mapeia as respostas do usuário para fácil acesso
    answers_map = {ans['question_id']: ans for ans in st.session_state.simulado_answers}

    for question in st.session_state.simulado_questions:
        q_id = question['question_id']
        user_answer_data = answers_map.get(q_id)

        if user_answer_data:
            icon = '✅' if user_answer_data['is_correct'] else '❌'
            expander_title = f"{icon} **{question.get('prova', 'N/A')}** | {question.get('enunciado', '')[:80]}..."

            with st.expander(expander_title):
                st.markdown(f"**Prova:** {question.get('prova', 'N/A')} | **Áreas:** {question.get('areas_principais', 'N/A')}")
                st.markdown("---")
                st.write(question.get('enunciado', ''))
                
                alternativas = json.loads(question.get('alternativas', '{}'))
                comentarios = json.loads(question.get('comentarios', '{}'))
                
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
        # Limpa o estado do simulado para começar de novo
        st.session_state.simulado_stage = 'config'
        del st.session_state.simulado_questions
        del st.session_state.simulado_answers
        del st.session_state.current_question_index
        del st.session_state.answer_submitted
        st.rerun()

# --- LÓGICA PRINCIPAL DA PÁGINA ---

# 1. Verificação de Login
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar o simulado.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# 2. Inicialização do Estado da Página
if 'simulado_stage' not in st.session_state:
    st.session_state.simulado_stage = 'config' # 'config', 'in_progress', 'results'
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'keywords' not in st.session_state:
    st.session_state.keywords = []


# --- RENDERIZAÇÃO CONDICIONAL BASEADA NO ESTÁGIO DO SIMULADO ---

# ESTÁGIO 1: CONFIGURAÇÃO DOS FILTROS
if st.session_state.simulado_stage == 'config':
    st.title("📝 Simulador de Provas")
    st.markdown("Selecione os filtros abaixo e clique em 'Gerar Simulado' para começar a praticar.")

    with st.container(border=True):
        st.subheader("Filtros do Simulado")
        # (A lógica de filtros é a mesma de antes)
        st.markdown("**Buscar em:**")
        filter_cols = st.columns(3)
        with filter_cols[0]: status_nao_respondidas = st.checkbox("Questões não respondidas", value=True)
        with filter_cols[1]: status_corretas = st.checkbox("Questões que acertei")
        with filter_cols[2]: status_incorretas = st.checkbox("Questões que errei")
        
        col1, col2 = st.columns(2)
        with col1: selected_specialty = st.selectbox("Área Principal:", ["Todas"] + get_all_specialties())
        with col2: selected_provas = st.multiselect("Prova(s):", get_all_provas())

        # ... (lógica de keywords omitida para simplicidade, mas pode ser adicionada aqui)
        
        num_questions = st.number_input("Número de questões para o simulado:", min_value=5, max_value=50, value=20, step=5)

        if st.button("Gerar Simulado", type="primary", use_container_width=True):
            selected_status_values = []
            if status_nao_respondidas: selected_status_values.append("nao_respondidas")
            if status_corretas: selected_status_values.append("corretas")
            if status_incorretas: selected_status_values.append("incorretas")

            if not selected_status_values:
                st.warning("Por favor, selecione pelo menos um status de questão para buscar.")
            else:
                with st.spinner("Preparando seu simulado..."):
                    questions = get_simulado_questions(
                        user_id=st.session_state.user_id,
                        count=num_questions,
                        status_filters=selected_status_values,
                        specialty=selected_specialty,
                        provas=selected_provas
                    )
                
                if questions:
                    st.session_state.simulado_questions = questions
                    st.session_state.simulado_answers = []
                    st.session_state.current_question_index = 0
                    st.session_state.simulado_stage = 'in_progress'
                    st.rerun()
                else:
                    st.error("Nenhuma questão encontrada com os filtros selecionados. Tente usar filtros menos restritivos.")

# ESTÁGIO 2: SIMULADO EM ANDAMENTO
elif st.session_state.simulado_stage == 'in_progress':
    total_questions = len(st.session_state.simulado_questions)
    current_index = st.session_state.current_question_index
    current_question_data = st.session_state.simulado_questions[current_index]

    st.title(f"Questão {current_index + 1} de {total_questions}")
    st.progress((current_index + 1) / total_questions)
    st.markdown("---")

    if st.session_state.answer_submitted:
        render_feedback(current_question_data)
    else:
        render_question(current_question_data)

# ESTÁGIO 3: RESULTADOS
elif st.session_state.simulado_stage == 'results':
    render_results()