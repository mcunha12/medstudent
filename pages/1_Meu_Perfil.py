# ==============================================================================
# ARQUIVO 3: pages/3_Meu_Perfil.py (NOVO)
# Crie este arquivo dentro da pasta "pages".
# ==============================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
from services import get_performance_data, get_time_window_metrics, get_weekly_performance, get_areas_performance, get_subtopics_for_review

st.set_page_config(layout="wide", page_title="Meu Perfil")

st.title("📊 Meu Perfil de Performance")
st.markdown("---")

# --- VERIFICA LOGIN E CARREGA DADOS ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para ver seu perfil.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

with st.spinner("Analisando seu histórico de performance..."):
    performance_data = get_performance_data(st.session_state.user_id)

if performance_data is None:
    st.info("Você ainda não respondeu nenhuma questão. Comece pelo simulado para ver suas estatísticas aqui!")
    st.stop()

# Desempacota os dataframes para uso
all_answers = performance_data["all_answers"]
areas_exploded = performance_data["areas_exploded"]
subtopicos_exploded = performance_data["subtopicos_exploded"]

# --- LINHA 1: GRÁFICOS TEMPORAIS E RANKING ---
st.subheader("Evolução Semanal")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    weekly_df = get_weekly_performance(all_answers)
    if not weekly_df.empty:
        fig = px.bar(weekly_df, x='answered_at', y='questoes_respondidas', title="Questões Respondidas por Semana", labels={'answered_at': 'Semana', 'questoes_respondidas': 'Quantidade'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados semanais para exibir.")

with col2:
    if not weekly_df.empty:
        fig = px.line(weekly_df, x='answered_at', y='taxa_de_acerto', title="Taxa de Acerto por Semana", markers=True, labels={'answered_at': 'Semana', 'taxa_de_acerto': 'Taxa de Acerto (%)'})
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados semanais para exibir.")

with col3:
    st.markdown("**Ranking Geral**")
    st.info("Em breve você poderá comparar sua performance com outros estudantes.")
    st.image("https://placehold.co/300x200/007AFF/FFFFFF?text=Ranking\n(Em Breve)", use_column_width=True)


st.markdown("---")
# --- LINHA 2: ANÁLISE POR ÁREA E SUBTÓPICOS ---
st.subheader("Análise por Área de Conhecimento")
col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    areas_perf_df = get_areas_performance(areas_exploded)
    if not areas_perf_df.empty:
        top_areas_acerto = areas_perf_df.sort_values('taxa_de_acerto', ascending=False).head(10)
        fig = px.bar(top_areas_acerto, x='areas_principais', y='taxa_de_acerto', title="Áreas com Maior Acerto", labels={'areas_principais': 'Área', 'taxa_de_acerto': 'Taxa de Acerto (%)'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de áreas para exibir.")

with col2:
    if not areas_perf_df.empty:
        top_areas_pratica = areas_perf_df.sort_values('total_respondidas', ascending=False).head(10)
        fig = px.bar(top_areas_pratica, x='areas_principais', y='total_respondidas', title="Áreas Mais Praticadas", labels={'areas_principais': 'Área', 'total_respondidas': 'Nº de Questões'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de áreas para exibir.")

with col3:
    st.markdown("**Foco para os Estudos**")
    st.caption("Subtópicos de questões que você errou nos últimos 7 dias.")
    subtopics_review = get_subtopics_for_review(subtopicos_exploded)
    if subtopics_review:
        for topic in subtopics_review:
            st.warning(f"📌 {topic}")
    else:
        st.success("Parabéns! Nenhum ponto de melhoria encontrado nos últimos 7 dias.")

st.markdown("---")
# --- LINHAS 3, 4 e 5: MÉTRICAS GERAIS ---
st.subheader("Métricas de Performance")

# Calcula as métricas para os diferentes períodos
geral_metrics = get_time_window_metrics(all_answers)
d7_metrics = get_time_window_metrics(all_answers, days=7)
d30_metrics = get_time_window_metrics(all_answers, days=30)

# Linha 3: Taxa de Acerto
st.markdown("##### Taxa de Acerto")
col1, col2, col3 = st.columns(3)
col1.metric("Geral", f"{geral_metrics['accuracy']:.1f}%")
col2.metric("Últimos 7 dias", f"{d7_metrics['accuracy']:.1f}%")
col3.metric("Últimos 30 dias", f"{d30_metrics['accuracy']:.1f}%")

# Linha 4: Questões Respondidas
st.markdown("##### Questões Respondidas")
col1, col2, col3 = st.columns(3)
col1.metric("Total", geral_metrics['answered'])
col2.metric("Últimos 7 dias", d7_metrics['answered'])
col3.metric("Últimos 30 dias", d30_metrics['answered'])

# Linha 5: Questões Corretas
st.markdown("##### Questões Corretas")
col1, col2, col3 = st.columns(3)
col1.metric("Total", geral_metrics['correct'])
col2.metric("Últimos 7 dias", d7_metrics['correct'])
col3.metric("Últimos 30 dias", d30_metrics['correct'])
