# Frasi Garitta - Sistema di Gestione Citazioni

Applicazione web per la gestione, validazione e visualizzazione di citazioni.

## Funzionalità

- Visualizzazione delle citazioni validate a rotazione
- Inserimento di nuove citazioni da parte degli utenti esterni
- Validazione delle citazioni tramite email
- Pannello amministrativo per approvare/rifiutare citazioni in attesa
- Modalità di manutenzione/allestimento del sito

## Installazione

### Requisiti

- Docker e Docker Compose

### Installazione con Docker

1. Clona il repository:
   ```
   git clone [URL_REPOSITORY]
   cd frasi_garitta
   ```

2. Personalizza le variabili d'ambiente nel file `docker-compose.yml`:
   - Configura l'email SMTP
   - Modifica le credenziali di amministrazione

3. Avvia il container:
   ```
   docker-compose up -d
   ```

4. L'applicazione sarà disponibile all'indirizzo http://localhost:5001

### Installazione manuale

1. Clona il repository:
   ```
   git clone [URL_REPOSITORY]
   cd frasi_garitta
   ```

2. Crea un ambiente virtuale Python e attivalo:
   ```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. Installa le dipendenze:
   ```
   pip install -r requirements.txt
   ```

4. Avvia l'applicazione:
   ```
   python app.py
   ```

5. L'applicazione sarà disponibile all'indirizzo http://localhost:5001

## Utilizzo

### Interfaccia Utente

- **Pagina principale**: Mostra le citazioni a rotazione
- **Pagina di inserimento**: Permette agli utenti di inviare nuove citazioni

### Amministrazione

- Accedi all'interfaccia di amministrazione all'indirizzo `/admin`
- Credenziali predefinite: username `admin`, password `password`
- Nel pannello amministrativo puoi:
  - Approvare o rifiutare le citazioni in attesa
  - Attivare/disattivare la modalità di manutenzione/allestimento del sito
  - Personalizzare il messaggio di manutenzione

## Sicurezza

Si consiglia di:
1. Modificare le credenziali di amministrazione
2. Configurare correttamente l'invio email
3. Utilizzare HTTPS in ambiente di produzione

## Manutenzione

- I dati sono salvati nel file `quotes.db` (SQLite)
- I file di testo delle citazioni sono memorizzati nella directory `quotes_files`
- La configurazione della modalità manutenzione è salvata in `maintenance_config.json`