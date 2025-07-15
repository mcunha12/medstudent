import streamlit as st
import json
# Importa as funções, incluindo a nova 'get_all_specialties'
from services import get_next_question, save_answer, generate_question_with_gemini, get_all_specialties

# --- VERIFICA SE O USUÁRIO ESTÁ LOGADO ---
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar o simulado.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# --- INICIALIZAÇÃO DO ESTADO DA PÁGINA ---
# Adiciona o estado para controlar o filtro selecionado
if 'selected_specialty' not in st.session_state:
    st.session_state.selected_specialty = None
if 'current_question' not in st.session_state:
    st.session_state.current_question = None
if 'answer_submitted' not in st.session_state:
    st.session_state.answer_submitted = False
if 'selected_answer' not in st.session_state:
    st.session_state.selected_answer = None

user_id = st.session_state.user_id
st.title("📝 Simulador de Questões")

# =================================================================
# ESTÁGIO 1: SELEÇÃO DO FILTRO
# Este bloco só aparece se nenhuma especialidade foi escolhida ainda.
# =================================================================
if st.session_state.selected_specialty is None:
    st.subheader("Passo 1: Escolha uma área para praticar")
    
    with st.spinner("Buscando especialidades..."):
        specialties = get_all_specialties()
    
    # Prepara as opções para o selectbox
    options = ["Todas"] + specialties if specialties else ["Todas"]
    
    # Usamos um formulário para que a página só recarregue ao clicar no botão
    with st.form("specialty_form"):
        chosen_specialty = st.selectbox(
            "Selecione a especialidade:",
            options=options,
            help="Escolha 'Todas' para praticar questões de qualquer área."
        )
        submit_button = st.form_submit_button("Iniciar Simulado")

        if submit_button:
            st.session_state.selected_specialty = chosen_specialty
            # Limpa qualquer questão anterior antes de começar
            st.session_state.current_question = None
            st.rerun()

# =================================================================
# ESTÁGIO 2: EXIBIÇÃO DA QUESTÃO
# Este bloco só executa depois que uma especialidade foi selecionada.
# =================================================================
else:
    # Carrega a questão se ainda não houver uma, agora usando o filtro
    if st.session_state.current_question is None:
        with st.spinner(f"Buscando questão de '{st.session_state.selected_specialty}'..."):
            question = get_next_question(user_id, specialty=st.session_state.selected_specialty)
        
        # Se não encontrar questão filtrada, avisa o usuário
        if question is None:
            st.warning(f"Nenhuma questão inédita encontrada para a área '{st.session_state.selected_specialty}'.")
            st.info("Tente a opção 'Todas' ou escolha outra especialidade.")
            if st.button("Mudar Filtro"):
                st.session_state.selected_specialty = None
                st.rerun()
            st.stop() # Para a execução se não houver questão
        
        st.session_state.current_question = question

    # --- A UI da questão (o resto do seu código, agora dentro deste 'else') ---
    q = st.session_state.current_question
    
    # Botão para mudar o filtro fica visível o tempo todo
    st.caption(f"Filtro ativo: **{st.session_state.selected_specialty}**")

    st.markdown(f"**Áreas:** {q.get('areas_principais', 'N/A')}")
    st.write(q.get('enunciado', ''))
    
    alternativas = json.loads(q.get('alternativas', '{}'))
    
    # Botões de alternativa
    for key, value in alternativas.items():
        if st.button(f"{key}: {value}", key=f"ans_{key}", use_container_width=True, disabled=st.session_state.answer_submitted):
            st.session_state.selected_answer = key
    
    # Botão de confirmar
    if st.button("Confirmar Resposta", disabled=st.session_state.answer_submitted or not st.session_state.selected_answer, use_container_width=True):
        st.session_state.answer_submitted = True
        is_correct = (st.session_state.selected_answer == q['alternativa_correta'])
        save_answer(user_id, q['question_id'], st.session_state.selected_answer, is_correct)
        st.rerun()

    # Feedback após resposta
    if st.session_state.answer_submitted:
        comentarios = json.loads(q.get('comentarios', '{}'))
        st.subheader("Comentários das Alternativas")
        for key, comment in comentarios.items():
            if key == q['alternativa_correta']:
                st.success(f"**{key} (Correta):** {comment}")
            elif key == st.session_state.selected_answer:
                st.error(f"**{key} (Sua Resposta):** {comment}")
            else:
                st.info(f"**{key}:** {comment}")
        
        # Opções após responder
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Próxima Questão", use_container_width=True, type="primary"):
                st.session_state.current_question = None
                st.session_state.answer_submitted = False
                st.session_state.selected_answer = None
                st.rerun()
        with col2:
            if st.button("Mudar Filtro de Área", use_container_width=True):
                st.session_state.selected_specialty = None
                st.session_state.current_question = None
                st.session_state.answer_submitted = False
                st.session_state.selected_answer = None
                st.rerun()