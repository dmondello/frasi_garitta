import os
import sqlite3
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, g, jsonify, redirect, request, render_template, url_for, flash, session

# Configurazione percorso database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'quotes.db')  # Assicurati che il file esista
QUOTES_FOLDER = os.path.join(BASE_DIR, 'quotes_files')

# Creazione app Flask
app = Flask(__name__, static_folder='static')
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = secrets.token_hex(16)

# Configurazione email da variabili d'ambiente o valori predefiniti
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USER = os.environ.get('EMAIL_USER', 'your_email@example.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'your_password')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'noreply@example.com')
SITE_URL = os.environ.get('SITE_URL', 'http://localhost:5001')

# Configurazione admin da variabili d'ambiente o valori predefiniti
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'password')  # Cambia questa password in produzione!

# Configurazione manutenzione
MAINTENANCE_MODE = False  # Modalità manutenzione attiva/disattiva
MAINTENANCE_MESSAGE = "Torneremo online presto!"  # Messaggio personalizzabile
MAINTENANCE_CONFIG_FILE = os.path.join(BASE_DIR, 'maintenance_config.json')  # File di configurazione

# Carica configurazione manutenzione se esiste
def load_maintenance_config():
    global MAINTENANCE_MODE, MAINTENANCE_MESSAGE
    if os.path.exists(MAINTENANCE_CONFIG_FILE):
        try:
            import json
            with open(MAINTENANCE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                MAINTENANCE_MODE = config.get('maintenance_mode', False)
                MAINTENANCE_MESSAGE = config.get('maintenance_message', MAINTENANCE_MESSAGE)
        except Exception as e:
            app.logger.error(f"Errore caricamento configurazione manutenzione: {str(e)}")

# Salva configurazione manutenzione
def save_maintenance_config():
    try:
        import json
        with open(MAINTENANCE_CONFIG_FILE, 'w') as f:
            json.dump({
                'maintenance_mode': MAINTENANCE_MODE,
                'maintenance_message': MAINTENANCE_MESSAGE
            }, f)
    except Exception as e:
        app.logger.error(f"Errore salvataggio configurazione manutenzione: {str(e)}")

# Middleware per la modalità manutenzione
@app.before_request
def check_maintenance():
    # Bypass per admin login e pagine statiche necessarie
    if MAINTENANCE_MODE:
        # Esclusioni: permettere sempre l'accesso all'admin e ai file CSS/JS statici
        if not request.path.startswith('/admin') and not request.path.startswith('/static/css') and not request.path.startswith('/static/js'):
            # Sempre permetti l'accesso alla pagina di login admin
            if request.path != '/admin' and request.path != '/admin/login':
                return render_template('maintenance.html', message=MAINTENANCE_MESSAGE), 503

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

# Inizializzazione
def init_db():
    # Crea la directory per i file delle frasi se non esiste
    if not os.path.exists(QUOTES_FOLDER):
        os.makedirs(QUOTES_FOLDER)
    
    # Crea le tabelle se non esistono
    with app.app_context():
        db = get_db()
        # Crea la tabella quotes_da_validare se non esiste
        db.execute('''
        CREATE TABLE IF NOT EXISTS quotes_da_validare (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_completo TEXT NOT NULL,
            frase TEXT NOT NULL,
            email TEXT NOT NULL,
            email_checked INTEGER DEFAULT 0,
            token_validazione TEXT UNIQUE NOT NULL
        )
        ''')
        db.commit()

# Funzione per inviare email di conferma
def send_confirmation_email(email, token, nome_completo):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_FROM
        msg['To'] = email
        msg['Subject'] = "Conferma la tua citazione"
        
        link = f"{SITE_URL}/conferma?token={token}"
        
        body = f"""
        Ciao {nome_completo},
        
        Grazie per aver condiviso una citazione con noi.
        Per confermare la tua citazione, clicca sul seguente link:
        
        {link}
        
        Il link è valido una sola volta.
        
        Grazie!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        return True
    except Exception as e:
        app.logger.error(f"Errore invio email: {str(e)}")
        return False

# Endpoint per il form di inserimento delle citazioni
@app.route('/submit', methods=['GET', 'POST'])
def submit_quote():
    if request.method == 'GET':
        return redirect('/static/submit.html')
    
    # POST - Elabora il form
    nome = request.form.get('nome', '').strip()
    cognome = request.form.get('cognome', '').strip()
    frase = request.form.get('frase', '').strip()
    email = request.form.get('email', '').strip()
    
    # Validazione
    if not (nome and cognome and frase and email):
        return jsonify({"error": "Tutti i campi sono obbligatori"}), 400
    
    # Creazione nome completo
    nome_completo = f"{nome} {cognome}"
    
    # Generazione token univoco
    token = secrets.token_urlsafe(32)
    
    # Salvataggio nel database
    db = get_db()
    try:
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO quotes_da_validare (nome_completo, frase, email, token_validazione) VALUES (?, ?, ?, ?)",
            (nome_completo, frase, email, token)
        )
        db.commit()
        
        # Recupera l'ID generato
        quote_id = cursor.lastrowid
        
        # Salva la frase come file di testo
        quote_file_path = os.path.join(QUOTES_FOLDER, f"quote_{quote_id}.txt")
        with open(quote_file_path, 'w', encoding='utf-8') as f:
            f.write(f"Autore: {nome_completo}\n\n{frase}")
        
        # Invia email di conferma
        if send_confirmation_email(email, token, nome_completo):
            return jsonify({
                "success": True,
                "message": "Citazione inviata! Controlla la tua email per confermarla."
            })
        else:
            return jsonify({
                "success": False,
                "message": "Citazione salvata ma c'è stato un problema nell'invio dell'email. Contatta l'amministratore."
            }), 500
            
    except Exception as e:
        app.logger.error(f"Errore salvataggio citazione: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Endpoint per la conferma via URL
@app.route('/conferma')
def confirm_quote():
    token = request.args.get('token')
    
    if not token:
        return render_template('error.html', message="Token mancante")
    
    db = get_db()
    
    # Verifica il token
    quote = db.execute(
        "SELECT id, nome_completo, frase FROM quotes_da_validare WHERE token_validazione = ?",
        (token,)
    ).fetchone()
    
    if not quote:
        return render_template('error.html', message="Token non valido o già utilizzato")
    
    try:
        # Segna come verificato
        db.execute(
            "UPDATE quotes_da_validare SET email_checked = 1 WHERE id = ?",
            (quote['id'],)
        )
        
        # Sposta nella tabella quotes
        db.execute(
            "INSERT INTO quotes (text, author, validated) VALUES (?, ?, 1)",
            (quote['frase'], quote['nome_completo'])
        )
        
        # Elimina dalla tabella quotes_da_validare
        db.execute(
            "DELETE FROM quotes_da_validare WHERE id = ?",
            (quote['id'],)
        )
        
        db.commit()
        
        return render_template('success.html', nome=quote['nome_completo'])
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore conferma citazione: {str(e)}")
        return render_template('error.html', message=f"Errore durante la conferma: {str(e)}")

# Admin login
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/admin/dashboard')
        else:
            error = 'Credenziali non valide'
    
    return render_template('admin_login.html', error=error)

# Admin logout
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

# Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    db = get_db()
    pending_quotes = db.execute(
        "SELECT id, nome_completo, frase, email, email_checked FROM quotes_da_validare"
    ).fetchall()
    
    return render_template('admin_dashboard.html', 
                           quotes=pending_quotes, 
                           maintenance_mode=MAINTENANCE_MODE,
                           maintenance_message=MAINTENANCE_MESSAGE)

# Abilita/disabilita modalità manutenzione
@app.route('/admin/toggle_maintenance', methods=['POST'])
def toggle_maintenance():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    global MAINTENANCE_MODE, MAINTENANCE_MESSAGE
    
    action = request.form.get('action')
    if action == 'enable':
        MAINTENANCE_MODE = True
        # Aggiorna messaggio se fornito
        message = request.form.get('message')
        if message and message.strip():
            MAINTENANCE_MESSAGE = message.strip()
    elif action == 'disable':
        MAINTENANCE_MODE = False
    
    # Salva la configurazione
    save_maintenance_config()
    
    return redirect('/admin/dashboard')

# Admin approve quote
@app.route('/admin/approve/<int:quote_id>', methods=['POST'])
def admin_approve_quote(quote_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    db = get_db()
    
    quote = db.execute(
        "SELECT nome_completo, frase FROM quotes_da_validare WHERE id = ?",
        (quote_id,)
    ).fetchone()
    
    if not quote:
        return jsonify({"error": "Citazione non trovata"}), 404
    
    try:
        # Sposta nella tabella quotes
        db.execute(
            "INSERT INTO quotes (text, author, validated) VALUES (?, ?, 1)",
            (quote['frase'], quote['nome_completo'])
        )
        
        # Elimina dalla tabella quotes_da_validare
        db.execute(
            "DELETE FROM quotes_da_validare WHERE id = ?",
            (quote_id,)
        )
        
        db.commit()
        
        return redirect('/admin/dashboard')
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore approvazione citazione: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Admin reject quote
@app.route('/admin/reject/<int:quote_id>', methods=['POST'])
def admin_reject_quote(quote_id):
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    db = get_db()
    
    try:
        # Elimina dalla tabella quotes_da_validare
        db.execute(
            "DELETE FROM quotes_da_validare WHERE id = ?",
            (quote_id,)
        )
        
        db.commit()
        
        return redirect('/admin/dashboard')
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore rifiuto citazione: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Carica configurazione manutenzione
    load_maintenance_config()
    
    # Debug all'avvio e inizializzazione
    with app.app_context():
        init_db()
        
        # Crea la directory per i file delle frasi se non esiste
        if not os.path.exists(QUOTES_FOLDER):
            os.makedirs(QUOTES_FOLDER)
            
        db = sqlite3.connect(DATABASE)
        tables = [r[0] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()]
        app.logger.debug(f"Tabelle presenti: {tables}")
        # Mostra le colonne delle tabelle
        cols_quotes = [c[1] for c in db.execute("PRAGMA table_info(quotes);").fetchall()]
        app.logger.debug(f"Colonne in 'quotes': {cols_quotes}")
        try:
            cols_pending = [c[1] for c in db.execute("PRAGMA table_info(quotes_da_validare);").fetchall()]
            app.logger.debug(f"Colonne in 'quotes_da_validare': {cols_pending}")
        except:
            app.logger.debug("Tabella 'quotes_da_validare' non ancora creata")
        db.close()
        
        # Mostra info modalità manutenzione
        app.logger.debug(f"Modalità manutenzione: {'Attiva' if MAINTENANCE_MODE else 'Disattivata'}")
        if MAINTENANCE_MODE:
            app.logger.debug(f"Messaggio manutenzione: {MAINTENANCE_MESSAGE}")
            
    app.run(port=5001)  # Cambia la porta a 5001 o un'altra porta libera
