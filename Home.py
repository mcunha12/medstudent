import streamlit as st
# Adiciona a importação da nova função de estatísticas
from services import get_or_create_user, get_global_platform_stats

st.set_page_config(layout="wide", page_title="Home - MedStudent")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .main { background-color: #F5F5F7; }
    .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
    .st-emotion-cache-z5fcl4 { padding-top: 2rem; }
    [data-testid="column"] {
        display: flex;
        flex-direction: column;
        height: 100%;
    }
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: all 0.3s ease-in-out;
        flex-grow: 1;
    }
    .card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 24px rgba(0,0,0,0.1);
    }
    .card h2 {
        font-size: 22px;
        font-weight: 600;
        color: #007AFF;
        margin-top: 0;
    }
    .card p {
        color: #3C3C43;
    }
    /* Estilo para a seção de estatísticas */
    .stats-container {
        text-align: center;
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- LÓGICA DE LOGIN E UI ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if not st.session_state.user_id:
    st.title("Bem-vindo ao MedStudent! 👋")
    st.subheader("Insira seu e-mail para começar a praticar e salvar seu progresso.")
    
    with st.form("login_form"):
        email = st.text_input("Seu e-mail", placeholder="seu.email@med.com")
        submitted = st.form_submit_button("Acessar")
        if submitted and email:
            with st.spinner("Verificando..."):
                st.session_state.user_id = get_or_create_user(email)
            st.rerun()
else:
    st.title(f"Bem-vindo de volta! 👋")
    st.markdown("### O que vamos praticar hoje?")
    
    # Cards de Navegação
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    
    with row1_col1:
        st.markdown("""
        <div class="card">
            <h2>📊 Meu Perfil</h2>
            <p>Analise sua performance com gráficos detalhados, identifique pontos fracos e acompanhe sua evolução.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_Meu_Perfil.py", label="**Ver minha performance**", icon="📊")

    with row1_col2:
        st.markdown("""
        <div class="card">
            <h2>📝 Simulador de Questões</h2>
            <p>Filtre por área, prova ou palavra-chave e teste seus conhecimentos com questões direcionadas.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Questões.py", label="**Ir para o Simulador**", icon="📝")

    with row2_col1:
        st.markdown("""
        <div class="card">
            <h2>🔎 Revisão de Questões</h2>
            <p>Revise todas as questões que você já respondeu, filtre por acertos, erros, área ou prova.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/3_Revisão.py", label="**Revisar minhas questões**", icon="🔎")
    
    with row2_col2:
        st.markdown("""
        <div class="card">
            <h2>💊 Calculadora de Posologia</h2>
            <p>Calcule doses de medicamentos de forma rápida e segura, com insights clínicos gerados por IA.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/4_Posologia.py", label="**Acessar a Calculadora**", icon="💊")

    # --- NOVA SEÇÃO DE ESTATÍSTICAS ---
    st.markdown("---")
    
    with st.spinner("Buscando dados da comunidade..."):
        stats = get_global_platform_stats()

    with st.container():
        st.markdown("<h3 style='text-align: center; color: #ffffff;'>Nossa Comunidade em Números</h3>", unsafe_allow_html=True)
        st.write("") # Espaçamento

        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

        with stat_col1:
            st.metric(label="Futuros Médicos na Plataforma", value=f"{stats['total_students']:,}".replace(",", "."))
        
        with stat_col2:
            st.metric(label="Estudantes focados nesta Semana", value=f"{stats['active_this_week']:,}".replace(",", "."))
        
        with stat_col3:
            st.metric(label="Questões Resolvidas (Últimos 7 dias)", value=f"{stats['answered_last_7_days']:,}".replace(",", "."))
            
        with stat_col4:
            st.metric(label="Acertos da Comunidade (Últimos 7 dias)", value=f"{stats['accuracy_last_7_days']:.1f}%")
        
        st.markdown("</div>", unsafe_allow_html=True)

    # Lógica do Logout (movida para a barra lateral para melhor UX)
    with st.sidebar:
        st.write("") # Espaçamento
        if st.button("Sair da Conta", use_container_width=True):
            st.session_state.clear()
            st.rerun()