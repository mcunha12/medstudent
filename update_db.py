import sqlite3

def delete_table():
    # Conecta ao banco de dados medstudent.db na mesma pasta
    conn = sqlite3.connect('medstudent.db')
    cursor = conn.cursor()

    # Deleta a tabela concepts se ela existir
    cursor.execute('DROP TABLE IF EXISTS concepts')

    # Salva as alterações e fecha a conexão
    conn.commit()
    conn.close()

if __name__ == '__main__':
    delete_table()
    print("Tabela 'concepts' deletada com sucesso (se existia).")
