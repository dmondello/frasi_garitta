import os
import sqlite3
from flask import Flask, g, jsonify, redirect

# Configurazione percorso database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'quotes.db')  # Assicurati che il file esista

# Creazione app Flask
app = Flask(__name__, static_folder='static')
app.config['DEBUG'] = True

@app.route('/')
def root():
    return redirect('/static/index.html')

# Gestione connessione SQLite
def get_db():
    app.logger.debug(f"Opening SQLite database at: {DATABASE}")
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Endpoint API che restituisce solo le frasi validate
@app.route('/api/quotes')
def get_quotes():
    # Verifica esistenza tabella
    cur = get_db().execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='quotes';"
    )
    if cur.fetchone() is None:
        app.logger.error("Table 'quotes' not found in the database!")
        return jsonify({"error": "Table 'quotes' non trovata"}), 500

    # Seleziona solo le frasi con validated = 1
    rows = get_db().execute(
        'SELECT id, text, author FROM quotes WHERE validated = 1'
    ).fetchall()
    quotes = [dict(id=r['id'], text=r['text'], author=r['author']) for r in rows]
    return jsonify(quotes)

if __name__ == '__main__':
    # Debug all’avvio: elenco tabelle e loro colonne
    with app.app_context():
        db = sqlite3.connect(DATABASE)
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()]
        app.logger.debug(f"Tabelle presenti: {tables}")
        # Mostra le colonne di quotes
        cols = [c[1] for c in db.execute("PRAGMA table_info(quotes);").fetchall()]
        app.logger.debug(f"Colonne in 'quotes': {cols}")
        db.close()
    app.run()
