import os
import json
import uuid
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


    if not supabase_url or not supabase_key or "SUA_CHAVE" in supabase_key:
        print("Erro Crítico: Verifique seu arquivo .env e a SUPABASE_SERVICE_KEY.")
        return

    try:
        supabase: Client = create_client(supabase_url, supabase_key)
        print("Conexão com o Supabase estabelecida com sucesso.")
    except Exception as e:
        print(f"Erro ao conectar com o Supabase: {e}")
        return

    try:
        print("Buscando dados existentes para evitar duplicatas...")
        # Busca tanto enunciados quanto IDs existentes
        response = supabase.table(TABLE_NAME).select("enunciado, question_id").execute()
        existing_enunciados = {item['enunciado'] for item in response.data if item.get('enunciado')}
        existing_ids = {item['question_id'] for item in response.data if item.get('question_id')}
        print(f"-> Encontrados {len(existing_enunciados)} enunciados e {len(existing_ids)} IDs no banco.")
    except Exception as e:
        print(f"Erro ao buscar dados existentes: {e}")
        return

    if not os.path.exists(SIMULADO_DIR):
        print(f"Erro: O diretório '{SIMULADO_DIR}' não foi encontrado.")
        return

    for filename in os.listdir(SIMULADO_DIR):
        if filename.endswith('.json'):
            file_path = os.path.join(SIMULADO_DIR, filename)
            print(f"\n----------------------------------------------------")
            print(f"Processando arquivo: {filename}...")

            try:
                prova_name = get_prova_from_filename(filename)
                print(f"-> Prova identificada: {prova_name}")

                with open(file_path, 'r', encoding='utf-8') as f:
                    questions_from_json = json.load(f)

                if not isinstance(questions_from_json, list):
                    questions_from_json = [questions_from_json]
                
                print(f"   -> Total de questões encontradas no arquivo: {len(questions_from_json)}")

                questions_to_upload = []
                skipped_enunciado_count = 0
                
                for q_json in questions_from_json:
                    enunciado = q_json.get('enunciado')

                    # 1. Critério principal: Pular se o ENUNCIADO já existir
                    if enunciado in existing_enunciados:
                        skipped_enunciado_count += 1
                        continue
                    
                    # 2. Lógica para garantir a unicidade do ID
                    question_id = q_json.get('id')
                    
                    # Se o ID não existir no JSON, ou se já existir no banco, gera um novo.
                    if not question_id or question_id in existing_ids:
                        new_id = str(uuid.uuid4())
                        print(f"   -> ID '{question_id}' já existe ou é nulo. Gerando um novo: {new_id}")
                        question_id = new_id
                    
                    # Adiciona o novo ID à lista de existentes para evitar colisões na mesma execução
                    existing_ids.add(question_id)

                    q_db = {
                        'question_id': question_id,
                        'enunciado': enunciado,
                        'alternativas': q_json.get('alternativas'),
                        'comentarios': q_json.get('comentarios'),
                        'alternativa_correta': q_json.get('alternativa_correta'),
                        'areas_principais': q_json.get('areas_principais'),
                        'subtopicos': q_json.get('subtopicos'),
                        'createdat': q_json.get('createdAt'),
                        'prova': prova_name
                    }
                    questions_to_upload.append(q_db)

                if skipped_enunciado_count > 0:
                    print(f"   -> {skipped_enunciado_count} questões puladas (enunciado já existe no banco).")

                if not questions_to_upload:
                    print(f"   -> Nenhuma questão nova para enviar neste arquivo.")
                    continue

                print(f"   -> Enviando {len(questions_to_upload)} novas questões para a tabela '{TABLE_NAME}'...")
                # Usamos 'insert' pois garantimos a unicidade do ID e do enunciado manualmente
                response = supabase.table(TABLE_NAME).insert(questions_to_upload).execute()

                if hasattr(response, 'error') and response.error:
                    print(f"   -> Erro ao enviar dados: {response.error}")
                else:
                    print(f"   -> Sucesso! Operação concluída para {filename}.")
                    # Atualiza a lista de enunciados para a próxima iteração
                    for q in questions_to_upload:
                        existing_enunciados.add(q['enunciado'])

            except json.JSONDecodeError:
                print(f"   -> ERRO: O arquivo '{filename}' não é um JSON válido.")
            except Exception as e:
                print(f"   -> ERRO INESPERADO: {e}")

    print("\nScript finalizado!")

if __name__ == "__main__":
    main()