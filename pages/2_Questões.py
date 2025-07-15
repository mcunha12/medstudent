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

    st.markdown("**Buscar em:**")
    filter_cols = st.columns(3)
    with filter_cols[0]:
        status_nao_respondidas = st.checkbox("Questões não respondidas", value=True)
    with filter_cols[1]:
        status_corretas = st.checkbox("Questões que acertei")
    with filter_cols[2]:
        status_incorretas = st.checkbox("Questões que errei")

    selected_status_values = []
    if status_nao_respondidas:
        selected_status_values.append("nao_respondidas")
    if status_corretas:
        selected_status_values.append("corretas")
    if status_incorretas:
        selected_status_values.append("incorretas")
    
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

    # --- ALTERAÇÃO APLICADA AQUI ---
    # Lógica para exibir e permitir a remoção individual de palavras-chave
    if st.session_state.keywords:
        st.caption("Palavras-chave ativas (clique para remover):")
        
        # Define um número máximo de colunas por linha para os botões
        cols_per_row = 7 
        
        # Agrupa as palavras-chave em linhas de 'cols_per_row'
        for i in range(0, len(st.session_state.keywords), cols_per_row):
            cols = st.columns(cols_per_row)
            # Pega a "fatia" de palavras-chave para a linha atual
            chunk = st.session_state.keywords[i:i + cols_per_row]
            
            for j, keyword in enumerate(chunk):
                with cols[j]:
                    # Cria um botão para cada palavra-chave
                    if st.button(f"❌ {keyword}", key=f"kw_{keyword}", use_container_width=True):
                        st.session_state.keywords.remove(keyword)
                        st.rerun()
        
        # Adiciona um separador e mantém o botão de limpar tudo
        st.markdown("""<hr style="height:1px;border:none;color:#333;background-color:#333;" /> """, unsafe_allow_html=True)
        if st.button("Limpar todas as palavras-chave"):
            st.session_state.keywords = []
            st.rerun()
    # --- FIM DA ALTERAÇÃO ---
    
    if st.button("Gerar Nova Questão", type="primary", use_container_width=True):
        if not selected_status_values:
            st.warning("Por favor, selecione pelo menos um status de questão para buscar (ex: Não respondidas).")
        else:
            with st.spinner("Buscando uma questão com os filtros selecionados..."):
                st.session_state.current_question = get_next_question(
                    user_id,
                    status_filters=selected_status_values,
                    specialty=selected_specialty,
                    provas=selected_provas,
                    keywords=st.session_state.keywords
                )
                st.session_state.answer_submitted = False
                st.session_state.feedback_answer = None
                st.rerun()

# =================================================================
# ÁREA DE EXIBIÇÃO DA QUESTÃO (sem alterações)
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