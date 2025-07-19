import streamlit as st
from services import get_all_subtopics, get_concept_explanation

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Wiki de Conceitos - MedStudent",
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
    st.warning("Por favor, faça o login na Home para acessar a Wiki de Conceitos.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("💡 Wiki de Conceitos")
st.markdown("Uma biblioteca de conhecimento que cresce com o nosso banco de questões. Use a busca para encontrar um tópico.")
st.markdown("---")

# --- LÓGICA DA PÁGINA ---
# Busca todos os subtópicos únicos para listar na Wiki
all_topics = get_all_subtopics()

if not all_topics:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()

# --- Barra de Busca ---
search_query = st.text_input(
    "Buscar um conceito...",
    placeholder="Ex: Fibrilação Atrial, Diabetes Mellitus Tipo 2, Penicilinas..."
)

# Filtra os tópicos com base na busca
if search_query:
    # Busca case-insensitive
    filtered_topics = [topic for topic in all_topics if search_query.lower() in topic.lower()]
else:
    filtered_topics = all_topics

st.markdown(f"**Exibindo {len(filtered_topics)} de {len(all_topics)} conceitos.**")

# --- Listagem dos Conceitos ---
if not filtered_topics:
    st.warning("Nenhum conceito encontrado para a sua busca.")
else:
    for topic in filtered_topics:
        with st.expander(f"📖 **{topic}**"):
            # A explicação é carregada sob demanda, apenas quando o usuário expande o card.
            # Isso torna a página muito mais rápida.
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                # A função get_concept_explanation já contém a lógica de buscar no DB ou gerar com IA
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)