# email_test.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()  # Carica le variabili dal file .env

EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = EMAIL_USER  # Mandala a te stesso per test

def send_test_email():
    msg = MIMEMultipart()
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = "🧪 Email di test SMTP da Flask App"

    body = """
    Ciao Daniele,

    Questa è un'email di prova inviata tramite script Python + SMTP.
    
    Se la stai leggendo, tutto funziona! 🎉
    """

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("✅ Email inviata con successo!")
    except Exception as e:
        print(f"❌ Errore durante l'invio dell'email: {str(e)}")

if __name__ == "__main__":
    send_test_email()
