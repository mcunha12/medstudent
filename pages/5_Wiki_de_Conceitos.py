import streamlit as st
import pandas as pd
from services import find_or_create_ai_concept, get_user_search_history, get_db_connection

st.set_page_config(
    layout="centered",
    page_title="Wiki IA - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'current_concept' not in st.session_state:
    st.session_state.current_concept = None

# Inicializa a flag para controlar a limpeza da busca
if 'search_submitted' not in st.session_state:
    st.session_state.search_submitted = False

# --- VERIFICA LOGIN ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki IA.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("💡 Wiki com IA")
st.markdown("Faça uma pergunta ou pesquise um termo para obter uma explicação detalhada gerada por IA.")

# --- BARRA DE PESQUISA ---
# Define o valor padrão baseado no estado de submissão
default_value = "" if st.session_state.search_submitted else st.session_state.get("wiki_search_input", "")

search_query = st.text_input(
    "Pesquisar conceito...",
    placeholder="Ex: Tratamento para Infarto Agudo do Miocárdio",
    key="wiki_search_input",
    value=default_value
)

# Se uma pesquisa foi enviada, processa e marca para limpar na próxima renderização
if search_query and not st.session_state.search_submitted:
    st.session_state.current_concept = find_or_create_ai_concept(
        search_query, st.session_state.user_id
    )
    # Marca que a pesquisa foi submetida para limpar o campo
    st.session_state.search_submitted = True
    st.rerun()

# Reset da flag após a renderização
if st.session_state.search_submitted:
    st.session_state.search_submitted = False

# --- EXIBIÇÃO DO CONCEITO ATUAL ---
if st.session_state.current_concept:
    concept = st.session_state.current_concept
    st.markdown("---")
    st.header(concept['title'])
    st.markdown(concept['explanation'], unsafe_allow_html=True)

# --- HISTÓRICO DE BUSCA DO USUÁRIO ---
st.markdown("---")
st.subheader("Seu Histórico de Pesquisas")

search_history = get_user_search_history(st.session_state.user_id)

if not search_history:
    st.info("Seu histórico de pesquisas aparecerá aqui.")
else:
    cols = st.columns(3)
    col_idx = 0
    for item in search_history:
        with cols[col_idx % 3]:
            if st.button(item['title'], key=item['id'], use_container_width=True):
                # --- CORREÇÃO APLICADA AQUI ---
                # Obtém a conexão com o banco de dados da forma correta
                conn = get_db_connection() 
                query = "SELECT * FROM ai_concepts WHERE id = ?"
                concept_df = pd.read_sql_query(query, conn, params=(item['id'],))
                if not concept_df.empty:
                    st.session_state.current_concept = concept_df.to_dict('records')[0]
                    st.rerun()
        col_idx += 1