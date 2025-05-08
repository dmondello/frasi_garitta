FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Crea la directory per i file delle frasi
RUN mkdir -p /app/quotes_files

# Espone la porta 5001
EXPOSE 5001

# Comando di avvio con gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]