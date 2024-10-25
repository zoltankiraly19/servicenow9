# Alap Docker-kép meghatározása
FROM python:3.9-slim

# Munka könyvtár létrehozása
WORKDIR /app

# Függőségek másolása és telepítése
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Alkalmazás fájlok másolása
COPY . .

# Port megadása
EXPOSE 5000

# Alkalmazás futtatása
CMD ["python", "app.py"]
