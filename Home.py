import streamlit as st
from services import get_or_create_user, get_user_stats # Importa funções do nosso novo arquivo

st.set_page_config(layout="wide", page_title="Home - Simulador ENAMED")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .main { background-color: #F5F5F7; }
    .st-emotion-cache-1y4p8pa { padding-top: 2rem; } /* Reduz o padding do topo */
    .st-emotion-cache-z5fcl4 { padding-top: 2rem; } /* Reduz o padding do topo */
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        margin: 10px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: all 0.3s ease-in-out;
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
</style>
""", unsafe_allow_html=True)

# --- LÓGICA DE LOGIN E UI ---

# Inicializa o user_id no estado da sessão se não existir
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

# Se não estiver logado, mostra a tela de login
if not st.session_state.user_id:
    st.title("Bem-vinda ao Simulador ENAMED, Yasmin! 👋")
    st.subheader("Insira seu e-mail para começar a praticar e salvar seu progresso.")
    
    with st.form("login_form"):
        email = st.text_input("Seu e-mail", placeholder="seu.email@med.com")
        submitted = st.form_submit_button("Acessar")
        if submitted and email:
            with st.spinner("Verificando..."):
                st.session_state.user_id = get_or_create_user(email)
            st.rerun()

# Se estiver logado, mostra a Home Page
else:
    st.title("Painel Principal")
    st.markdown("---")

    # --- SEÇÃO DE NAVEGAÇÃO ---
    st.header("O que vamos praticar hoje?")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="card">
            <h2>📝 Simulador de Questões</h2>
            <p>Gere questões de múltipla escolha, teste seus conhecimentos e receba feedback detalhado na hora.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_Questões.py", label="Ir para o Simulado", icon="📝")

    with col2:
        st.markdown("""
        <div class="card">
            <h2>💊 Calculadora de Posologia</h2>
            <p>Calcule doses de medicamentos de forma rápida e segura, com insights clínicos gerados por IA.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Posologia.py", label="Ir para a Calculadora", icon="💊")

    st.markdown("---")

    # --- SEÇÃO DE ESTATÍSTICAS ---
    st.header("Sua Performance")
    with st.spinner("Calculando suas estatísticas..."):
        stats = get_user_stats(st.session_state.user_id)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(label="Taxa de Acerto Geral", value=f"{stats['accuracy']:.1f}%")
    with c2:
        st.metric(label="Total de Questões Respondidas", value=stats['total_answered'])
    with c3:
        st.metric(label="Total de Respostas Corretas", value=stats['total_correct'])

    if st.sidebar.button("Sair"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()