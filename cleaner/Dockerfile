# Step 1: Brug Python 3.9 som base image
FROM python:3.9-slim

# Step 2: Sæt arbejdsbibliotek
WORKDIR /app

# Step 3: Kopier kravfilen og installer dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Step 4: Kopier den øvrige kode til containeren
COPY . .

# Step 5: Start FastAPI-serveren med Uvicorn
CMD sleep 25 && uvicorn main:app --host 0.0.0.0 --port 8001
