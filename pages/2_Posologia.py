# ==============================================================================
# ARQUIVO 4: pages/2_Posologia.py (QUASE INALTERADO)
# Mova seu arquivo de Posologia para dentro da pasta "pages".
# Apenas adicionamos a verificação de login para consistência.
# ==============================================================================
import streamlit as st
import requests
import json

# VERIFICA LOGIN
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a calculadora.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# O restante do seu código da página de Posologia continua aqui...
# ... (copie e cole o código original da sua página de Posologia aqui)
# Configuração da página
st.set_page_config(page_title="Posologia", layout="centered", page_icon="💊")

# CSS global para estilo clean Apple-like
st.markdown(
    """
    <style>
      body { background-color: #F5F5F7; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen; }
      .st-emotion-cache-z5fcl4 { padding-top: 2rem; }
      .section-card { background: #FFFFFF; border-radius: 16px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 16px rgba(0,0,0,0.05); }
      h1 { font-size: 28px; font-weight: 600; color: #1C1C1E; margin-bottom: 4px; }
      h1 + p { font-size: 14px; color: #636366; margin-top: 0; }
      label { font-size: 16px; font-weight: 500; color: #1C1C1E; margin-bottom: 8px; display: block; }
      input, textarea { border: 1px solid #D1D1D6; border-radius: 12px; padding: 12px; font-size: 16px; width: 100%; box-sizing: border-box; margin-bottom: 16px; }
      .stButton>button { background-color: #007AFF; color: #FFFFFF; border: none; border-radius: 12px; padding: 12px; font-size: 17px; font-weight: 600; width: 100%; margin-top: 8px; }
      .stSpinner>div>div { border-top-color: #007AFF !important; }
      .result { font-size: 22px; font-weight: 600; color: #E63946; margin-bottom: 0; }
    </style>
    """,
    unsafe_allow_html=True
)
st.title("💊 Calculadora de Posologia")

# Formulário principal
with st.form(key='posologia_form'):
    med_name = st.text_input("Medicamento", value="", placeholder="Ex: Amoxicilina", key='med_name')
    weight_str = st.text_input("Peso (kg)", value="", placeholder="0.0", key='weight_str')
    age_str = st.text_input("Idade (anos)", value="", placeholder="0", key='age_str')
    dosage_str = st.text_input("Dosagem (mg/kg)", value="", placeholder="0.0", key='dosage_str')
    interval_str = st.text_input("Intervalo (horas)", value="", placeholder="1", key='interval_str')
    concentration_str = st.text_input("Concentração (mg/mL)", value="", placeholder="0.0", key='concentration_str')
    # comorbidities = st.text_area("Comorbidades e especificidades", value="", placeholder="Ex: hipertensão, diabetes", key='comorbidities')
    submit = st.form_submit_button("Enviar")

# Processamento após envio
if submit:
    # Conversão dos valores
    try:
        weight = float(st.session_state.weight_str)
        age = int(st.session_state.age_str)
        dosage_mgkg = float(st.session_state.dosage_str)
        interval_hours = int(st.session_state.interval_str)
        concentration = float(st.session_state.concentration_str)
    except Exception:
        st.error("Por favor, preencha todos os campos numéricos corretamente.")
        st.stop()

    # Cálculo da dose
    dose_ml = None
    if concentration > 0:
        total_mg = weight * dosage_mgkg
        dose_ml = total_mg / concentration

    # Dados para IA e prompt
    data = {
        "med_name": med_name,
        "weight": weight,
        "age": age,
        "dosage_mgkg": dosage_mgkg,
        "interval_hours": interval_hours,
        "concentration": concentration,
        # "comorbidities": comorbidities
    }
    system_prompt = (
        f"Você é um médico educador. Use estes dados: {json.dumps(data, ensure_ascii=False)}  "
        "Responda diretamente a um estudante de medicina, explicando:\n"
        "1. Como a comorbidade afeta a posologia deste medicamento.\n"
        "2. Se for um medicamento de alta relevância, inclua um exemplo de situação-problema comum na prática médica; caso contrário, restrinja-se ao caso fornecido.\n\n"
        "3. Não precisa falar sobre a dosagem para esse caso específico pois já foi calculado previamente. Isso nao precisa ser dito na resposta."
        "4. Seja sucinto e direto ao ponto que importa"
        "Retorne apenas a resposta ao estudante, em tom amigável e instrutivo."
    )

    # Exibição dos resultados
    st.markdown("**Resultado da Posologia**")
    if dose_ml is not None:
        st.markdown(
            f"<p>O paciente deve tomar {dose_ml:.2f} mL a cada {interval_hours} horas</p>",
            unsafe_allow_html=True
        )
    else:
        st.warning("Concentração deve ser maior que zero para calcular a dose.")


    # Chamada à IA com tratamento de erros de rede

    # Chamada à IA com tratamento de URL inválida, conexão e timeout
    st.markdown("**Relatório MedStudentAI**")
    with st.spinner("MedStudentAI está gerando o relatório..."):
        # Carrega e valida o URL
        openrouter_url = st.secrets.get("OPENROUTER_URL", "").strip()
        if openrouter_url and not openrouter_url.startswith(("http://", "https://")):
            openrouter_url = "https://" + openrouter_url

        api_key = st.secrets.get("OPENROUTER_API_KEY", "").strip()
        model   = st.secrets.get("MODEL", "").strip()

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt}
            ]
        }

        # try:
        #     resp = requests.post(openrouter_url, headers=headers, json=body, timeout=10)
        #     resp.raise_for_status()
        #     ai_report = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        # except requests.exceptions.InvalidURL:
        #     ai_report = "URL inválida: verifique o OPENROUTER_URL em secrets.toml."
        # except requests.exceptions.ConnectionError:
        #     ai_report = "Não foi possível conectar ao servidor de IA. Verifique sua conexão e as configurações em secrets.toml."
        # except requests.exceptions.Timeout:
        #     ai_report = "A requisição ao servidor de IA expirou. Tente novamente mais tarde."
        # except Exception as e:
        #     ai_report = f"Erro ao gerar relatório de IA: {e}"

    # st.markdown(ai_report)

