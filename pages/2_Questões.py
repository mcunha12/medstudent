import streamlit as st
import json
from services import get_next_question, save_answer, get_all_specialties, get_all_provas

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
    
    col1, col2 = st.columns(2)
    with col1:
        # Filtro de Especialidade
        specialties = ["Todas"] + get_all_specialties()
        selected_specialty = st.selectbox("Área Principal:", specialties)

    with col2:
        # Filtro de Prova
        provas = get_all_provas()
        selected_provas = st.multiselect("Prova(s):", provas)

    # --- Filtro de Palavras-chave ---
    def add_keyword():
        """Adiciona a palavra-chave do input à lista no session_state."""
        keyword = st.session_state.keyword_input
        if keyword and keyword.lower() not in [k.lower() for k in st.session_state.keywords]:
            st.session_state.keywords.append(keyword)
        st.session_state.keyword_input = "" # Limpa o campo de input

    st.text_input(
        "Buscar por palavras-chave:",
        placeholder="Digite uma palavra e pressione Enter...",
        on_change=add_keyword,
        key="keyword_input"
    )

    # Exibe as palavras-chave ativas com opção de remover
    if st.session_state.keywords:
        st.write("Filtros ativos:")
        cols = st.columns(len(st.session_state.keywords))
        for i, keyword in enumerate(st.session_state.keywords):
            with cols[i]:
                if st.button(f"❌ {keyword}", key=f"kw_{keyword}", use_container_width=True):
                    st.session_state.keywords.remove(keyword)
                    st.rerun()
    
    # --- Botão para Gerar Questão ---
    if st.button("Gerar Nova Questão", type="primary", use_container_width=True):
        with st.spinner("Buscando uma questão com os filtros selecionados..."):
            st.session_state.current_question = get_next_question(
                user_id,
                specialty=selected_specialty,
                provas=selected_provas,
                keywords=st.session_state.keywords
            )
            st.session_state.answer_submitted = False # Reseta o estado da resposta

# =================================================================
# ÁREA DE EXIBIÇÃO DA QUESTÃO
# =================================================================
st.markdown("---")

q = st.session_state.current_question

if q:
    st.markdown(f"**Prova:** {q.get('prova', 'N/A')} | **Áreas:** {q.get('areas_principais', 'N/A')}")
    st.write(q.get('enunciado', ''))
    
    alternativas = json.loads(q.get('alternativas', '{}'))
    
    # Botões de alternativa
    if not st.session_state.answer_submitted:
        selected_answer = None
        for key, value in alternativas.items():
            if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True):
                selected_answer = key
        
        if selected_answer:
            st.session_state.answer_submitted = True
            is_correct = (selected_answer == q['alternativa_correta'])
            save_answer(user_id, q['question_id'], selected_answer, is_correct)
            # Guarda a resposta selecionada para exibir o feedback correto
            st.session_state.feedback_answer = selected_answer
            st.rerun()

    # Feedback após resposta
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
    # Mensagem exibida quando não há questão carregada
    st.info("Use os filtros acima e clique em **'Gerar Nova Questão'** para começar seu simulado.")
    st.warning("Se nenhuma questão for encontrada, tente remover ou alterar alguns filtros.")