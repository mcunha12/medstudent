# update_db.py
import sqlite3

DB_FILE = 'medstudent.db'
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

try:
    # Adiciona a coluna 'areas' à tabela 'concepts' se ela não existir
    cursor.execute("ALTER TABLE concepts ADD COLUMN areas TEXT;")
    print("Coluna 'areas' adicionada com sucesso à tabela 'concepts'.")
except sqlite3.OperationalError as e:
    # O erro "duplicate column name" é esperado se você rodar o script mais de uma vez
    if "duplicate column name" in str(e):
        print("Coluna 'areas' já existe na tabela 'concepts'. Nenhuma alteração necessária.")
    else:
        raise e

conn.commit()
conn.close()