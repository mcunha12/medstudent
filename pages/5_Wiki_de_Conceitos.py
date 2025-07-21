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
    layout="wide",
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
st.markdown("Uma biblioteca de conhecimento que cresce com o nosso banco de questões. Use os filtros para refinar sua busca.")
st.markdown("---")


# --- CARREGAMENTO DOS DADOS BASE ---
concepts_df = get_all_concepts_with_areas()
all_areas = sorted(list(concepts_df['area'].unique()))

if concepts_df.empty:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()

# --- INTERFACE DE FILTROS ---
with st.expander("🔎 Filtros e Busca", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        # Filtro por Área
        selected_areas = st.multiselect(
            "Filtrar por Área(s):",
            options=all_areas,
            placeholder="Selecione uma ou mais áreas"
        )
    with col2:
        # Filtro por Questões Incorretas
        show_only_incorrect = st.toggle(
            "Mostrar apenas conceitos de questões que errei",
            help="Ative para focar nos seus pontos fracos com base no histórico de simulados."
        )
    
    # Barra de Busca por texto
    search_query = st.text_input(
        "Buscar um conceito por palavra-chave:",
        placeholder="Ex: Fibrilação Atrial, Diabetes Mellitus Tipo 2..."
    )

# --- LÓGICA DE FILTRAGEM ---
filtered_df = concepts_df.copy()

# 1. Filtra por questões incorretas, se ativado
if show_only_incorrect:
    incorrect_topics = get_subtopics_from_incorrect_answers(st.session_state.user_id)
    if incorrect_topics:
        filtered_df = filtered_df[filtered_df['concept'].isin(incorrect_topics)]
    else:
        st.info("Você não tem questões erradas registradas para filtrar.")
        filtered_df = pd.DataFrame(columns=['concept', 'area']) # Zera os resultados

# 2. Filtra por área(s) selecionada(s)
if selected_areas:
    filtered_df = filtered_df[filtered_df['area'].isin(selected_areas)]

# 3. Filtra pela busca de texto
if search_query:
    filtered_df = filtered_df[filtered_df['concept'].str.contains(search_query, case=False, na=False)]

# Pega a lista final e única de conceitos após todos os filtros
final_concepts_list = filtered_df['concept'].unique().tolist()

# --- LÓGICA DE PAGINAÇÃO ---
ITEMS_PER_PAGE = 20
total_items = len(final_concepts_list)
total_pages = math.ceil(total_items / ITEMS_PER_PAGE)

# Garante que o número da página seja válido após a filtragem
if st.session_state.wiki_page_number >= total_pages:
    st.session_state.wiki_page_number = 0

start_idx = st.session_state.wiki_page_number * ITEMS_PER_PAGE
end_idx = start_idx + ITEMS_PER_PAGE
paginated_concepts = final_concepts_list[start_idx:end_idx]

# --- CONTROLES DE PAGINAÇÃO E FEEDBACK ---
st.markdown(f"**Exibindo {len(paginated_concepts)} de {total_items} conceitos encontrados.**")

if total_pages > 1:
    page_indicator = f"Página {st.session_state.wiki_page_number + 1} de {total_pages}"
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("⬅️ Anterior", disabled=(st.session_state.wiki_page_number == 0)):
            st.session_state.wiki_page_number -= 1
            st.rerun()
    with col2:
        st.write(f"<div style='text-align: center;'>{page_indicator}</div>", unsafe_allow_html=True)
    with col3:
        if st.button("Próxima ➡️", disabled=(st.session_state.wiki_page_number >= total_pages - 1)):
            st.session_state.wiki_page_number += 1
            st.rerun()

st.markdown("---")

# --- LISTAGEM DOS CONCEITOS ---
if not paginated_concepts:
    st.warning("Nenhum conceito encontrado para os filtros selecionados.")
else:
    for topic in paginated_concepts:
        with st.expander(f"📖 **{topic}**"):
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)