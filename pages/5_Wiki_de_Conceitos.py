import streamlit as st
import pandas as pd
import math
from services import get_wiki_data, get_concept_explanation, get_relevant_concepts

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="centered",
    page_title="Wiki de Conceitos - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki de Conceitos.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("💡 Wiki de Conceitos")
st.markdown("Uma biblioteca de conhecimento para consulta rápida. Use os filtros para refinar sua busca.")

# --- CARREGAMENTO DOS DADOS BASE ---
wiki_df = get_wiki_data(st.session_state.user_id)

if wiki_df.empty:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()

all_areas = sorted(list(wiki_df['areas'].str.split(', ').explode().str.strip().unique()))
all_concepts_list = sorted(wiki_df['concept'].unique().tolist())

# --- INTERFACE DE FILTROS ---
with st.expander("🔎 Filtros e Busca"):
    show_only_incorrect = st.toggle(
        "Focar nos meus pontos fracos",
        help="Ative para ver apenas conceitos de questões que você errou."
    )
    selected_areas = st.multiselect(
        "Filtrar por Área(s):",
        options=all_areas
    )
    search_query = st.text_input(
        "Buscar por palavra-chave ou fazer uma pergunta:",
        placeholder="Ex: Fibrilação Atrial, tratamento para IAM..."
    )

# --- NOVA LÓGICA DE FILTRAGEM CONDICIONAL ---

# Verifica se algum filtro foi ativado pelo usuário
any_filter_active = show_only_incorrect or selected_areas or search_query

if any_filter_active:
    # Se um filtro estiver ativo, executa a lógica de filtragem detalhada
    filtered_df = wiki_df.copy()

    if show_only_incorrect:
        filtered_df = filtered_df[filtered_df['user_has_error'] == True]
    if selected_areas:
        filtered_df = filtered_df[filtered_df['areas'].apply(lambda x: any(area in x for area in selected_areas))]
    if search_query:
        search_results_df = filtered_df[filtered_df['concept'].str.contains(search_query, case=False, na=False)]
        
        if search_results_df.empty:
            with st.spinner("Nenhum resultado direto encontrado. Buscando com IA..."):
                ai_concepts = get_relevant_concepts(search_query, all_concepts_list)
                filtered_df = wiki_df[wiki_df['concept'].isin(ai_concepts)]
                st.info(f"A busca com IA encontrou {len(ai_concepts)} conceito(s) relacionado(s).")
        else:
            filtered_df = search_results_df
    
    final_concepts_list = sorted(filtered_df['concept'].unique().tolist())
else:
    # Se nenhum filtro estiver ativo, a lista final é simplesmente a lista completa de conceitos
    final_concepts_list = all_concepts_list

# --- FEEDBACK DE RESULTADOS ---
st.markdown("---")
st.markdown(f"**{len(final_concepts_list)} conceitos encontrados.**")
st.write("")

# --- LISTAGEM DOS CONCEITOS (SEM PAGINAÇÃO) ---
if not final_concepts_list:
    st.warning("Nenhum conceito encontrado para os filtros selecionados.")
else:
    for topic in final_concepts_list:
        with st.expander(topic):
            # A função pesada só é chamada aqui, quando o card é expandido.
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)
            st.markdown("---")  