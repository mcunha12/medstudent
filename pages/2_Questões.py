import streamlit as st
import json
from services import get_next_question, save_answer, get_all_specialties, get_all_provas, normalize_for_search

# --- VERIFICA LOGIN ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar o simulado.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'keywords' not in st.session_state:
    st.session_state.keywords = []

user_id = st.session_state.user_id

# =================================================================
# CABEÇALHO DE FILTROS PERSISTENTE
# =================================================================
with st.container(border=True):
    st.subheader("Filtros do Simulado")

    # ALTERADO: Filtro de Status agora permite múltiplas seleções
    status_options = {
        "Questões não respondidas": "nao_respondidas",
        "Questões que acertei": "corretas",
        "Questões que errei": "incorretas"
    }
    selected_status_labels = st.multiselect(
        "Buscar em:",
        options=list(status_options.keys()),
        default=["Questões não respondidas"] # Mantém um padrão amigável
    )
    # Converte os rótulos selecionados para os valores que a função espera
    selected_status_values = [status_options[label] for label in selected_status_labels]
    
    col1, col2 = st.columns(2)
    with col1:
        specialties = ["Todas"] + get_all_specialties()
        selected_specialty = st.selectbox("Área Principal:", specialties)
    with col2:
        provas = get_all_provas()
        selected_provas = st.multiselect("Prova(s):", provas)

    def add_keyword():
        keyword_input = st.session_state.get("keyword_input", "")
        if keyword_input:
            normalized_keyword = normalize_for_search(keyword_input)
            if normalized_keyword not in st.session_state.keywords:
                st.session_state.keywords.append(normalized_keyword)
        st.session_state.keyword_input = ""

    st.text_input("Buscar por palavras-chave:", placeholder="Digite uma palavra e pressione Enter...", on_change=add_keyword, key="keyword_input")

    if st.session_state.keywords:
        active_keywords_str = " | ".join([f"'{kw}'" for kw in st.session_state.keywords])
        st.caption(f"Palavras-chave ativas: {active_keywords_str}")
        if st.button("Limpar palavras-chave"):
            st.session_state.keywords = []
            st.rerun()
    
    if st.button("Gerar Nova Questão", type="primary", use_container_width=True):
        # Validação para garantir que pelo menos um status foi selecionado
        if not selected_status_values:
            st.warning("Por favor, selecione pelo menos um status de questão para buscar.")
        else:
            with st.spinner("Buscando uma questão com os filtros selecionados..."):
                st.session_state.current_question = get_next_question(
                    user_id,
                    status_filters=selected_status_values, # Passa a LISTA de filtros
                    specialty=selected_specialty,
                    provas=selected_provas,
                    keywords=st.session_state.keywords
                )
                st.session_state.answer_submitted = False
                st.session_state.feedback_answer = None
                st.rerun()

# =================================================================
# ÁREA DE EXIBIÇÃO DA QUESTÃO
# (Nenhuma mudança necessária aqui)
# =================================================================
st.markdown("---")
q = st.session_state.current_question

if q:
    st.markdown(f"**Prova:** {q.get('prova', 'N/A')} | **Áreas:** {q.get('areas_principais', 'N/A')}")
    st.write(q.get('enunciado', ''))
    
    alternativas = json.loads(q.get('alternativas', '{}'))
    
    if not st.session_state.answer_submitted:
        selected_answer = None
        for key, value in alternativas.items():
            if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True):
                selected_answer = key
        
        if selected_answer:
            st.session_state.answer_submitted = True
            is_correct = (selected_answer == q['alternativa_correta'])
            save_answer(user_id, q['question_id'], selected_answer, is_correct)
            st.session_state.feedback_answer = selected_answer
            st.rerun()

    if st.session_state.answer_submitted:
        comentarios = json.loads(q.get('comentarios', '{}'))
        st.subheader("Comentários das Alternativas")
        for key, comment in comentarios.items():
            if key == q['alternativa_correta']:
                st.success(f"**{key} (Correta):** {comment}")
            elif key == st.session_state.get('feedback_answer'):
                st.error(f"**{key} (Sua Resposta):** {comment}")
            else:
                st.info(f"**{key}:** {comment}")
else:
    st.info("Use os filtros acima e clique em **'Gerar Nova Questão'** para começar seu simulado.")
    st.warning("Se nenhuma questão for encontrada, tente remover ou alterar alguns filtros.")