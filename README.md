# AutoQuery Solver Agent

A real-time database monitoring and anomaly detection system built using Change Data Capture (CDC) architecture.

## 🚀 Overview

AutoQuery Solver Agent is designed to monitor database activities in real time and process changes as they occur. The system captures INSERT, UPDATE, and DELETE operations from a MySQL database using Debezium and streams them through Apache Kafka for further processing, analytics, and anomaly detection.

The project follows a modular architecture where independent workers handle monitoring, processing, and intelligent analysis of database events.

---

## 📌 What This Project Does

* Monitors MySQL databases in real time.
* Captures every database change automatically using CDC.
* Streams database events to Kafka topics.
* Automatically detects anomalies in incoming records.
* Uses AI (Gemini) to flag suspicious data intelligently.
* Detects duplicate and near-duplicate records.
* Enables scalable event-driven processing.
* Forms the foundation for automated query analysis and alerting.

---

## 🛠️ Tech Stack

* **MySQL** — Primary Database
* **Apache Kafka** — Event Streaming Platform
* **Debezium** — Change Data Capture (CDC)
* **Docker** — Containerized Deployment
* **Python** — Data Processing & Analysis
* **Pandera** — Schema & Type Validation
* **FuzzyWuzzy** — Near-Duplicate Detection
* **Metaphone** — Phonetic Name Matching
* **Google Gemini API** — AI-Powered Record Inspection
* **Git & GitHub** — Version Control

---

## 🏗️ Architecture

```
MySQL Database
↓
Debezium Connector (CDC)
↓
Apache Kafka Topics
↓
Workers / Agents
↓
Analytics & Anomaly Detection
```

---

## ✅ Worker 1 — Monitoring Agent (Completed)

### Responsibilities

* Watches MySQL database continuously.
* Detects INSERT, UPDATE, and DELETE operations.
* Uses Debezium CDC connectors for change capture.
* Publishes database events into Kafka topics.
* Ensures near real-time data streaming.
* Provides the event source for downstream agents.

### Features

* Real-time monitoring
* Event-driven architecture
* Scalable Kafka integration
* Automatic schema change tracking
* Reliable data streaming pipeline

---

## ✅ Worker 2 — Inspector Agent (Completed)

### Responsibilities

* Consumes every CDC event from Kafka in real time.
* Runs three layers of checks on every incoming database record.
* Logs clean records and flags anomalies immediately.

### 3-Layer Inspection System

#### Layer 1 — Rule-Based Checking
| Tool | Purpose |
|---|---|
| **Python Regex** | Validates email, phone, date, and name formats |
| **Pandera** | Schema-level type and range validation |

#### Layer 2 — AI-Powered Checking
| Tool | Purpose |
|---|---|
| **Google Gemini API** | Reads each record and flags typos, inconsistencies, and suspicious values |

#### Layer 3 — Duplicate Detection
| Tool | Purpose |
|---|---|
| **FuzzyWuzzy / RapidFuzz** | Catches near-duplicate names (e.g. "Rahul Sharma" vs "Rahul Shmara") |
| **Double Metaphone** | Matches names that sound the same even if spelled differently |

### File Structure

```
worker2/
├── inspector_agent.py        # Main Kafka consumer loop
├── checks/
│   ├── rule_based.py         # Regex + Pandera checks
│   ├── ai_checker.py         # Gemini API integration
│   └── duplicate.py          # FuzzyWuzzy + Metaphone
├── requirements.txt
└── Dockerfile
```

### Sample Output

```
📥 Event [C] — {'id': 11, 'name': 'R4hul $hmara', 'phone': 'not-a-phone', ...}
⚠️  Rule issues: ["[FORMAT] 'name' does not match name pattern", "[FORMAT] 'phone' does not match phone pattern"]
🤖 AI issues : ["Name 'R4hul $hmara' appears to be a typo"]
🔁 Dup issues: ["[NEAR-DUPLICATE] 'R4hul $hmara' is 100% similar to 'r4hul $hmara'"]
❌ ANOMALY DETECTED — 7 issue(s)
```

---

## 🚀 Getting Started

### Prerequisites

* Docker Desktop installed — https://www.docker.com/products/docker-desktop
* Git installed — https://git-scm.com
* Gemini API key — https://aistudio.google.com/apikey

### Setup

**Step 1 — Clone the repository:**
```bash
git clone https://github.com/RohitKumar186/AutoQuerySolver.git
cd AutoQuerySolver
```

**Step 2 — Create your `.env` file:**
```bash
cp .env.example .env
```

Open `.env` and fill in your values:
```env
DB_ROOT_PASSWORD=super_secure_root_pass_2026
DB_NAME=autoquery_db
DB_USER=solver_admin
DB_PASSWORD=secure_agent_password_2026
MYSQL_PORT=3307
KAFKA_TOPIC=dbserver1.autoquery_db.customers
GEMINI_API_KEY=your_gemini_api_key_here
```

**Step 3 — Start all containers:**
```bash
docker compose up --build inspector_agent
```

**Step 4 — Register the Debezium connector:**
```bash
curl -X POST "http://localhost:8083/connectors" -H "Content-Type: application/json" -d @config/debezium-connector.json
```

**Step 5 — Test anomaly detection:**
```bash
docker exec -it watchman_mysql mysql -u root -p<DB_ROOT_PASSWORD> autoquery_db
```
```sql
INSERT INTO customers (name, phone) VALUES ('R4hul $hmara', 'not-a-phone');
```

**Step 6 — Watch the inspector logs:**
```bash
docker logs -f watchman_inspector
```

---

## 🔄 Upcoming Workers

### Worker 3 — Alert System
* Sends Slack or email notifications when anomalies are detected.
* Supports configurable alert thresholds.
* Integrates with existing monitoring tools.

### Worker 4 — AI Query Analysis Agent
* Uses LLMs to analyze database events.
* Generates human-readable insights.
* Provides intelligent recommendations.
* Automates query investigation workflows.

---

## 🎯 Project Goals

* Build a scalable database monitoring platform.
* Enable real-time event processing.
* Detect anomalies automatically.
* Reduce manual database auditing effort.
* Create an AI-powered database observability system.

---

## 🔮 Future Enhancements

* Machine Learning based anomaly detection.
* Dashboard for live monitoring.
* Email and Slack alert integration.
* Multi-database support.
* Historical trend analysis.
* AI-powered root cause analysis.
* Natural language querying of database events.

---

## 👨‍💻 Author

Rohit Kumar

GitHub: https://github.com/RohitKumar186
