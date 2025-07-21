import os
import json
import uuid
import pandas as pd
import toml
from pathlib import Path

# --- CONFIGURAÇÃO ---
BASE_DIR = Path(__file__).parent
SIMULADOS_DIR = BASE_DIR / "simulados"
SECRETS_FILE_PATH = BASE_DIR / ".streamlit" / "secrets.toml"


# --- CONEXÃO COM GOOGLE SHEETS ---
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
    except Exception as e:
        print(f"❌ Erro fatal ao conectar com o Google Sheets: {e}")
        return None

def are_fields_different(json_question, sheet_question, prova_name):
    """
    Compara uma questão do arquivo JSON com uma da planilha para ver se há diferenças.
    """
    if prova_name != sheet_question.get("prova", ""): return True
    if json_question.get("alternativa_correta", "") != sheet_question.get("alternativa_correta", ""): return True
    if ", ".join(json_question.get("areas_principais", [])) != sheet_question.get("areas_principais", ""): return True
    if ", ".join(json_question.get("subtopicos", [])) != sheet_question.get("subtopicos", ""): return True

    try:
        json_alternativas = json_question.get("alternativas", {})
        sheet_alternativas = json.loads(sheet_question.get("alternativas", '{}'))
        if json_alternativas != sheet_alternativas: return True

        json_comentarios = json_question.get("comentarios", {})
        sheet_comentarios = json.loads(sheet_question.get("comentarios", '{}'))
        if json_comentarios != sheet_comentarios: return True
    except (json.JSONDecodeError, TypeError):
        return True

    return False

def upload_local_simulados():
    """
    Função principal que lê os JSONs locais e os envia para a planilha,
    atualizando questões existentes se necessário.
    """
    print("🚀 Iniciando script de sincronização de simulados...")
    
    questions_sheet = connect_to_google_sheets()
    if not questions_sheet:
        return

    print("📊 Buscando e mapeando questões existentes na planilha...")
    try:
        all_records = questions_sheet.get_all_records()
        existing_questions_map = {record['enunciado']: {'data': record, 'index': i + 2} for i, record in enumerate(all_records)}
        print(f"🔍 Encontradas e mapeadas {len(existing_questions_map)} questões existentes.")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível buscar questões existentes. Erro: {e}")
        existing_questions_map = {}

    if not SIMULADOS_DIR.exists():
        print(f"❌ A pasta de simulados não foi encontrada em: {SIMULADOS_DIR}")
        return
        
    json_files = list(SIMULADOS_DIR.glob('*.json'))
    if not json_files:
        print(f"❌ Nenhum arquivo .json encontrado na pasta: {SIMULADOS_DIR}")
        return

    print(f"\n📂 Encontrados {len(json_files)} arquivos JSON para processar.")

    new_questions_to_upload = []
    questions_to_update = []
    total_questions_in_files = 0
    questions_identical = 0

    # --- INÍCIO DA CORREÇÃO ---
    # Usaremos um conjunto para rastrear enunciados já processados nesta execução
    processed_in_this_run = set()
    # --- FIM DA CORREÇÃO ---

    for file_path in json_files:
        print(f"\n--- Processando arquivo: {file_path.name} ---")
        
        filename_stem = file_path.stem
        try:
            first_hyphen = filename_stem.find('-')
            second_hyphen = filename_stem.find('-', first_hyphen + 1) if first_hyphen != -1 else -1
            prova_name = filename_stem[:second_hyphen] if second_hyphen != -1 else filename_stem
            print(f"📝 Nome da prova extraído: '{prova_name}'")
        except Exception:
            prova_name = "N/A"
            print(f"⚠️ Não foi possível extrair o nome da prova de '{filename_stem}'. Usando 'N/A'.")
        
        # Corrigindo a leitura do JSON para garantir que é um arquivo válido
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ ERRO FATAL: O arquivo {file_path.name} não é um JSON válido e não pode ser processado.")
            continue # Pula para o próximo arquivo

        questions_in_file = data if isinstance(data, list) else [data]
        total_questions_in_files += len(questions_in_file)

        for question_data in questions_in_file:
            if isinstance(question_data, list):
                if not question_data:
                    print("⚠️ Encontrada lista de questão vazia. Pulando.")
                    continue
                question_data = question_data[0]

            if not isinstance(question_data, dict):
                print(f"⚠️ Item inesperado encontrado que não é um dicionário. Pulando. Item: {question_data}")
                continue

            enunciado = question_data.get("enunciado")
            if not enunciado:
                print("⚠️ Questão sem 'enunciado' encontrada. Pulando.")
                continue

            # --- INÍCIO DA CORREÇÃO DE LÓGICA ---
            # Primeiro, verifica se já processamos essa questão (duplicada local)
            if enunciado in processed_in_this_run:
                print(f" duplicates️ Questão duplicada neste lote de arquivos. Pulando: '{enunciado[:50]}...'")
                continue
            # --- FIM DA CORREÇÃO DE LÓGICA ---
            
            if enunciado in existing_questions_map:
                existing_record = existing_questions_map[enunciado]
                if are_fields_different(question_data, existing_record['data'], prova_name):
                    print(f"🔄 Conteúdo diferente detectado. Agendando atualização para: '{enunciado[:50]}...'")
                    question_id = existing_record['data'].get('question_id')
                    
                    full_row_values = [
                        question_id,
                        enunciado,
                        json.dumps(question_data.get("alternativas", {})),
                        json.dumps(question_data.get("comentarios", {})),
                        question_data.get("alternativa_correta", ""),
                        ", ".join(question_data.get("areas_principais", [])),
                        ", ".join(question_data.get("subtopicos", [])),
                        prova_name 
                    ]
                    questions_to_update.append({
                        'range': f"A{existing_record['index']}:H{existing_record['index']}",
                        'values': [full_row_values]
                    })
                else:
                    print(f"👌 Conteúdo idêntico. Pulando: '{enunciado[:50]}...'")
                    questions_identical += 1
            else:
                print(f"✨ Nova questão encontrada. Agendando adição: '{enunciado[:50]}...'")
                question_id = str(uuid.uuid4())
                
                new_questions_to_upload.append([
                    question_id,
                    enunciado,
                    json.dumps(question_data.get("alternativas", {})),
                    json.dumps(question_data.get("comentarios", {})),
                    question_data.get("alternativa_correta", ""),
                    ", ".join(question_data.get("areas_principais", [])),
                    ", ".join(question_data.get("subtopicos", [])),
                    prova_name
                ])
            
            # Marca o enunciado como processado para esta execução
            processed_in_this_run.add(enunciado)

    if questions_to_update:
        print(f"\n⏳ Atualizando {len(questions_to_update)} questões existentes na planilha...")
        try:
            questions_sheet.batch_update(questions_to_update)
            print("✅ Atualizações concluídas com sucesso!")
        except Exception as e:
            print(f"❌ Erro durante a atualização em lote: {e}")
    
    if new_questions_to_upload:
        print(f"\n⬆️ Adicionando {len(new_questions_to_upload)} novas questões à planilha...")
        try:
            questions_sheet.append_rows(new_questions_to_upload, value_input_option='USER_ENTERED')
            print("✅ Novas questões adicionadas com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao adicionar novas questões: {e}")

    if not questions_to_update and not new_questions_to_upload:
        print("\n✅ Nenhuma alteração necessária. A planilha já está sincronizada.")

    print("\n--- Relatório Final da Sincronização ---")
    print(f"Arquivos JSON lidos: {len(json_files)}")
    print(f"Total de questões nos arquivos: {total_questions_in_files}")
    print(f"Novas questões adicionadas: {len(new_questions_to_upload)}")
    print(f"Questões existentes atualizadas: {len(questions_to_update)}")
    print(f"Questões existentes sem alterações: {questions_identical}")
    print("🏁 Script finalizado.")

if __name__ == "__main__":
    try:
        import toml
    except ImportError:
        print("Biblioteca 'toml' não encontrada. Instalando...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "toml"])

    upload_local_simulados()