import streamlit as st
import json
# Importa apenas o 'model' do Gemini do nosso arquivo de serviços
from services import model

# --- VERIFICAÇÃO DE LOGIN ---
# Garante que o usuário esteja logado para usar a ferramenta.
if 'user_id' not in st.session_state or not st.session_state.user_id:
    st.warning("Por favor, faça o login na Home para acessar a calculadora.")
    st.page_link("Home.py", label="Voltar para a Home", icon="🏠")
    st.stop()

# --- CONFIGURAÇÃO E ESTILO DA PÁGINA ---
# O st.set_page_config() foi removido, pois ele só pode ser chamado uma vez
# no arquivo principal (Home.py). As outras páginas herdam a configuração.

st.title("💊 Calculadora de Posologia")
st.markdown("---")

# CSS para um estilo mais limpo e profissional
st.markdown(
    """
    <style>
      .st-emotion-cache-z5fcl4 { padding-top: 2rem; }
      .st-emotion-cache-1y4p8pa { padding-top: 2rem; }
      .st-form {
          background: white;
          border-radius: 12px;
          padding: 24px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.05);
      }
      .stButton>button {
          background-color: #007AFF;
          color: white;
          border: none;
          border-radius: 10px;
          padding: 12px 20px;
          font-size: 16px;
          font-weight: 600;
          width: 100%;
          margin-top: 16px;
      }
      .result-card {
          background-color: #EFEFEF;
          border-left: 5px solid #007AFF;
          padding: 16px;
          border-radius: 8px;
          margin-top: 16px;
      }
      .result-card h3 {
          margin-top: 0;
          color: #1C1C1E;
      }
      .result-card p {
          font-size: 18px;
          font-weight: 500;
          color: #1C1C1E;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# --- FORMULÁRIO PRINCIPAL ---
with st.form(key='posologia_form'):
    st.subheader("Dados do Paciente e Medicação")
    
    # Usando colunas para um layout mais organizado
    col1, col2 = st.columns(2)
    with col1:
        med_name = st.text_input("Medicamento", placeholder="Ex: Amoxicilina")
        weight_str = st.text_input("Peso (kg)", placeholder="Ex: 15.5")
        age_str = st.text_input("Idade (anos)", placeholder="Ex: 4")
    with col2:
        dosage_str = st.text_input("Dosagem (mg/kg)", placeholder="Ex: 50")
        interval_str = st.text_input("Intervalo (horas)", placeholder="Ex: 8")
        concentration_str = st.text_input("Concentração (mg/mL)", placeholder="Ex: 250")

    comorbidities = st.text_area(
        "Comorbidades e especificidades",
        placeholder="Ex: Insuficiência renal, hipertensão, diabetes, alergia a penicilina..."
    )
    
    submit_button = st.form_submit_button(label="Calcular e Gerar Relatório")

# --- PROCESSAMENTO APÓS ENVIO ---
if submit_button:
    # Validação dos campos
    required_fields = [med_name, weight_str, age_str, dosage_str, interval_str, concentration_str]
    if not all(required_fields):
        st.error("Por favor, preencha todos os campos obrigatórios.")
        st.stop()
    
    # Conversão dos valores com tratamento de erro
    try:
        weight = float(weight_str)
        age = int(age_str)
        dosage_mgkg = float(dosage_str)
        interval_hours = int(interval_str)
        concentration = float(concentration_str)
    except ValueError:
        st.error("Por favor, insira valores numéricos válidos para peso, idade, dosagem, intervalo e concentração.")
        st.stop()

    # --- CÁLCULO DA DOSE ---
    st.subheader("Resultado do Cálculo")
    if concentration > 0:
        total_mg_dose = weight * dosage_mgkg
        dose_ml = total_mg_dose / concentration
        
        st.markdown(f"""
        <div class="result-card">
            <h3>Dose Calculada:</h3>
            <p>{dose_ml:.2f} mL a cada {interval_hours} horas.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("A concentração deve ser maior que zero para calcular a dose em mL.")

    # --- CHAMADA À IA (GEMINI) ---
    st.subheader("Relatório Educacional MedStudentAI")
    with st.spinner("Gerando insights clínicos com a IA..."):
        # Preparação do prompt para o Gemini
        data_for_ai = {
            "medicamento": med_name,
            "peso_kg": weight,
            "idade_anos": age,
            "dosagem_mg_por_kg": dosage_mgkg,
            "intervalo_horas": interval_hours,
            "concentracao_mg_por_ml": concentration,
            "comorbidades_e_especificidades": comorbidities or "Nenhuma informada"
        }
        prompt = (
            f"Você é um médico sênior e educador, respondendo a uma estudante de medicina. "
            f"Com base nos seguintes dados de um caso hipotético: {json.dumps(data_for_ai, ensure_ascii=False)}. "
            "Gere um relatório educacional sucinto e direto. Foque nos seguintes pontos:\n"
            "1. **Análise Clínica:** Como as comorbidades informadas (ou a ausência delas) impactam a escolha ou a posologia deste medicamento? Quais cuidados são necessários?\n"
            "2. **Contexto Prático:** Se for um medicamento comum, crie um breve exemplo de cenário clínico onde essa prescrição seria típica. Ex: 'Imagine um paciente chegando ao PS com...'.\n"
            "3. **Pontos de Atenção:** Mencione 1 ou 2 'red flags' ou efeitos adversos importantes que a estudante deve monitorar.\n\n"
            "**Instruções de Formato:**\n"
            "- Use um tom amigável e instrutivo.\n"
            "- Não repita o cálculo da dose, apenas a análise clínica.\n"
            "- Use negrito para destacar termos importantes.\n"
            "- A resposta deve ser apenas o relatório, sem introduções como 'Olá, Yasmin' ou 'Aqui está o relatório'."
        )

        try:
            # Usa o modelo Gemini importado de services.py
            response = model.generate_content(prompt)
            ai_report = response.text
            st.markdown(ai_report)
        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o relatório da IA: {e}")
