import streamlit as st
from services import get_or_create_user

st.set_page_config(layout="wide", page_title="Home - MedStudentAI")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .main { background-color: #F5F5F7; }
    .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
    .st-emotion-cache-z5fcl4 { padding-top: 2rem; }
    .card {
        background-color: white;
        border-radius: 12px;
        padding: 24px;
        margin: 10px 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: all 0.3s ease-in-out;
        height: 100%;
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
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if not st.session_state.user_id:
    st.title("Bem-vindo ao MedStudentAI! 👋")
    st.subheader("Insira seu e-mail para começar a praticar e salvar seu progresso.")
    
    with st.form("login_form"):
        email = st.text_input("Seu e-mail", placeholder="seu.email@med.com")
        submitted = st.form_submit_button("Acessar")
        if submitted and email:
            with st.spinner("Verificando..."):
                st.session_state.user_id = get_or_create_user(email)
            st.rerun()
else:
    st.title(f"Olá!")
    st.markdown("### O que vamos praticar hoje?")
    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="card">
            <h2>📊 Meu Perfil</h2>
            <p>Analise sua performance com gráficos detalhados, identifique pontos fracos e acompanhe sua evolução.</p>
        </div>
        """, unsafe_allow_html=True)
        # CORREÇÃO: Usando um emoji válido e o caminho do arquivo correto
        st.page_link("pages/1_Meu_Perfil.py", label="**Ver minha performance**", icon="📊")

    with col2:
        st.markdown("""
        <div class="card">
            <h2>📝 Simulador de Questões</h2>
            <p>Gere questões de múltipla escolha, teste seus conhecimentos e receba feedback detalhado na hora.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Questões.py", label="**Ir para o Simulado**", icon="📝")

    with col3:
        st.markdown("""
        <div class="card">
            <h2>💊 Calculadora de Posologia</h2>
            <p>Calcule doses de medicamentos de forma rápida e segura, com insights clínicos gerados por IA.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/3_Posologia.py", label="**Ir para a Calculadora**", icon="💊")
    
    if st.sidebar.button("Sair"):
        for key in st.session_state.keys():
            if key != 'user_id':
                del st.session_state[key]
        st.session_state.user_id = None
        st.rerun()