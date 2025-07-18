import streamlit as st
import json
from services import get_simulado_questions, save_answer, get_all_specialties, get_all_provas, normalize_for_search

# --- Funções Auxiliares da Página ---

def reset_simulado_state():
    """Função auxiliar para limpar o estado do simulado e voltar à tela de configuração."""
    st.session_state.simulado_stage = 'config'
    for key in ['simulado_questions', 'simulado_answers', 'current_question_index', 'answer_submitted']:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

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
        
        save_answer(st.session_state.user_id, question_data['question_id'], selected_answer, is_correct)
        
        st.session_state.simulado_answers.append({
            'question_id': question_data['question_id'],
            'user_answer': selected_answer,
            'is_correct': is_correct
        })
        
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
    
    # Botão para reiniciar na página de resultados
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

# --- RENDERIZAÇÃO CONDICIONAL ---

if st.session_state.simulado_stage == 'config':
    st.title("📝 Simulador de Provas")
    st.markdown("Selecione os filtros abaixo e clique em 'Gerar Simulado' para começar a praticar.")

    with st.container(border=True):
        # ... (código dos filtros permanece igual)
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
        st.info("O simulado será gerado com **20 questões** selecionadas aleatoriamente com base nos seus filtros.")
        
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
                        user_id=st.session_state.user_id, count=20,
                        status_filters=selected_status_values, specialty=selected_specialty,
                        provas=selected_provas, keywords=st.session_state.keywords
                    )
                if questions and len(questions) > 0:
                    st.session_state.simulado_questions = questions
                    st.session_state.simulado_answers = []
                    st.session_state.current_question_index = 0
                    st.session_state.simulado_stage = 'in_progress'
                    st.rerun()
                else:
                    st.error("Nenhuma questão encontrada com os filtros selecionados. Tente usar filtros menos restritivos.")

elif st.session_state.simulado_stage == 'in_progress':
    total_questions = len(st.session_state.simulado_questions)
    current_index = st.session_state.current_question_index
    current_question_data = st.session_state.simulado_questions[current_index]

    st.title(f"Questão {current_index + 1} de {total_questions}")
    
    # --- NOVO BOTÃO PARA REINICIAR ---
    if st.button("✖️ Cancelar e Gerar Novo Simulado", type="secondary"):
        reset_simulado_state()
    
    st.progress((current_index + 1) / total_questions)
    st.markdown("---")

    if st.session_state.answer_submitted:
        render_feedback(current_question_data)
    else:
        render_question(current_question_data)

elif st.session_state.simulado_stage == 'results':
    render_results()