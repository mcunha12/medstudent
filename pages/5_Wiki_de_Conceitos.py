import streamlit as st
from services import _generate_title_and_explanation, _save_ai_concept, get_user_search_history, get_concept_by_id

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

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'current_concept' not in st.session_state:
    st.session_state.current_concept = None

USER_ID = st.session_state.user_id

st.title("💡 Wiki com IA")
st.markdown("Faça uma pergunta ou pesquise um termo para obter uma explicação detalhada gerada por IA.")

# --- BARRA DE PESQUISA ---
with st.form(key="search_form", clear_on_submit=True):
    search_query = st.text_input(
        "Pesquisar conceito...",
        placeholder="Ex: Tratamento para Infarto Agudo do Miocárdio",
        key="wiki_search_input" # Chave para manter o valor se necessário
    )
    submitted = st.form_submit_button("Pesquisar", use_container_width=True)

# Processa a busca quando o formulário é enviado
if submitted and search_query:
    # Sempre gera um novo conceito e o salva
    st.toast("Gerando novo conceito com IA...", icon="🧠")
    with st.spinner("Aguarde, a IA está trabalhando..."):
        new_concept_data = _generate_title_and_explanation(search_query)

    if new_concept_data and 'title' in new_concept_data and 'explanation' in new_concept_data and new_concept_data['title'] != 'Erro':
        saved_concept = _save_ai_concept(new_concept_data, USER_ID)
        if saved_concept:
            st.toast("Novo conceito gerado e salvo!", icon="✅")
            st.session_state.current_concept = saved_concept
        else:
            st.error("Falha ao salvar o novo conceito.")
            st.session_state.current_concept = {'title': 'Erro', 'explanation': 'Falha ao salvar o novo conceito.'}
    else:
        st.error("A IA não conseguiu gerar o conteúdo para sua busca. Tente refinar a pergunta.")
        st.session_state.current_concept = {'title': 'Erro', 'explanation': new_concept_data.get('explanation', 'A IA não conseguiu gerar uma resposta.')}

# --- EXIBIÇÃO DO CONCEITO ATUAL ---
if st.session_state.current_concept:
    concept = st.session_state.current_concept
    st.markdown("---")
    
    # Exibe o título do conceito
    st.subheader(f"📖 {concept['title']}")
    
    # ENVOLVE A EXPLICAÇÃO DENTRO DE UM EXPANDER PARA TORNÁ-LA MINIMIZÁVEL
    with st.expander(f"Ver Explicação Detalhada: {concept['title']}", expanded=True):
        st.markdown(concept['explanation'], unsafe_allow_html=True)

# --- HISTÓRICO DE BUSCA DO USUÁRIO ---
st.markdown("---")
st.subheader("Seu Histórico de Pesquisas")

search_history = get_user_search_history(USER_ID)

if not search_history:
    st.info("Seu histórico de pesquisas aparecerá aqui.")
else:
    # Exibe o histórico em até 3 colunas
    cols = st.columns(3)
    for i, item in enumerate(search_history):
        col = cols[i % 3]
        # O botão agora usa o ID único do conceito como chave
        if col.button(item['title'], key=item['id'], use_container_width=True):
            # Ao clicar, busca o conceito completo pelo ID e atualiza o estado
            with st.spinner("Carregando do seu histórico..."):
                st.session_state.current_concept = get_concept_by_id(item['id'])
            st.rerun()