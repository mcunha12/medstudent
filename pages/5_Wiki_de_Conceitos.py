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

# --- INICIALIZAÇÃO E CARREGAMENTO DE DADOS ---
# O estado agora só precisa guardar a lista de conceitos
if 'all_concepts' not in st.session_state:
    st.session_state.all_concepts = get_user_search_history(USER_ID)

st.title("💡 Wiki de Conceitos")
st.markdown("Pesquise em seu histórico ou peça para a IA gerar uma nova explicação sobre qualquer tema.")

# --- LAYOUT: Barra de Busca e Botão de Geração ---
col1, col2 = st.columns([3, 2])

with col1:
    search_term = st.text_input(
        "Filtrar conceitos ou buscar novo tema...",
        placeholder="Ex: Fisiopatologia da Sepse",
        label_visibility="collapsed"
    )

with col2:
    if st.button("🤖 Gerar Explicação com IA", use_container_width=True) and search_term:
        with st.spinner(f"A IA está estudando sobre '{search_term}'..."):
            result = find_or_create_ai_concept(search_term, USER_ID)

        if result and result.get("status") != "error":
            st.toast(result.get("message"), icon="✅")
            new_concept = result.get("concept")
            
            # Adiciona o novo conceito à lista na sessão para exibição imediata
            if not any(c['id'] == new_concept['id'] for c in st.session_state.all_concepts):
                st.session_state.all_concepts.insert(0, new_concept)
            
            # Limpa o termo de busca para mostrar a lista completa com o novo item no topo
            st.query_params.clear() 
            st.rerun()
        else:
            st.error(result.get("message", "Ocorreu um erro desconhecido."))

st.markdown("---")

# --- LÓGICA DE FILTRAGEM ---
if search_term:
    filtered_concepts = [
        concept for concept in st.session_state.all_concepts 
        if search_term.lower() in concept['title'].lower()
    ]
    st.subheader(f"Resultados da busca por: '{search_term}'")
else:
    filtered_concepts = st.session_state.all_concepts
    st.subheader("Seu Histórico de Conceitos")

# --- LÓGICA DE EXIBIÇÃO SIMPLIFICADA ---
if not filtered_concepts:
    st.info("Nenhum conceito encontrado.")
else:
    for concept in filtered_concepts:
        # A exibição agora é direta, sem botões ou estados de "ativo"
        # O usuário controla o que está expandido ou não
        with st.expander(f"**{concept['title']}**"):
            st.markdown(concept.get('explanation', '*Explicação não disponível.*'), unsafe_allow_html=True)