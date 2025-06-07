import streamlit as st
from pathlib import Path
import importlib.util

# Configuração da página
st.set_page_config(page_title="MedStudentAI", layout="wide", page_icon="🏠")

# Carrega módulo Python a partir de caminho

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Localização dos arquivos de feature
dir_pages = Path(__file__).resolve().parent / "pages"
simulado_file = dir_pages / "1_Simulado.py"
posologia_file = dir_pages / "2_Posologia.py"

# Navegação lateral
tab = st.sidebar.selectbox("Selecione uma funcionalidade:", ["Home", "Simulado", "Posologia"])

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

if tab == "Home":
    st.markdown("<div style='max-width:600px; margin:auto;'>", unsafe_allow_html=True)
    st.markdown("<p class='home-title'>Bem-vindo ao MedStudentAI</p>", unsafe_allow_html=True)
    st.markdown("<p class='home-subtitle'>Escolha uma ferramenta no menu lateral para começar:</p>", unsafe_allow_html=True)
    
    st.markdown(
        "<div class='feature-card'>"
        "<h3>📝 Simulado Dinâmico</h3>"
        "<p>Gere questões de múltipla escolha e receba feedback imediato com explicações.</p>"
        "</div>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<div class='feature-card'>"
        "<h3>💊 Calculadora de Posologia</h3>"
        "<p>Calcule doses e receba insights clínicos baseados nos dados do paciente.</p>"
        "</div>",
        unsafe_allow_html=True
    )

elif tab == "Simulado":
    if simulado_file.exists():
        sim_mod = load_module("simulado", simulado_file)
        sim_mod.main()
    else:
        st.error("Arquivo de simulado não encontrado em pages/1_Simulado.py")

elif tab == "Posologia":
    if posologia_file.exists():
        pos_mod = load_module("posologia", posologia_file)
        pos_mod.main()
    else:
        st.error("Arquivo de posologia não encontrado em pages/2_Posologia.py")
