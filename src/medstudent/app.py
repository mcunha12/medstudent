import streamlit as st

# Configuração da página
st.set_page_config(page_title="MedStudentAI", layout="wide", page_icon="🏠")

# CSS global para a home
st.markdown(
    """
    <style>
      .welcome-container { display: flex; flex-direction: column; align-items: center; padding: 2rem; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen; color: #1C1C1E; }
      .feature-card { background: #FFF; border-radius: 16px; padding: 24px; margin: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.05); width: 80%; max-width: 400px; }
      .feature-card h2 { font-size: 22px; margin-bottom: 8px; }
      .feature-card p { font-size: 16px; color: #636366; margin-bottom: 0; }
    </style>
    """,
    unsafe_allow_html=True
)

# Conteúdo da Home
st.markdown("<div class='welcome-container'>", unsafe_allow_html=True)

st.markdown("<h1>Bem-vindo ao MedStudentAI</h1>", unsafe_allow_html=True)
st.markdown("<p>Explore as principais funcionalidades para auxiliar seus estudos de medicina.</p>", unsafe_allow_html=True)

# Cartão de Simulado
st.markdown(
    "<div class='feature-card'>"
    "<h2>📝 Simulado Dinâmico</h2>"
    "<p>Gerar questões de múltipla escolha com base em simulados de referência.</p>"
    "<p>Resposta imediata e explicativa para cada questão.</p>"
    "</div>",
    unsafe_allow_html=True
)

# Cartão de Posologia
st.markdown(
    "<div class='feature-card'>"
    "<h2>💊 Calculadora de Posologia</h2>"
    "<p>Calcule doses de medicamentos com base em peso, idade e concentração.</p>"
    "<p>Receba insights clínicos personalizados para melhorar o aprendizado.</p>"
    "</div>",
    unsafe_allow_html=True
)

st.markdown("</div>", unsafe_allow_html=True)
