import streamlit as st
import pandas as pd
import json
from services import get_user_answered_questions_details

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Revisão - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- FUNÇÃO PARA CARREGAR CSS EXTERNO ---
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Carrega o CSS e o Header Fixo
load_css("style.css")
st.markdown('<div class="fixed-header">MedStudent 👨‍🏫</div>', unsafe_allow_html=True)


# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para ver seu histórico.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("🔎 Revisão de Questões Respondidas")
st.markdown("---")

# --- CARREGA OS DADOS DO HISTÓRICO ---
with st.spinner("Carregando seu histórico de respostas..."):
    answered_df = get_user_answered_questions_details(st.session_state.user_id)

if answered_df.empty:
    st.info("Você ainda não respondeu nenhuma questão. Responda algumas no simulado para vê-las aqui!")
    st.stop()

# --- ÁREA DE FILTROS ---
st.subheader("Filtros")

# Campo de busca por palavra-chave
search_query = st.text_input(
    "Buscar por palavra-chave:",
    placeholder="Ex: diabetes, insuficiência renal, penicilina..."
)

col1, col2, col3 = st.columns(3)

with col1:
    # Filtro por Acerto/Erro
    status_filter = st.selectbox(
        "Filtrar por Status:",
        options=["Todas", "Corretas", "Incorretas"]
    )

with col2:
    # Filtro por Área
    # Tratamento de erro para caso a coluna 'areas_principais' não exista ou esteja vazia
    if 'areas_principais' in answered_df.columns and not answered_df['areas_principais'].dropna().empty:
        unique_areas = sorted(list(answered_df['areas_principais'].dropna().str.split(',\s*').explode().str.strip().unique()))
    else:
        unique_areas = []
    area_filter = st.multiselect("Filtrar por Área:", options=unique_areas)

with col3:
    # Filtro por Prova
    if 'prova' in answered_df.columns and not answered_df['prova'].dropna().empty:
        unique_provas = sorted(list(answered_df['prova'].dropna().unique()))
    else:
        unique_provas = []
    prova_filter = st.multiselect("Filtrar por Prova:", options=unique_provas)

# --- APLICA A LÓGICA DE FILTRAGEM ---
filtered_df = answered_df.copy()

# 1. Aplica o filtro de busca por palavra-chave primeiro
if search_query:
    # Junta todas as colunas de texto em uma só para a busca
    searchable_text = filtered_df.apply(
        lambda row: ' '.join(row[['enunciado', 'alternativas', 'comentarios', 'areas_principais', 'subtopicos', 'prova']].astype(str).fillna('')),
        axis=1
    )
    filtered_df = filtered_df[searchable_text.str.contains(search_query, case=False, na=False)]

# 2. Aplica os outros filtros no resultado da busca
if status_filter == "Corretas":
    filtered_df = filtered_df[filtered_df['is_correct'] == True]
elif status_filter == "Incorretas":
    filtered_df = filtered_df[filtered_df['is_correct'] == False]

if area_filter:
    # Garante que a coluna existe antes de filtrar
    if 'areas_principais' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['areas_principais'].str.contains('|'.join(area_filter), case=False, na=False)]

if prova_filter:
    # Garante que a coluna existe antes de filtrar
    if 'prova' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['prova'].isin(prova_filter)]

st.markdown("---")

# --- EXIBIÇÃO DA LISTAGEM ---
st.subheader(f"Exibindo {len(filtered_df)} de {len(answered_df)} questões")

if filtered_df.empty:
    st.warning("Nenhum resultado encontrado para os filtros selecionados.")
else:
    for _, row in filtered_df.iterrows():
        icon = '✅' if row.get('is_correct', False) else '❌'
        expander_title = f"{icon} **{row.get('prova', 'N/A')}** | {row.get('enunciado', '')[:100]}..."

        with st.expander(expander_title):
            st.markdown(f"**Prova:** {row.get('prova', 'N/A')}")
            st.markdown(f"**Áreas:** {row.get('areas_principais', 'N/A')}")
            st.markdown("---")
            
            st.markdown("**Enunciado completo:**")
            st.write(row.get('enunciado', ''))
            st.markdown("---")

            st.subheader("Alternativas e Comentários")
            
            try:
                # Usar .get() com fallback para string JSON vazia evita erros
                alternativas = json.loads(row.get('alternativas', '{}'))
                comentarios = json.loads(row.get('comentarios', '{}'))
                alternativa_correta = row.get('alternativa_correta', '')
                sua_resposta = row.get('user_answer', '')

                for key, value in alternativas.items():
                    full_text = f"**{key}:** {value}"
                    
                    if key == alternativa_correta:
                        st.success(f"**{full_text} (Correta)**")
                        st.caption(f"Comentário: {comentarios.get(key, 'Sem comentário.')}")
                    elif key == sua_resposta:
                        st.error(f"**{full_text} (Sua Resposta)**")
                        st.caption(f"Comentário: {comentarios.get(key, 'Sem comentário.')}")
                    else:
                        st.info(f"{full_text}")
                        st.caption(f"Comentário: {comentarios.get(key, 'Sem comentário.')}")
            
            except Exception as e:
                st.error(f"Não foi possível exibir os detalhes da questão. Erro: {e}")
            
            st.markdown("---")
            st.subheader("Tópicos para Revisão")
            subtopicos = row.get('subtopicos', 'Nenhum subtópico listado.')
            st.info(f"📌 {subtopicos}")