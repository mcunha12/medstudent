# ==============================================================================
# ARQUIVO: pages/1_Meu_Perfil.py (Corrigido)
# ==============================================================================
import streamlit as st
import pandas as pd
import plotly.express as px
from services import get_performance_data, get_time_window_metrics, get_temporal_performance, get_areas_performance, get_subtopics_for_review

# O st.set_page_config foi removido pois só pode ser chamado na Home.py
st.title("📊 Meu Perfil de Performance")
st.markdown("---")

# --- VERIFICA LOGIN E CARREGA DADOS ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para ver seu perfil.")
    st.page_link("Home.py", label="Voltar para a Home", icon="�")
    st.stop()

with st.spinner("Analisando seu histórico de performance..."):
    performance_data = get_performance_data(st.session_state.user_id)

if performance_data is None:
    st.info("Você ainda não respondeu nenhuma questão. Comece pelo simulado para ver suas estatísticas aqui!")
    st.stop()

all_answers = performance_data["all_answers"]
areas_exploded = performance_data["areas_exploded"]
subtopicos_exploded = performance_data["subtopicos_exploded"]

# --- LINHA 1: GRÁFICOS TEMPORAIS E RANKING ---
st.subheader("Evolução da Performance")

periodo_selecionado = st.selectbox(
    "Agrupar dados por:",
    ("Semana", "Dia")
)
period_map = {"Semana": "W", "Dia": "D"}
period_code = period_map[periodo_selecionado]

col1, col2, col3 = st.columns([2, 2, 1])

with col1:
    temporal_df = get_temporal_performance(all_answers, period=period_code)
    if not temporal_df.empty:
        fig = px.bar(temporal_df, x='periodo', y='questoes_respondidas', title=f"Questões Respondidas por {periodo_selecionado}", labels={'periodo': periodo_selecionado, 'questoes_respondidas': 'Quantidade'})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"Sem dados para o período selecionado.")

with col2:
    if not temporal_df.empty:
        fig = px.line(temporal_df, x='periodo', y='taxa_de_acerto', title=f"Taxa de Acerto por {periodo_selecionado}", markers=True, labels={'periodo': periodo_selecionado, 'taxa_de_acerto': 'Taxa de Acerto (%)'})
        fig.update_yaxes(range=[0, 101])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"Sem dados para o período selecionado.")

with col3:
    st.markdown("**Ranking Geral**")
    st.info("Em breve você poderá comparar sua performance com outros estudantes.")
    
    # --- CORREÇÃO APLICADA AQUI ---
    # Passamos apenas a URL para o st.image
    image_url = "https://placehold.co/300x200/007AFF/FFFFFF?text=Ranking"
    st.image(image_url, use_container_width=True)
    st.caption("(Em Breve)") # Usamos st.caption para o texto adicional


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

geral_metrics = get_time_window_metrics(all_answers)
d7_metrics = get_time_window_metrics(all_answers, days=7)
d30_metrics = get_time_window_metrics(all_answers, days=30)

st.markdown("##### Taxa de Acerto")
col1, col2, col3 = st.columns(3)
col1.metric("Geral", f"{geral_metrics['accuracy']:.1f}%")
col2.metric("Últimos 7 dias", f"{d7_metrics['accuracy']:.1f}%")
col3.metric("Últimos 30 dias", f"{d30_metrics['accuracy']:.1f}%")

st.markdown("##### Questões Respondidas")
col1, col2, col3 = st.columns(3)
col1.metric("Total", geral_metrics['answered'])
col2.metric("Últimos 7 dias", d7_metrics['answered'])
col3.metric("Últimos 30 dias", d30_metrics['answered'])

st.markdown("##### Questões Corretas")
col1, col2, col3 = st.columns(3)
col1.metric("Total", geral_metrics['correct'])
col2.metric("Últimos 7 dias", d7_metrics['correct'])
col3.metric("Últimos 30 dias", d30_metrics['correct'])