import streamlit as st
import re
from services import authenticate_or_register_user, get_global_platform_stats, load_concepts_df

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Home - MedStudent",
    initial_sidebar_state="collapsed"
)



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
                    
                    # --- PRÉ-CARREGAMENTO DOS CONCEITOS ---
                    with st.spinner("Preparando sua sessão..."):
                        load_concepts_df() # "Aquece" o cache com a lista de conceitos
                    
                    st.success(auth_response['message'])
                    st.rerun()
                else:
                    st.error(auth_response['message'])
else:
    # --- ESTRATÉGIA DE PRÉ-CARREGAMENTO (CACHE WARMING) ---
    # "Aquece" o cache dos conceitos na primeira vez que o usuário logado acessa a Home.
    if 'concepts_cache_warmed' not in st.session_state:
        with st.spinner("Otimizando sua sessão..."):
            # Esta função já é cacheada, então rodá-la aqui pré-popula o cache
            # para que a página da Wiki carregue instantaneamente.
            load_concepts_df()
        st.session_state.concepts_cache_warmed = True

    # O resto da página continua normalmente
    st.title(f"Bem-vindo de volta! 👋")
    st.markdown("### O que vamos praticar hoje?")
    
    st.write("") 
    
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.page_link("pages/1_Simulado.py", label="📝 Simulador", icon="📝")
    
    with col2:
        st.page_link("pages/2_Meu_Perfil.py", label="📊 Meu Perfil", icon="📊")

    with col3:
        st.page_link("pages/3_Revisão_de_Questões.py", label="🔎 Revisão", icon="🔎")
    
    with col4:
        st.page_link("pages/4_Posologia.py", label="💊 Posologia", icon="💊")

    with col5:
        st.page_link("pages/5_Wiki_de_Conceitos.py", label="💡 Wiki de Conceitos", icon="💡")

    # --- Seção de Estatísticas e Logout ---
    st.markdown("---")
    
    with st.spinner("Buscando dados da comunidade..."):
        stats = get_global_platform_stats()

    with st.container(border=True):
        st.markdown("<h3 style='text-align: center;'>Nossa Comunidade em Números</h3>", unsafe_allow_html=True)
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)

        with stat_col1:
            st.metric(label="Futuros Médicos", value=f"{stats['total_students']:,}".replace(",", "."))
        
        with stat_col2:
            st.metric(label="Ativos na Semana", value=f"{stats['active_this_week']:,}".replace(",", "."))
        
        with stat_col3:
            st.metric(label="Questões Resolvidas (7d)", value=f"{stats['answered_last_7_days']:,}".replace(",", "."))
            
        with stat_col4:
            st.metric(label="Acertos da Comunidade (7d)", value=f"{stats['accuracy_last_7_days']:.1f}%")

    with st.sidebar:
        st.write("")
        st.write("")
        if st.button("Sair da Conta", use_container_width=True):
            st.session_state.clear()
            st.rerun()