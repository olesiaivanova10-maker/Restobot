FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create credentials dir if needed
# We assume credentials.json is provided via bind mount or copied in
COPY . .

CMD ["python", "main.py"]
