# Brug Python som base image
FROM python:3.10

# Skift til arbejdsmappe
WORKDIR /app

# Kopiér og installer afhængigheder
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiér kode
COPY . .

# Vent 10 sekunder før start
CMD sleep 40
CMD uvicorn main:app --host 0.0.0.0 --port 8000
