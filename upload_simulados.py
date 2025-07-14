import os
import json
import uuid
import gspread
import pandas as pd
import toml  # Biblioteca para ler o arquivo .toml
from pathlib import Path

# --- CONFIGURAÇÃO ---
# Caminho para a pasta onde estão seus arquivos JSON de simulados.
# O script assume que ele está na raiz do projeto "medstudent".
BASE_DIR = Path(__file__).parent
SIMULADOS_DIR = BASE_DIR / "simulados"
SECRETS_FILE_PATH = BASE_DIR / ".streamlit" / "secrets.toml"


# --- CONEXÃO COM GOOGLE SHEETS (MÉTODO SIMPLIFICADO) ---
def connect_to_google_sheets():
    """Conecta ao Google Sheets usando as credenciais do secrets.toml."""
    print("🔑 Lendo arquivo de segredos...")
    try:
        if not SECRETS_FILE_PATH.exists():
            raise FileNotFoundError(f"Arquivo de segredos não encontrado em: {SECRETS_FILE_PATH}")

        secrets = toml.load(SECRETS_FILE_PATH)
        
        creds_dict = dict(secrets["gcp_service_account"])
        sheet_name = secrets["gcs"]["sheet_name"]

        gc = gspread.service_account_from_dict(creds_dict)
        spreadsheet = gc.open(sheet_name)
        print("✅ Conectado com sucesso ao Google Sheets.")
        return spreadsheet.worksheet("questions")
    except FileNotFoundError as e:
        print(f"❌ Erro: {e}")
        print("Certifique-se de que o arquivo .streamlit/secrets.toml existe na raiz do seu projeto.")
        return None
    except Exception as e:
        print(f"❌ Erro fatal ao conectar com o Google Sheets: {e}")
        print("Verifique o conteúdo do seu arquivo .streamlit/secrets.toml.")
        return None

def upload_local_simulados():
    """
    Função principal que lê os JSONs locais e os envia para a planilha.
    """
    print("🚀 Iniciando script de upload de simulados...")
    
    questions_sheet = connect_to_google_sheets()
    if not questions_sheet:
        return # Encerra se a conexão falhar

    # 1. Obter todas as questões existentes para evitar duplicatas
    print("📊 Buscando questões existentes na planilha...")
    try:
        existing_questions_df = pd.DataFrame(questions_sheet.get_all_records())
        # Usamos um set para uma verificação de existência muito mais rápida
        existing_enunciados = set(existing_questions_df['enunciado']) if not existing_questions_df.empty else set()
        print(f"🔍 Encontradas {len(existing_enunciados)} questões existentes.")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível buscar questões existentes. Pode haver duplicatas. Erro: {e}")
        existing_enunciados = set()

    # 2. Ler todos os arquivos JSON da pasta de simulados
    if not SIMULADOS_DIR.exists():
        print(f"❌ A pasta de simulados não foi encontrada em: {SIMULADOS_DIR}")
        return
        
    json_files = list(SIMULADOS_DIR.glob('*.json'))
    if not json_files:
        print(f"❌ Nenhum arquivo .json encontrado na pasta: {SIMULADOS_DIR}")
        return

    print(f"\n📂 Encontrados {len(json_files)} arquivos JSON para processar.")

    new_questions_to_upload = []
    total_questions_in_files = 0

    for file_path in json_files:
        print(f"\n--- Processando arquivo: {file_path.name} ---")
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Erro de formatação no arquivo {file_path.name}. Pulando.")
                continue

            # O JSON pode ser um objeto único ou uma lista de objetos
            questions_in_file = data if isinstance(data, list) else [data]
            total_questions_in_files += len(questions_in_file)

            for question_data in questions_in_file:
                enunciado = question_data.get("enunciado")
                if not enunciado:
                    print("⚠️ Questão sem 'enunciado' encontrada. Pulando.")
                    continue

                # 3. Verificar se a questão já existe
                if enunciado in existing_enunciados:
                    print(f"🔵 Questão duplicada encontrada. Pulando: '{enunciado[:50]}...'")
                    continue
                
                # 4. Se for nova, preparar para o upload
                print(f"✨ Nova questão encontrada: '{enunciado[:50]}...'")
                
                # Formata a linha para o Google Sheets
                new_row = [
                    str(uuid.uuid4()),  # Gera um novo ID único
                    enunciado,
                    json.dumps(question_data.get("alternativas", {})),
                    json.dumps(question_data.get("comentarios", {})),
                    question_data.get("alternativa_correta", ""),
                    ", ".join(question_data.get("areas_principais", [])),
                    ", ".join(question_data.get("subtopicos", []))
                ]
                new_questions_to_upload.append(new_row)
                existing_enunciados.add(enunciado)

    # 5. Fazer o upload de todas as novas questões de uma vez
    if new_questions_to_upload:
        print(f"\n⬆️ Enviando {len(new_questions_to_upload)} novas questões para a planilha...")
        try:
            questions_sheet.append_rows(new_questions_to_upload, value_input_option='USER_ENTERED')
            print("✅ Upload concluído com sucesso!")
        except Exception as e:
            print(f"❌ Erro durante o upload em lote para o Google Sheets: {e}")
    else:
        print("\n✅ Nenhuma questão nova para adicionar.")

    # 6. Relatório Final
    print("\n--- Relatório Final ---")
    print(f"Arquivos JSON lidos: {len(json_files)}")
    print(f"Total de questões nos arquivos: {total_questions_in_files}")
    print(f"Novas questões adicionadas à planilha: {len(new_questions_to_upload)}")
    print("🏁 Script finalizado.")

if __name__ == "__main__":
    # Adiciona a dependência 'toml' se necessário. O Streamlit geralmente já a inclui.
    try:
        import toml
    except ImportError:
        print("Biblioteca 'toml' não encontrada. Instalando...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "toml"])

    upload_local_simulados()
