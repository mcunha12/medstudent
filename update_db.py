# update_db.py
import sqlite3

DB_FILE = 'medstudent.db'
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

try:
    # Cria a nova tabela para os conceitos gerados pela IA
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ai_concepts (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        explanation TEXT NOT NULL,
        users TEXT,
        created_at TEXT NOT NULL
    );
    """)
    print("Tabela 'ai_concepts' verificada/criada com sucesso.")
except Exception as e:
    print(f"Ocorreu um erro: {e}")

conn.commit()
conn.close()
print("Processo concluído.")

#   