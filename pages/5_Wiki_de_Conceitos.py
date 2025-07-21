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

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'wiki_page_number' not in st.session_state:
    st.session_state.wiki_page_number = 0

st.title("💡 Wiki de Conceitos")
st.markdown("Uma biblioteca de conhecimento para consulta rápida. Use os filtros para refinar sua busca.")

# --- CARREGAMENTO DOS DADOS BASE ---
# Esta função carrega apenas os metadados (nomes, áreas, flag de erro), sem as explicações.
wiki_df = get_wiki_data(st.session_state.user_id)

if wiki_df.empty:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()

all_areas = sorted(list(wiki_df['areas'].str.split(', ').explode().str.strip().unique()))
all_concepts_list = wiki_df['concept'].tolist()

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

# --- LÓGICA DE FILTRAGEM E BUSCA (COM PRIORIDADES) ---
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

# --- LÓGICA DE PAGINAÇÃO ---
ITEMS_PER_PAGE = 5000000
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
    col1, col2, col3 = st.columns([1, 1, 1])
    if col1.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.wiki_page_number == 0)):
        st.session_state.wiki_page_number -= 1
        st.rerun()
    col2.write(f"<div style='text-align: center; margin-top: 0.5rem;'>Página {st.session_state.wiki_page_number + 1}/{total_pages}</div>", unsafe_allow_html=True)
    if col3.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.wiki_page_number >= total_pages - 1)):
        st.session_state.wiki_page_number += 1
        st.rerun()

st.write("")

# --- LISTAGEM DOS CONCEITOS ---
if not paginated_concepts:
    st.warning("Nenhum conceito encontrado para os filtros selecionados.")
else:
    for topic in paginated_concepts:
        with st.expander(topic):
            # A função pesada só é chamada aqui, quando o card é expandido.
            # O resultado fica cacheado por 1 ano.
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)

