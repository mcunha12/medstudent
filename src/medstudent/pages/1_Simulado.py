import streamlit as st
import requests
import json
import os

# Configuração da página
st.set_page_config(page_title="Simulado Dinâmico", layout="centered", page_icon="📝")

# CSS Apple-like
st.markdown(
    """
    <style>
      body { background-color: #F5F5F7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen; }
      .card { background: #FFF; border-radius: 16px; padding: 24px; margin-bottom: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
      h1 { font-size: 28px; font-weight: 600; color: #1C1C1E; margin-bottom: 8px; }
      .question { font-size: 18px; font-weight: 500; margin: 16px 0 8px; }
      .comment { font-size: 16px; color: #1C1C1E; margin-top: 12px; }
      .stButton>button { background-color: #007AFF; color: #FFFFFF; border: none; border-radius: 12px; padding: 12px; font-size: 17px; font-weight: 600; width: 100%; }
    </style>
    """,
    unsafe_allow_html=True
)

# Cabeçalho
st.markdown("<h1>Simulado de Medicina</h1>", unsafe_allow_html=True)

# Diretório de simulados
SIMULADOS_DIR = os.path.join(os.getcwd(), 'src', 'simulados')
BANCA_OPCOES = [
    os.path.splitext(f)[0]
    for f in os.listdir(SIMULADOS_DIR)
    if f.endswith('.json') and not f.startswith('.')
] if os.path.isdir(SIMULADOS_DIR) else []

# Estado inicial
st.session_state.setdefault('reference_data', None)
st.session_state.setdefault('current_q', None)
st.session_state.setdefault('show_comment', False)
st.session_state.setdefault('answer_selected', None)

# Validação de questão obrigatória (todos os campos)
def is_valid_question(q: dict) -> bool:
    # Enunciado
    if not (isinstance(q.get('question'), str) or isinstance(q.get('enunciado'), str)):
        return False
    # Alternativas
    alts = q.get('alternatives') or q.get('alternativas')
    if isinstance(alts, dict):
        if len(alts) != 5 or not all(isinstance(v, str) for v in alts.values()):
            return False
    else:
        return False
    # Comentário único
    comment = q.get('commentary') or q.get('comentario')
    if not (isinstance(comment, str) and comment):
        return False
    # Alternativa correta
    correct = q.get('correct_option') or q.get('correta')
    if not isinstance(correct, int) or correct < 1 or correct > 5:
        return False
    return True

# Gera questão válida com prompt específico e retries
def gerar_questao(ref_data):
    ref_json = json.dumps(ref_data, ensure_ascii=False)
    prompt = (
        "Analise o JSON de referência contendo enunciados e competências. "
        f"Referência: {ref_json}. Gere UMA questão de múltipla escolha de alto nível com 5 alternativas e um único comentário. "
        "O objeto JSON deve ter 4 campos: 'enunciado' (string), 'alternativas' (dict com 5 strings), "
        "'correct_option' (int de 1 a 5) e 'commentary' (string explicando por que cada alternativa está correta ou incorreta)."
    )
    for _ in range(5):
        try:
            body = {"model": st.secrets['MODEL'], "messages": [{"role": "system", "content": prompt}]}
            resp = requests.post(
                st.secrets['OPENROUTER_URL'],
                headers={"Authorization": f"Bearer {st.secrets['OPENROUTER_API_KEY']}"},
                json=body,
                timeout=15
            )
            resp.raise_for_status()
            q = json.loads(resp.json().get('choices', [{}])[0].get('message', {}).get('content', '{}'))
        except Exception:
            q = None
        if q and is_valid_question(q):
            return q
    st.error("Não foi possível gerar uma questão válida após várias tentativas.")
    return None

# Seleção de simulado e geração de questão
st.selectbox("Selecione o simulado:", BANCA_OPCOES, key='banca')
if st.button("Gerar Questão"):
    try:
        with open(os.path.join(SIMULADOS_DIR, f"{st.session_state.banca}.json"), encoding='utf-8') as f:
            st.session_state.reference_data = json.load(f)
        st.session_state.show_comment = False
        st.session_state.current_q = gerar_questao(st.session_state.reference_data)
    except Exception as e:
        st.error(f"Erro ao carregar referência ou gerar questão: {e}")

# Exibe questão se disponível
if st.session_state.current_q:
    q = st.session_state.current_q
    enun = q.get('enunciado') or q.get('question')
    st.markdown(f"<p class='question'><strong>Questão:</strong> {enun}</p>", unsafe_allow_html=True)
    alts = q.get('alternativas') or q.get('alternatives')
    options = list(alts.values())
    st.session_state.answer_selected = st.radio("Escolha uma alternativa:", options, key='answer')

    if not st.session_state.show_comment:
        if st.button("Enviar"):
            idx = options.index(st.session_state.answer_selected) + 1
            correct = q.get('correct_option') or q.get('correta')
            st.session_state.show_comment = True
            if idx == correct:
                st.success("Resposta correta!")
            else:
                st.error(f"Resposta incorreta. Correta: alternativa {correct}")
            st.markdown(f"<p>{q.get('commentary') or q.get('comentario')}</p>", unsafe_allow_html=True)
    else:
        if st.button("Próxima"):
            st.session_state.show_comment = False
            st.session_state.current_q = gerar_questao(st.session_state.reference_data)
    st.markdown("</div>", unsafe_allow_html=True)
