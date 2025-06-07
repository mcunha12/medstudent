import streamlit as st
import importlib.util
from pathlib import Path

# Configuração da página
st.set_page_config(page_title="MedStudentAI", layout="wide", page_icon="🏠")

# CSS global para a home
st.markdown(
    """
    <style>
      .home-title { font-size:32px; font-weight:600; color:#1C1C1E; margin-top:1rem; }
      .home-subtitle { font-size:18px; color:#636366; margin-bottom:2rem; }
      .feature-card { background:#FFF; border-radius:12px; padding:24px; margin:12px 0; box-shadow:0 4px 12px rgba(0,0,0,0.05); }
      .feature-card h3 { margin:0; font-size:20px; }
      .feature-card p { margin:8px 0 0; color:#636366; }
    </style>
    """, unsafe_allow_html=True)

# Carrega módulo Python dinamicamente a partir de um arquivo

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Define caminhos
BASE_DIR = Path(__file__).resolve().parent
PAGES_DIR = BASE_DIR / "pages"
SIMULADO_PATH = PAGES_DIR / "1_Simulado.py"
POSOLOGIA_PATH = PAGES_DIR / "2_Posologia.py"

# Navegação lateral
tab = st.sidebar.selectbox("Selecione uma funcionalidade:", ["Home", "Simulado", "Posologia"])

if tab == "Home":
    st.markdown("<div style='max-width:600px; margin:auto;'>", unsafe_allow_html=True)
    st.markdown("<p class='home-title'>Bem-vindo ao MedStudentAI</p>", unsafe_allow_html=True)
    st.markdown("<p class='home-subtitle'>Escolha uma ferramenta no menu lateral para começar:</p>", unsafe_allow_html=True)
    st.markdown(
        "<div class='feature-card'><h3>📝 Simulado Dinâmico</h3>"
        "<p>Gere questões de múltipla escolha e receba feedback imediato com explicações.</p></div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div class='feature-card'><h3>💊 Calculadora de Posologia</h3>"
        "<p>Calcule doses e receba insights clínicos baseados nos dados do paciente.</p></div>",
        unsafe_allow_html=True
    )

elif tab == "Simulado":
    if SIMULADO_PATH.exists():
        sim_mod = load_module(SIMULADO_PATH, "simulado")
        if hasattr(sim_mod, 'main'):
            sim_mod.main()
        else:
            st.error("Função main() não encontrada em 1_Simulado.py")
    else:
        st.error("Arquivo 1_Simulado.py não encontrado.")

elif tab == "Posologia":
    if POSOLOGIA_PATH.exists():
        pos_mod = load_module(POSOLOGIA_PATH, "posologia")
        if hasattr(pos_mod, 'main'):
            pos_mod.main()
        else:
            st.error("Função main() não encontrada em 2_Posologia.py")
    else:
        st.error("Arquivo 2_Posologia.py não encontrado.")
