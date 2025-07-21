import streamlit as st
import pandas as pd
import math
from services import (
    get_all_concepts_with_areas, 
    get_subtopics_from_incorrect_answers, 
    get_concept_explanation
)

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="centered", # Layout centralizado fica melhor em mobile
    page_title="Wiki de Conceitos - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- FUNÇÃO PARA CARREGAR CSS EXTERNO ---
def load_css(file_name):
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Arquivo de estilo '{file_name}' não encontrado.")

# Carrega o CSS e o Header Fixo
load_css("style.css")
st.markdown('<div class="fixed-header">MedStudent 👨‍🏫</div>', unsafe_allow_html=True)

# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki de Conceitos.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'wiki_page_number' not in st.session_state:
    st.session_state.wiki_page_number = 0

st.title("💡 Wiki de Conceitos")
st.markdown("Uma biblioteca de conhecimento para consulta rápida. Use os filtros para refinar sua busca.")

# --- CARREGAMENTO DOS DADOS BASE ---
concepts_df = get_all_concepts_with_areas()
if concepts_df.empty:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()
all_areas = sorted(list(concepts_df['area'].unique()))

# --- INTERFACE DE FILTROS ---
with st.expander("🔎 Filtros e Busca"):
    # Filtro por Questões Incorretas (mais proeminente)
    show_only_incorrect = st.toggle(
        "Focar nos meus pontos fracos",
        help="Ative para ver apenas conceitos de questões que você errou."
    )
    # Filtro por Área
    selected_areas = st.multiselect(
        "Filtrar por Área(s):",
        options=all_areas,
        placeholder="Selecione uma ou mais áreas"
    )
    # Barra de Busca por texto
    search_query = st.text_input(
        "Buscar por palavra-chave:",
        placeholder="Ex: Fibrilação Atrial, Diabetes..."
    )

# --- LÓGICA DE FILTRAGEM ---
filtered_df = concepts_df.copy()
if show_only_incorrect:
    incorrect_topics = get_subtopics_from_incorrect_answers(st.session_state.user_id)
    if incorrect_topics:
        filtered_df = filtered_df[filtered_df['concept'].isin(incorrect_topics)]
    else:
        st.info("Você não tem questões erradas registradas para filtrar.")
        filtered_df = pd.DataFrame(columns=['concept', 'area'])
if selected_areas:
    filtered_df = filtered_df[filtered_df['area'].isin(selected_areas)]
if search_query:
    filtered_df = filtered_df[filtered_df['concept'].str.contains(search_query, case=False, na=False)]

final_concepts_list = sorted(filtered_df['concept'].unique().tolist())

# --- LÓGICA DE PAGINAÇÃO ---
ITEMS_PER_PAGE = 20
total_items = len(final_concepts_list)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1

if st.session_state.wiki_page_number >= total_pages:
    st.session_state.wiki_page_number = 0

start_idx = st.session_state.wiki_page_number * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
paginated_concepts = final_concepts_list[start_idx:end_idx]

# --- CONTROLES DE PAGINAÇÃO E FEEDBACK ---
st.markdown(f"**{total_items} conceitos encontrados.**")

if total_pages > 1:
    st.markdown('<div class="pagination-controls">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.wiki_page_number == 0)):
            st.session_state.wiki_page_number -= 1
            st.rerun()
    with col2:
        st.markdown(f"<div class='page-indicator'>Página {st.session_state.wiki_page_number + 1}/{total_pages}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.wiki_page_number >= total_pages - 1)):
            st.session_state.wiki_page_number += 1
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

st.write("") # Espaçamento

# --- LISTAGEM DOS CONCEITOS ---
if not paginated_concepts:
    st.warning("Nenhum conceito encontrado para os filtros selecionados.")
else:
    for topic in paginated_concepts:
        # Envolve cada expander em um div com a classe CSS para estilização
        st.markdown('<div class="concept-item">', unsafe_allow_html=True)
        with st.expander(topic):
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)