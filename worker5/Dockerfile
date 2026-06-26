FROM python:3.11-slim

# Install mysqldump (needed by safety/backup.py via subprocess)
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all worker5 source files
COPY . .

# Create backups directory inside container
RUN mkdir -p /backups

CMD ["python", "executor_agent.py"]