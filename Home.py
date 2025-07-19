import streamlit as st
import re # Para validação de e-mail
from services import authenticate_or_register_user, get_global_platform_stats

# --- CONFIGURAÇÃO DA PÁGINA (DEVE SER O PRIMEIRO COMANDO) ---
st.set_page_config(
    layout="wide",
    page_title="Home - MedStudent",
    initial_sidebar_state="collapsed"  # Sidebar começa fechada
)

# --- FUNÇÃO PARA CARREGAR CSS EXTERNO ---
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Carrega o CSS e o Header Fixo
load_css("style.css")
st.markdown('<div class="fixed-header">MedStudent 👨‍🏫</div>', unsafe_allow_html=True)


# --- LÓGICA DE LOGIN E UI ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None

if not st.session_state.user_id:
    st.title("Bem-vindo ao MedStudent! 👋")
    st.subheader("Acesse sua conta ou cadastre-se para começar a praticar.")
    
    with st.form("login_form"):
        email = st.text_input("Seu e-mail", placeholder="seu.email@med.com")
        password = st.text_input("Sua senha", type="password", placeholder="********")
        submitted = st.form_submit_button("Entrar / Cadastrar")
        
        if submitted:
            # Lógica de validação de input
            is_valid = True
            
            if not email or not password:
                st.error("Por favor, preencha o e-mail e a senha.")
                is_valid = False

            elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                st.error("Formato de e-mail inválido. Verifique o e-mail digitado.")
                is_valid = False

            elif len(password) < 6:
                st.error("A senha deve ter no mínimo 6 caracteres.")
                is_valid = False

            if is_valid:
                with st.spinner("Verificando..."):
                    auth_response = authenticate_or_register_user(email, password)
                
                if auth_response['status'] == 'success':
                    st.session_state.user_id = auth_response['user_id']
                    st.success(auth_response['message'])
                    st.rerun()
                else:
                    st.error(auth_response['message'])
else:
    # Página para usuário logado
    st.title(f"Bem-vindo de volta! 👋")
    st.markdown("### O que vamos praticar hoje?")
    
    # Cards de Navegação
    row1_col1, row1_col2 = st.columns(2)
    row2_col1, row2_col2 = st.columns(2)
    
    with row1_col1:
        st.markdown("""
        <div class="card">
            <h2>📝 Simulador de Provas</h2>
            <p>Filtre por área, prova ou palavra-chave e teste seus conhecimentos com simulados de 20 questões.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/1_Simulado.py", label="**Ir para o Simulador**", icon="📝")

    with row1_col2:
        st.markdown("""
        <div class="card">
            <h2>📊 Meu Perfil</h2>
            <p>Analise sua performance com gráficos detalhados, identifique pontos fracos e acompanhe sua evolução.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/2_Meu_Perfil.py", label="**Ver minha performance**", icon="📊")

    with row2_col1:
        st.markdown("""
        <div class="card">
            <h2>🔎 Revisão de Questões</h2>
            <p>Revise todas as questões que você já respondeu, filtre por acertos, erros, área ou prova.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/3_Revisão_de_Questões.py", label="**Revisar minhas questões**", icon="🔎")
    
    with row2_col2:
        st.markdown("""
        <div class="card">
            <h2>💊 Calculadora de Posologia</h2>
            <p>Calcule doses de medicamentos de forma rápida e segura, com insights clínicos gerados por IA.</p>
        </div>
        """, unsafe_allow_html=True)
        st.page_link("pages/4_Posologia.py", label="**Acessar a Calculadora**", icon="💊")

    st.markdown("---")
    
    with st.spinner("Buscando dados da comunidade..."):
        stats = get_global_platform_stats()

    with st.container():
        st.markdown("<h3 style='text-align: center;'>Nossa Comunidade em Números</h3>", unsafe_allow_html=True)
        st.write("")

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

    with st.sidebar:
        st.write("")
        if st.button("Sair da Conta", use_container_width=True):
            st.session_state.clear()
            st.rerun()