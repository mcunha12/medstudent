import streamlit as st
from services import get_all_subtopics, get_concept_explanation, get_relevant_concepts

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    layout="wide",
    page_title="Wiki de Conceitos - MedStudent",
    initial_sidebar_state="collapsed"
)

# --- FUNÇÃO PARA CARREGAR CSS EXTERNO ---
def load_css(file_name):
    # 'try-except' para evitar erro se o arquivo não for encontrado
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"Arquivo de estilo '{file_name}' não encontrado.")

# Carrega o CSS e o Header Fixo
load_css("style.css")
st.markdown('<div class="fixed-header">MedStudent 👨‍🏫</div>', unsafe_allow_html=True)


# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a Wiki de Conceitos.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

st.title("💡 Wiki de Conceitos")
st.markdown("Uma biblioteca de conhecimento que cresce com o nosso banco de questões. Use a busca para encontrar um tópico ou fazer uma pergunta.")
st.markdown("---")

# --- LÓGICA DA PÁGINA ---
all_topics = get_all_subtopics()

if not all_topics:
    st.info("Ainda não há subtópicos cadastrados no banco de questões para exibir na Wiki.")
    st.stop()

# --- Barra de Busca ---
search_query = st.text_input(
    "Buscar um conceito ou fazer uma pergunta...",
    placeholder="Ex: Qual o tratamento para infarto agudo do miocárdio?"
)

# --- LÓGICA DE BUSCA ---
if search_query:
    # Usa a nova função de busca semântica com a IA
    with st.spinner("Buscando conceitos relevantes com a IA..."):
        filtered_topics = get_relevant_concepts(search_query, all_topics)
else:
    # Se a busca estiver vazia, mostra todos os tópicos
    filtered_topics = all_topics

st.markdown(f"**Exibindo {len(filtered_topics)} de {len(all_topics)} conceitos.**")

# --- Listagem dos Conceitos ---
if not filtered_topics:
    st.warning("Nenhum conceito relevante encontrado para a sua busca.")
else:
    for topic in filtered_topics:
        with st.expander(f"📖 **{topic}**"):
            # A explicação é carregada sob demanda, apenas quando o usuário expande o card.
            with st.spinner(f"Buscando material de estudo para '{topic}'..."):
                # A função get_concept_explanation já contém a lógica de buscar no DB ou gerar com IA
                explanation = get_concept_explanation(topic)
                st.markdown(explanation, unsafe_allow_html=True)