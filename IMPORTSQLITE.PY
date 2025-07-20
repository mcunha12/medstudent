# setup_database.py
import sqlite3
import pandas as pd
import os

# Nomes dos arquivos CSV e tabelas correspondentes
CSV_FILES = {
    'users.csv': 'users',
    'questions.csv': 'questions',
    'answers.csv': 'answers',
    'concepts.csv': 'concepts'
}

DB_FILE = 'medstudent.db'

# Deleta o banco de dados antigo, se existir, para começar do zero
if os.path.exists(DB_FILE):
    os.remove(DB_FILE)
    print(f"Banco de dados '{DB_FILE}' antigo removido.")

# Conecta ao banco de dados (ele será criado se não existir)
conn = sqlite3.connect(DB_FILE)
print(f"Banco de dados '{DB_FILE}' criado com sucesso.")

# Itera sobre os arquivos CSV e os carrega para o banco de dados
for csv_file, table_name in CSV_FILES.items():
    if os.path.exists(csv_file):
        try:
            df = pd.read_csv(csv_file)
            # Converte colunas que podem ser JSON para texto
            if table_name == 'questions':
                if 'alternativas' in df.columns:
                    df['alternativas'] = df['alternativas'].astype(str)
                if 'comentarios' in df.columns:
                    df['comentarios'] = df['comentarios'].astype(str)

            df.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"Arquivo '{csv_file}' carregado com sucesso para a tabela '{table_name}'.")
        except Exception as e:
            print(f"Erro ao processar o arquivo '{csv_file}': {e}")
    else:
        print(f"AVISO: Arquivo '{csv_file}' não encontrado. A tabela '{table_name}' não foi criada.")

# Fecha a conexão
conn.close()
print("Processo concluído. O banco de dados está pronto para ser usado.")