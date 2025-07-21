import streamlit as st
from services import find_or_create_ai_concept, get_user_search_history

st.set_page_config(
    layout="centered",
    page_title="Wiki IA - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'current_concept' not in st.session_state:
    st.session_state.current_concept = None

# --- VERIFICA LOGIN ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki IA.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("💡 Wiki com IA")
st.markdown("Faça uma pergunta ou pesquise um termo para obter uma explicação detalhada gerada por IA.")

# --- BARRA DE PESQUISA ---
search_query = st.text_input(
    "Pesquisar conceito...",
    placeholder="Ex: Tratamento para Infarto Agudo do Miocárdio",
    key="wiki_search_input"
)

if search_query:
    # Quando o usuário pesquisa, chama a função principal
    st.session_state.current_concept = find_or_create_ai_concept(
        search_query, st.session_state.user_id
    )
    # Limpa a barra de pesquisa para a próxima busca
    st.session_state.wiki_search_input = ""


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
    # Cria colunas para exibir o histórico de forma mais organizada
    cols = st.columns(3)
    col_idx = 0
    for item in search_history:
        with cols[col_idx % 3]:
            if st.button(item['title'], key=item['id'], use_container_width=True):
                # Ao clicar em um item do histórico, busca a explicação completa
                conn = st.session_state.db_connection # Assumindo que a conexão está no session_state
                query = "SELECT * FROM ai_concepts WHERE id = ?"
                concept_df = pd.read_sql_query(query, conn, params=(item['id'],))
                if not concept_df.empty:
                    st.session_state.current_concept = concept_df.to_dict('records')[0]
                    st.rerun()
        col_idx += 1