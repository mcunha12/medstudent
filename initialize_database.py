# initialize_database.py
import sqlite3
import pandas as pd
import os

DB_FILE = 'medstudent.db'
CSV_FILES = {
    'users.csv': 'users',
    'questions.csv': 'questions',
    'answers.csv': 'answers'
}

def create_tables(conn):
    """Cria as tabelas no banco de dados se elas não existirem."""
    cursor = conn.cursor()
    # Cria a tabela concepts com o schema correto
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS concepts (
        concept TEXT PRIMARY KEY,
        explanation TEXT,
        areas TEXT
    );
    """)
    print("Tabela 'concepts' verificada/criada.")
    conn.commit()

def sync_concepts(conn):
    """Sincroniza os conceitos da tabela 'questions' para a tabela 'concepts'."""
    print("Iniciando sincronização de conceitos...")
    
    # Gera a lista mestre de conceitos a partir das questões
    query = "SELECT areas_principais, subtopicos FROM questions"
    df = pd.read_sql_query(query, conn)
    
    if df.empty or 'subtopicos' not in df.columns:
        print("Tabela 'questions' vazia ou sem 'subtopicos'. Nenhum conceito para sincronizar.")
        return

    df.dropna(subset=['subtopicos'], inplace=True)
    df['subtopicos'] = df['subtopicos'].str.split(',')
    df['areas_principais'] = df['areas_principais'].fillna('').str.split(',')
    df = df.explode('subtopicos').explode('areas_principais')
    df['subtopicos'] = df['subtopicos'].str.strip()
    df['areas_principais'] = df['areas_principais'].str.strip()
    df.dropna(subset=['subtopicos', 'areas_principais'], inplace=True)
    df = df[df['subtopicos'] != '']
    df = df[df['areas_principais'] != '']
    
    concept_areas = df.groupby('subtopicos')['areas_principais'].apply(lambda x: ', '.join(sorted(x.unique()))).reset_index()
    concept_areas.rename(columns={'subtopicos': 'concept', 'areas_principais': 'areas'}, inplace=True)
    
    # Usa INSERT OR IGNORE para adicionar apenas os conceitos que não existem
    concept_areas.to_sql('concepts', conn, if_exists='append', index=False)
    print(f"Sincronização concluída. A tabela 'concepts' está atualizada.")


def main():
    # Deleta o banco antigo para garantir um começo limpo
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print(f"Banco de dados '{DB_FILE}' antigo removido.")

    conn = sqlite3.connect(DB_FILE)
    
    # Cria as tabelas CSV
    for csv_file, table_name in CSV_FILES.items():
        if os.path.exists(csv_file):
            pd.read_csv(csv_file).to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"Tabela '{table_name}' criada a partir de '{csv_file}'.")
        else:
            print(f"AVISO: '{csv_file}' não encontrado.")
    
    # Cria a tabela concepts vazia
    create_tables(conn)
    
    # Popula a tabela concepts com dados da tabela questions
    sync_concepts(conn)
    
    conn.close()
    print("\nBanco de dados inicializado com sucesso!")


if __name__ == "__main__":
    main()