import os
import json
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis de ambiente (SUPABASE_URL e SUPABASE_SERVICE_KEY) do arquivo .env
load_dotenv()

# --- Configuração ---
SIMULADO_DIR = 'simulados' # Nome do diretório onde estão os JSONs
TABLE_NAME = 'questions' # Nome da tabela no Supabase

# Função para extrair o nome da "prova" do nome do arquivo
def get_prova_from_filename(filename: str) -> str:
    """
    Extrai o nome da prova do nome do arquivo.
    Regra: Pega tudo antes do segundo hífen. Se não houver segundo hífen,
    pega tudo antes do primeiro.
    Ex: 'sus-ba-clinica-medica.json' -> 'sus-ba'
    Ex: 'enade-2023.json' -> 'enade'
    """
    base_name = filename.replace('.json', '')
    parts = base_name.split('-')
    if len(parts) > 2:
        return f"{parts[0]}-{parts[1]}"
    return parts[0]

def main():
    """
    Função principal para ler os arquivos JSON e enviá-los ao Supabase.
    """
    print("Iniciando o script de atualização do banco de dados...")

    # Validação das variáveis de ambiente
    supabase_url = "https://gupeyvxderpzflctfbxg.supabase.co"
    supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd1cGV5dnhkZXJwemZsY3RmYnhnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTMzOTIwNzIsImV4cCI6MjA2ODk2ODA3Mn0.AavDJvloqg8ydJT3kAKOvPQ2Vc6nOZt7Lx5Hd_xfpKw"

    if not supabase_url or not supabase_key:
        print("Erro: As variáveis de ambiente SUPABASE_URL e SUPABASE_SERVICE_KEY não foram definidas.")
        print("Verifique se você criou e preencheu o arquivo .env corretamente.")
        return

    # Conexão com o Supabase
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Conexão com o Supabase estabelecida com sucesso.")
    except Exception as e:
        print(f"Erro ao conectar com o Supabase: {e}")
        return

    if not os.path.exists(SIMULADO_DIR):
        print(f"Erro: O diretório '{SIMULADO_DIR}' não foi encontrado.")
        return

    # Itera sobre todos os arquivos no diretório
    for filename in os.listdir(SIMULADO_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(SIMULADO_DIR, filename)
            print(f"\nProcessando arquivo: {filename}...")

            try:
                prova_name = get_prova_from_filename(filename)
                print(f"-> Prova identificada: {prova_name}")

                with open(file_path, 'r', encoding='utf-8') as f:
                    questions_from_json = json.load(f)

                if not isinstance(questions_from_json, list):
                    print(f"   -> Erro de formato: O conteúdo de '{filename}' não é uma lista. Pulando.")
                    continue

                # Lista para armazenar as questões com o schema corrigido
                questions_to_upload = []

                # Mapeia os campos do JSON para o schema do banco de dados
                for q_json in questions_from_json:
                    q_db = {
                        # Mapeamento dos campos
                        'question_id': q_json.get('id'),
                        'enunciado': q_json.get('enunciado'),
                        'alternativas': q_json.get('alternativas'),
                        'comentarios': q_json.get('comentarios'),
                        'alternativa_correta': q_json.get('alternativa_correta'),
                        'areas_principais': q_json.get('areas_principais'),
                        'subtopicos': q_json.get('subtopicos'),
                        'createdat': q_json.get('createdAt'), # Corrigindo o nome do campo
                        
                        # Adiciona o campo "prova" extraído do nome do arquivo
                        'prova': prova_name
                    }
                    
                    # Garante que questões sem ID não sejam enviadas
                    if q_db['question_id'] is None:
                        print(f"   -> Aviso: Questão sem 'id' encontrada no arquivo {filename}. Pulando esta questão.")
                        continue
                        
                    questions_to_upload.append(q_db)

                if not questions_to_upload:
                    print(f"   -> Nenhuma questão válida para enviar no arquivo {filename}.")
                    continue

                # Envia os dados para o Supabase usando 'upsert'
                # O on_conflict é inferido pela chave primária 'question_id'
                print(f"   -> Enviando {len(questions_to_upload)} questões para a tabela '{TABLE_NAME}'...")
                response = supabase.table(TABLE_NAME).upsert(questions_to_upload, on_conflict='question_id').execute()

                if hasattr(response, 'error') and response.error:
                    print(f"   -> Erro ao enviar dados: {response.error}")
                else:
                    print(f"   -> Sucesso! Operação concluída para {filename}.")

            except json.JSONDecodeError:
                print(f"   -> Erro de leitura: O arquivo '{filename}' não é um JSON válido. Pulando.")
            except Exception as e:
                print(f"   -> Ocorreu um erro inesperado ao processar '{filename}': {e}")

    print("\nScript finalizado!")

if __name__ == "__main__":
    main()