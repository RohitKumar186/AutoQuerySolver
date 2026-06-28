FROM python:3.11-slim

WORKDIR /app

# System deps for pymysql + chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create __init__.py files so Python treats directories as packages
RUN touch nodes/__init__.py services/__init__.py models/__init__.py api/__init__.py

EXPOSE 8769 8770

CMD ["python", "logger_agent.py"]