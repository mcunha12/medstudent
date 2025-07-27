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

# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para ver seu histórico.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("🔎 Revisão de Questões")
st.markdown("---")

# --- CARREGA E LIMPA OS DADOS DO HISTÓRICO ---
with st.spinner("Carregando seu histórico de respostas..."):
    answered_df = get_user_answered_questions_details(st.session_state.user_id)

if answered_df.empty:
    st.info("Você ainda não respondeu nenhuma questão. Responda algumas no simulado para vê-las aqui!")
    st.stop()

# --- CORREÇÃO: Limpeza dos dados para os filtros funcionarem corretamente ---
if 'areas_principais' in answered_df.columns:
    answered_df['areas_principais_cleaned'] = answered_df['areas_principais'].astype(str).str.replace(r'[\[\]"]', '', regex=True)
else:
    answered_df['areas_principais_cleaned'] = ''

if 'prova' in answered_df.columns:
    answered_df['prova_cleaned'] = answered_df['prova'].astype(str).str.replace(r'[\[\]"]', '', regex=True)
else:
    answered_df['prova_cleaned'] = ''


# --- ÁREA DE FILTROS ---
st.subheader("Filtros")

search_query = st.text_input(
    "Buscar por palavra-chave:",
    placeholder="Ex: diabetes, insuficiência renal, penicilina..."
)

col1, col2, col3 = st.columns(3)

with col1:
    status_filter = st.selectbox(
        "Filtrar por Status:",
        options=["Todas", "Corretas", "Incorretas"]
    )

with col2:
    # Filtro por Área (usando a coluna limpa)
    unique_areas = sorted(
        answered_df['areas_principais_cleaned'].str.split(',')
        .explode()
        .str.strip()
        .dropna()
        .loc[lambda x: x != '']
        .unique()
        .tolist()
    )
    area_filter = st.multiselect("Filtrar por Área:", options=unique_areas)

with col3:
    # Filtro por Prova (usando a coluna limpa)
    unique_provas = sorted(
        answered_df['prova_cleaned'].dropna().loc[lambda x: x != ''].unique().tolist()
    )
    prova_filter = st.multiselect("Filtrar por Prova:", options=unique_provas)

# --- APLICA A LÓGICA DE FILTRAGEM ---
filtered_df = answered_df.copy()

# 1. Filtro de busca por palavra-chave
if search_query:
    searchable_text = filtered_df.apply(
        lambda row: ' '.join(row[['enunciado', 'alternativas', 'comentarios', 'areas_principais_cleaned', 'subtopicos', 'prova_cleaned']].astype(str).fillna('')),
        axis=1
    )
    filtered_df = filtered_df[searchable_text.str.contains(search_query, case=False, na=False)]

# 2. Filtros de status, área e prova
if status_filter == "Corretas":
    filtered_df['is_correct'] = (filtered_df['is_correct'].astype(str).str.lower() == 'true')
    filtered_df = filtered_df[filtered_df['is_correct'] == True]
elif status_filter == "Incorretas":
    filtered_df['is_correct'] = (filtered_df['is_correct'].astype(str).str.lower() == 'true')
    filtered_df = filtered_df[filtered_df['is_correct'] == False]

if area_filter:
    # A filtragem agora usa a coluna limpa
    filtered_df = filtered_df[filtered_df['areas_principais_cleaned'].str.contains('|'.join(area_filter), case=False, na=False)]

if prova_filter:
    # A filtragem agora usa a coluna limpa
    filtered_df = filtered_df[filtered_df['prova_cleaned'].isin(prova_filter)]


st.markdown("---")
# --- EXIBIÇÃO DA LISTAGEM ---
# (O restante do código para exibir os resultados permanece o mesmo)

st.subheader(f"Exibindo {len(filtered_df)} de {len(answered_df)} questões")

if filtered_df.empty:
    st.warning("Nenhum resultado encontrado para os filtros selecionados.")
else:
    for _, row in filtered_df.iterrows():
        # Converte 'is_correct' para booleano para o ícone
        is_correct_bool = str(row.get('is_correct', 'false')).lower() == 'true'
        icon = '✅' if is_correct_bool else '❌'
        
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