import streamlit as st
from services import get_or_create_user

st.set_page_config(layout="wide", page_title="Home - MedStudentAI")

# --- ESTILO CSS ---
st.markdown("""
<style>
    .main { background-color: #F5F5F7; }
    /* Ajustes para garantir alinhamento e espaçamento consistentes */
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
        margin-bottom: 20px; /* Adiciona margem inferior */
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        transition: all 0.3s ease-in-out;
        flex-grow: 1; /* Faz o card crescer para preencher a coluna */
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

    # ALTERAÇÃO: Layout alterado para uma grade 2x2 para melhor organização
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    
    with row1_col1:
        # st.markdown("""
        # <div class="card">
        #     <h2>📊 Meu Perfil</h2>
        #     <p>Analise sua performance com gráficos detalhados, identifique pontos fracos e acompanhe sua evolução.</p>
        # </div>
        # """, unsafe_allow_html=True)
        st.page_link("pages/1_Meu_Perfil.py", label="**Ver minha performance**", icon="📊")

    with row1_col2:
        # st.markdown("""
        # <div class="card">
        #     <h2>📝 Simulador de Questões</h2>
        #     <p>Gere questões de múltipla escolha, teste seus conhecimentos e receba feedback detalhado na hora.</p>
        # </div>
        # """, unsafe_allow_html=True)
        st.page_link("pages/2_Questões.py", label="**Ir para o Simulado**", icon="📝")

    # NOVO CARD: Adicionado card para a página de Revisão
    with row2_col1:
        # st.markdown("""
        # <div class="card">
        #     <h2>🔎 Revisão de Questões</h2>
        #     <p>Revise todas as questões que você já respondeu, filtre por acertos, erros, área ou prova.</p>
        # </div>
        # """, unsafe_allow_html=True)
        st.page_link("pages/3_Revisão.py", label="**Revisar minhas questões**", icon="🔎")
    with row2_col2:
        # st.markdown("""
        # <div class="card">
        #     <h2>💊 Calculadora de Posologia</h2>
        #     <p>Calcule doses de medicamentos de forma rápida e segura, com insights clínicos gerados por IA.</p>
        # </div>
        # """, unsafe_allow_html=True)
        # CORREÇÃO: O caminho do arquivo foi corrigido de 3 para 4
        st.page_link("pages/4_Posologia.py", label="**Ir para a Calculadora**", icon="💊")
    
    # Lógica do Logout permanece a mesma
    if st.button("Sair", key="logout_button"):
        # Limpa todo o session_state para um logout completo
        st.session_state.clear()
        st.rerun()