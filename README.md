# AutoQuery Solver Agent

A real-time database monitoring and anomaly detection system.

## What This Project Does
Monitors a MySQL database for any changes (INSERT, UPDATE, DELETE) 
and streams them in real time using Kafka and Debezium.

## Tech Stack
- **MySQL** — Main database
- **Kafka** — Message streaming
- **Debezium** — Captures database changes automatically

## Architecture

### ✅ Worker 1 — Monitoring Agent (Done)
- Watches MySQL database for any data changes in real time
- Uses CDC (Change Data Capture) via Debezium
- Streams every change into Kafka topics automatically
