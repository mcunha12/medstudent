import streamlit as st
from services import find_or_create_ai_concept, get_user_search_history, get_concept_by_id

st.set_page_config(
    layout="centered",
    page_title="Wiki IA - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- VERIFICA LOGIN ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki IA.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

USER_ID = st.session_state.user_id

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'active_concept_id' not in st.session_state:
    st.session_state.active_concept_id = None
if 'all_concepts' not in st.session_state:
    # Carrega todos os conceitos do usuário uma única vez
    st.session_state.all_concepts = get_user_search_history(USER_ID)

st.title("💡 Wiki de Conceitos")
st.markdown("Pesquise em seu histórico ou peça para a IA gerar uma nova explicação sobre qualquer tema.")

# --- NOVO LAYOUT: Barra de Busca e Botão de Geração ---
col1, col2 = st.columns([3, 2]) # A busca ocupa mais espaço

with col1:
    search_term = st.text_input(
        "Filtrar conceitos ou buscar novo tema...",
        placeholder="Ex: Fisiopatologia da Sepse",
        label_visibility="collapsed"
    )

with col2:
    # Este botão agora dispara a geração de IA
    if st.button("🤖 Gerar Explicação com IA", use_container_width=True) and search_term:
        with st.spinner(f"A IA está estudando sobre '{search_term}'..."):
            result = find_or_create_ai_concept(search_term, USER_ID)

        if result and result.get("status") != "error":
            st.toast(result.get("message"), icon="✅")
            new_concept = result.get("concept")
            
            # Atualiza o estado da sessão com o novo conceito
            st.session_state.active_concept_id = new_concept['id']
            # Adiciona o novo conceito à lista em cache para exibição imediata
            if not any(c['id'] == new_concept['id'] for c in st.session_state.all_concepts):
                st.session_state.all_concepts.insert(0, new_concept)

        else:
            st.error(result.get("message", "Ocorreu um erro desconhecido."))
            st.session_state.active_concept_id = None
        
        st.rerun()

st.markdown("---")

# --- LÓGICA DE FILTRAGEM ---
if search_term:
    # Filtra os conceitos com base no título
    filtered_concepts = [
        concept for concept in st.session_state.all_concepts 
        if search_term.lower() in concept['title'].lower()
    ]
else:
    # Se a busca estiver vazia, exibe todos
    filtered_concepts = st.session_state.all_concepts

# --- LÓGICA DE EXIBIÇÃO DOS CARDS ---
if not filtered_concepts:
    st.info("Nenhum conceito encontrado. Tente uma busca diferente ou gere uma nova explicação.")
else:
    st.subheader("Seu Histórico de Conceitos")
    for concept_summary in filtered_concepts:
        # A mágica para expandir o card ativo acontece aqui
        is_expanded = (concept_summary['id'] == st.session_state.active_concept_id)
        
        # Carrega o conteúdo completo apenas para o card que será expandido
        if is_expanded:
            full_concept = get_concept_by_id(concept_summary['id'])
            explanation_content = full_concept.get('explanation', 'Não foi possível carregar a explicação.')
        else:
            explanation_content = "Clique no botão ao lado para ver os detalhes..."

        with st.expander(f"**{concept_summary['title']}**", expanded=is_expanded):
            st.markdown(explanation_content, unsafe_allow_html=True)

        # Botão para definir o card como ativo (e expandi-lo no rerun)
        if st.button("Ver Detalhes", key=f"btn_{concept_summary['id']}", use_container_width=True):
            st.session_state.active_concept_id = concept_summary['id']
            st.rerun()