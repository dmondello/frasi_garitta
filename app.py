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
        # Segna come verificato con email_checked = 3
        db.execute(
            "UPDATE quotes_da_validare SET email_checked = 3 WHERE id = ?",
            (quote['id'],)
        )
        
        # Copia nella tabella quotes con validated = 0
        db.execute(
            "INSERT INTO quotes (text, author, validated) VALUES (?, ?, 0)",
            (quote['frase'], quote['nome_completo'])
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

# Admin change password
@app.route('/admin/change_password', methods=['POST'])
def admin_change_password():
    global ADMIN_PASSWORD
    
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Verifica che la password corrente sia corretta
    if current_password != ADMIN_PASSWORD:
        flash('La password corrente non è valida', 'error')
        return redirect('/admin/dashboard')
    
    # Verifica che la nuova password sia valida
    if not new_password or len(new_password) < 6:
        flash('La nuova password deve essere di almeno 6 caratteri', 'error')
        return redirect('/admin/dashboard')
    
    # Verifica che le password coincidano
    if new_password != confirm_password:
        flash('Le nuove password non coincidono', 'error')
        return redirect('/admin/dashboard')
    
    # Aggiorna la password
    ADMIN_PASSWORD = new_password
    
    # Aggiorna la password nell'ambiente
    os.environ['ADMIN_PASSWORD'] = new_password
    
    flash('Password aggiornata con successo', 'success')
    return redirect('/admin/dashboard')

# Admin dashboard
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin')
    
    db = get_db()
    
    # Gestione delle citazioni in attesa
    pending_quotes = db.execute(
        "SELECT id, nome_completo, frase, email, email_checked FROM quotes_da_validare"
    ).fetchall()
    
    # Recupero parametri di filtro e paginazione per le frasi
    search = request.args.get('search', '')
    filter_status = request.args.get('filter_status', 'all')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Numero di elementi per pagina
    
    # Costruzione della query base con i filtri
    query = "SELECT id, text, author, validated FROM quotes WHERE 1=1"
    params = []
    
    # Applica filtro di ricerca
    if search:
        query += " AND (text LIKE ? OR author LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    # Applica filtro per stato
    if filter_status == 'validated':
        query += " AND validated = 1"
    elif filter_status == 'not_validated':
        query += " AND validated = 0"
    
    # Query per contare il totale dei risultati
    count_query = query.replace("SELECT id, text, author, validated", "SELECT COUNT(*)")
    total_count = db.execute(count_query, params).fetchone()[0]
    
    # Calcola il numero totale di pagine
    total_pages = (total_count + per_page - 1) // per_page
    
    # Aggiungi ordinamento e paginazione
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    offset = (page - 1) * per_page
    params.extend([per_page, offset])
    
    # Esegui la query con i filtri e la paginazione
    quotes_list = db.execute(query, params).fetchall()
    
    return render_template('admin_dashboard.html', 
                           quotes=pending_quotes, 
                           quotes_list=quotes_list,
                           search=search,
                           filter_status=filter_status,
                           page=page,
                           total_pages=total_pages,
                           total_count=total_count,
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

# API per gestire le frasi nella tabella quotes

# Aggiungi una nuova frase
@app.route('/admin/quotes/add', methods=['POST'])
def admin_add_quote():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Accesso non autorizzato"}), 401
    
    text = request.form.get('text')
    author = request.form.get('author')
    validated = 1 if request.form.get('validated') == 'on' else 0
    
    if not text or not author:
        return jsonify({"error": "Testo e autore sono obbligatori"}), 400
    
    db = get_db()
    
    try:
        db.execute(
            "INSERT INTO quotes (text, author, validated) VALUES (?, ?, ?)",
            (text, author, validated)
        )
        
        db.commit()
        
        return redirect('/admin/dashboard')
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore aggiunta citazione: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Modifica una frase esistente
@app.route('/admin/quotes/edit/<int:quote_id>', methods=['POST'])
def admin_edit_quote(quote_id):
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Accesso non autorizzato"}), 401
    
    text = request.form.get('text')
    author = request.form.get('author')
    validated = 1 if request.form.get('validated') == 'on' else 0
    
    if not text or not author:
        return jsonify({"error": "Testo e autore sono obbligatori"}), 400
    
    db = get_db()
    
    try:
        db.execute(
            "UPDATE quotes SET text = ?, author = ?, validated = ? WHERE id = ?",
            (text, author, validated, quote_id)
        )
        
        db.commit()
        
        return redirect('/admin/dashboard')
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore modifica citazione: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Elimina una frase
@app.route('/admin/quotes/delete/<int:quote_id>', methods=['POST'])
def admin_delete_quote(quote_id):
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Accesso non autorizzato"}), 401
    
    db = get_db()
    
    try:
        db.execute(
            "DELETE FROM quotes WHERE id = ?",
            (quote_id,)
        )
        
        db.commit()
        
        return redirect('/admin/dashboard')
        
    except Exception as e:
        db.rollback()
        app.logger.error(f"Errore eliminazione citazione: {str(e)}")
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
