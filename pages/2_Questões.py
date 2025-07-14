# ==============================================================================
# ARQUIVO 3: pages/1_Questões.py (REFATORADO)
# Mova seu arquivo de Questões para dentro de uma pasta "pages".
# ==============================================================================
import streamlit as st
import json
# Importa apenas as funções necessárias do nosso arquivo de serviços
from services import get_next_question, save_answer, generate_question_with_gemini

st.set_page_config(layout="wide", page_title="Simulador de Questões")

# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar o simulado.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'selected_answer' not in st.session_state:
    st.session_state.selected_answer = None

# --- LÓGICA DA PÁGINA ---
user_id = st.session_state.user_id

# Carrega a questão se ainda não houver uma
if st.session_state.current_question is None:
    with st.spinner("Buscando uma nova questão para você..."):
        question = get_next_question(user_id)
        if question is None:
            question = generate_question_with_gemini()
        st.session_state.current_question = question

# --- UI DA PÁGINA ---
st.title("📝 Simulador de Questões")
q = st.session_state.current_question

if q:
    st.markdown(f"**Áreas:** {q.get('areas_principais', 'N/A')}")
    st.write(q.get('enunciado', ''))
    
    alternativas = json.loads(q.get('alternativas', '{}'))
    comentarios = json.loads(q.get('comentarios', '{}'))

    # Botões de alternativa
    for key, value in alternativas.items():
        if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True, disabled=st.session_state.answer_submitted):
            st.session_state.selected_answer = key
    
    # Botão de confirmar
    if st.button("Confirmar Resposta", disabled=st.session_state.answer_submitted or not st.session_state.selected_answer):
        st.session_state.answer_submitted = True
        is_correct = (st.session_state.selected_answer == q['alternativa_correta'])
        save_answer(user_id, q['question_id'], st.session_state.selected_answer, is_correct)
        st.rerun()

    # Feedback após resposta
    if st.session_state.answer_submitted:
        st.subheader("Comentários das Alternativas")
        for key, comment in comentarios.items():
            if key == q['alternativa_correta']:
                st.success(f"**{key} (Correta):** {comment}")
            elif key == st.session_state.selected_answer:
                st.error(f"**{key} (Sua Resposta):** {comment}")
            else:
                st.info(f"**{key}:** {comment}")
        
        if st.button("Próxima Questão", use_container_width=True, type="primary"):
            st.session_state.current_question = None
            st.session_state.answer_submitted = False
            st.session_state.selected_answer = None
            st.rerun()
else:
    st.warning("Não foi possível carregar ou gerar uma nova questão.")
    if st.button("Tentar novamente"):
        st.session_state.current_question = None
        st.rerun()