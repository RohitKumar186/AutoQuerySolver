FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Worker 3 source
COPY . .

# Copy Worker 2's checks folder so we can reuse rule_based + duplicate checkers
# This is mounted via docker-compose volumes — see docker-compose.yml
# PYTHONPATH ensures "from checks.xxx import" works in all nodes

ENV PYTHONPATH="/app:/worker2"

# ChromaDB persistent data directory
RUN mkdir -p /chroma_data

CMD ["python", "doctor_agent.py"]