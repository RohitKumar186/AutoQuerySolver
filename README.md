# 🔍 AutoQuery Solver Agent

> A real-time database monitoring and AI-powered anomaly detection system built on Change Data Capture (CDC) architecture.

---

## 🚀 Overview

AutoQuery Solver Agent monitors MySQL database activity in real time, capturing every INSERT, UPDATE, and DELETE operation using Debezium CDC and streaming them through Apache Kafka. Each stage of the pipeline is handled by an independent worker — from raw change capture and intelligent 3-layer inspection, through AI-powered correction, human validation, safe execution, and full audit logging.

---

## 📌 What This Project Does

- Monitors MySQL databases continuously in real time
- Captures all database changes automatically via CDC (no polling)
- Streams events to Kafka topics for scalable downstream processing
- Validates every incoming record with rule-based and AI checks
- Detects near-duplicate and phonetically similar records
- Uses Google Gemini to flag typos, inconsistencies, and suspicious values
- Visualises anomaly results on a live dashboard
- AI suggests the best fix using past experience (memory/vector store)
- Human approval gate before any fix is applied to the database
- Safely writes corrections with rollback/savepoint protection
- Logs every fix permanently and feeds it back as memory for future corrections

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Database | MySQL 8.0 |
| CDC Connector | Debezium 2.4 |
| Event Streaming | Apache Kafka (Confluent 7.5.0, KRaft mode) |
| Stream Browser | Kafka UI (Provectus) |
| Schema Validation | Pandera, Pydantic, JSON Schema |
| Duplicate Detection | FuzzyWuzzy / RapidFuzz + Double Metaphone |
| AI Inspection & Fix | Claude API (Sonnet), Google Gemini API |
| Agent Framework | LangGraph / CrewAI |
| Memory / Vector Store | pgvector (Postgres), Pinecone, OpenAI / Claude Embeddings |
| Human Approval UI | FastAPI + React |
| Queue | Redis |
| Database Writing | SQLAlchemy / psycopg2 |
| Rollback | SQL Transactions + SAVEPOINT, pg_dump / mysqldump, Flyway / Liquibase |
| Audit Logging | PostgreSQL audit table, Python logging, ELK Stack |
| Dashboard | Streamlit (Worker 2), Grafana / Metabase (Worker 6) |
| Notifications | Slack API / Email (SMTP) |
| Containerization | Docker & Docker Compose |
| Version Control | Git & GitHub |

---

## 🏗️ Architecture

```
MySQL Database (binlog enabled)
        ↓
Debezium CDC Connector  (port 8083)
        ↓
Apache Kafka (KRaft mode)  (port 9092)
        ↓
Worker 2 — Inspector Agent
  ├── Layer 1: Rule-Based (Regex + Pandera)
  ├── Layer 2: AI-Powered (Gemini API)
  ├── Layer 3: Duplicate Detection (FuzzyWuzzy + Metaphone)
  └── Live Dashboard (Streamlit, port 8501)
        ↓
Worker 3 — Doctor (Correction Agent)
  └── Claude API + LangGraph + Vector Memory
        ↓
Worker 4 — Checker (Validation Agent)
  └── Rule Engine + Human Approval UI + Slack Alert
        ↓
Worker 5 — Fixer (Execution Agent)
  └── SQLAlchemy + SAVEPOINT + Rollback Safety Net
        ↓
Worker 6 — Diary Keeper (Logging Agent)
  └── Audit Table + pgvector Memory + Grafana Dashboard
```

---

## 🐳 Docker Services

| Container | Image | Port | Role |
|---|---|---|---|
| `watchman_mysql` | mysql:8.0 | `${MYSQL_PORT}` | Primary database with binlog enabled |
| `watchman_kafka` | confluentinc/cp-kafka:7.5.0 | 9092 | Event streaming broker (KRaft) |
| `watchman_debezium` | debezium/connect:2.4 | 8083 | CDC connector |
| `watchman_kafka_ui` | provectuslabs/kafka-ui | 8080 | Live Kafka stream browser |
| `watchman_inspector` | custom (worker2/) | — | 3-layer anomaly inspection + dashboard |
| `watchman_doctor` | custom (worker3/) | — | AI correction agent |
| `watchman_checker` | custom (worker4/) | — | Validation + human approval gate |
| `watchman_fixer` | custom (worker5/) | — | Safe database write execution |
| `watchman_diary` | custom (worker6/) | — | Audit logging + self-learning memory |

---

## ⚙️ Setup & Quick Start

### Prerequisites

- Docker Desktop — https://www.docker.com/products/docker-desktop
- Git — https://git-scm.com
- Gemini API key — https://aistudio.google.com/apikey

### Step 1 — Clone the repository

```bash
git clone https://github.com/RohitKumar186/AutoQuerySolver.git
cd AutoQuerySolver
```

### Step 2 — Configure environment variables

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

### Step 3 — Start the full stack

```bash
docker compose up --build inspector_agent
```

### Step 4 — Register the Debezium connector

```bash
curl -X POST "http://localhost:8083/connectors" \
  -H "Content-Type: application/json" \
  -d @config/debezium-connector.json
```

### Step 5 — Test anomaly detection

```bash
docker exec -it watchman_mysql mysql -u root -p<DB_ROOT_PASSWORD> autoquery_db
```

```sql
INSERT INTO customers (name, phone) VALUES ('R4hul $hmara', 'not-a-phone');
```

### Step 6 — Watch the inspector logs

```bash
docker logs -f watchman_inspector
```

### Service URLs

| Service | URL |
|---|---|
| Anomaly Dashboard (Streamlit) | http://localhost:8501 |
| Kafka UI | http://localhost:8080 |
| Debezium REST API | http://localhost:8083 |
| Human Approval UI | http://localhost:3000 |
| MySQL | localhost:3307 |

---

## ✅ Worker 1 — Monitoring Agent *(Completed)*

Watches MySQL continuously for row-level changes using Debezium CDC. Captures INSERT, UPDATE, and DELETE operations and publishes them as events to Kafka topics. Tracks schema changes automatically and provides a reliable, near real-time event stream for downstream workers.

**Key features:** event-driven architecture, persistent volumes, automatic restart on failure, isolated Docker network.

---

## ✅ Worker 2 — Inspector Agent *(Completed)*

Consumes every CDC event from Kafka in real time and runs three layers of checks on every incoming record. Clean records are logged; anomalies are flagged immediately with a detailed issue breakdown. Results are streamed to a live Streamlit dashboard.

### 3-Layer Inspection System

#### Layer 1 — Rule-Based Checking

| Tool | Purpose |
|---|---|
| Python Regex | Validates email, phone, date, and name formats |
| Pandera | Schema-level type and range validation |

#### Layer 2 — AI-Powered Checking

| Tool | Purpose |
|---|---|
| Google Gemini API | Reads each record and flags typos, inconsistencies, and suspicious values |

#### Layer 3 — Duplicate Detection

| Tool | Purpose |
|---|---|
| FuzzyWuzzy / RapidFuzz | Catches near-duplicate names (e.g. "Rahul Sharma" vs "Rahul Shmara") |
| Double Metaphone | Matches names that sound the same even if spelled differently |

### Live Dashboard

A Streamlit dashboard (port 8501) visualises the inspector's output in real time — live event feed, anomaly vs clean record counts, drill-down per flagged record, and filters by event type and anomaly layer.

### Sample Output

```
📥 Event [C] — {'id': 11, 'name': 'R4hul $hmara', 'phone': 'not-a-phone', ...}
⚠️  Rule issues: ["[FORMAT] 'name' does not match name pattern", "[FORMAT] 'phone' does not match phone pattern"]
🤖 AI issues : ["Name 'R4hul $hmara' appears to be a typo"]
🔁 Dup issues: ["[NEAR-DUPLICATE] 'R4hul $hmara' is 100% similar to 'r4hul $hmara'"]
❌ ANOMALY DETECTED — 7 issue(s)
```

### File Structure

```
worker2/
├── inspector_agent.py        # Main Kafka consumer loop
├── dashboard/
│   └── app.py                # Streamlit live dashboard
├── checks/
│   ├── rule_based.py         # Regex + Pandera checks
│   ├── ai_checker.py         # Gemini API integration
│   └── duplicate.py          # FuzzyWuzzy + Metaphone
├── requirements.txt
└── Dockerfile
```

---

## 🔄 Worker 3 — The Doctor (Correction Agent) *(Upcoming)*

Figures out the best fix for every flagged anomaly using AI reasoning and past experience stored in a vector memory bank.

### The AI Brain

| Tool | Purpose |
|---|---|
| Claude API (Sonnet) | Reads the bad record and writes the fix with explanation |
| LangChain | Toolkit that helps Claude talk to databases and other tools |

### Memory / Knowledge Base

| Tool | Purpose |
|---|---|
| pgvector (in Postgres) | Stores all past fixes so the Doctor can remember what worked before |
| Pinecone (optional) | Cloud-based memory store — easier to set up than pgvector |
| OpenAI / Claude Embeddings | Converts fixes into a searchable format so similar ones can be found |

### Agent Framework

| Tool | Purpose |
|---|---|
| LangGraph | Manages the Doctor's thinking steps — like a flowchart runner for AI |
| CrewAI (alternative) | Lets multiple AI agents work as a team |

---

## 🔄 Worker 4 — The Checker (Validation Agent) *(Upcoming)*

Makes sure every fix is safe, correct, and follows the company's rules before it is applied.

### Rule Engine Tools

| Tool | Purpose |
|---|---|
| JSON Schema | Defines what valid data looks like in code |
| Pydantic | Double-checks data types automatically |
| SQLAlchemy | Checks if the fix respects database constraints (foreign keys, etc.) |

### Human Approval Tools

| Tool | Purpose |
|---|---|
| FastAPI | Builds the approve / reject screen that managers see |
| React (frontend) | Makes the approval screen work in a browser |
| Redis Queue | Holds fixes that are waiting for human approval |

### Notification Tools

| Tool | Purpose |
|---|---|
| Slack API / Email (SMTP) | Sends a "please approve this fix" alert to the right person |

---

## 🔄 Worker 5 — The Fixer (Execution Agent) *(Upcoming)*

The only worker that actually edits the database — very carefully, with a full safety net.

### Database Writing

| Tool | Purpose |
|---|---|
| SQLAlchemy / psycopg2 | Writes SQL commands to the database safely |
| SQL Transactions + SAVEPOINT | Checkpoint system — if something breaks, it rewinds like a video game save |

### Safety / Rollback Tools

| Tool | Purpose |
|---|---|
| pg_dump / mysqldump | Takes a snapshot of the data before changing it |
| Flyway / Liquibase | Tracks all database changes like a history book — easy to undo |

### Testing the Fix Worked

| Tool | Purpose |
|---|---|
| SQLAlchemy read-back check | After editing, reads the row again to confirm the fix actually applied |
| pytest | Runs automatic tests to make sure the Fixer is working correctly |

---

## 🔄 Worker 6 — The Diary Keeper (Logging Agent) *(Upcoming)*

Records everything forever and teaches the system to get smarter over time.

### Audit Logging Tools

| Tool | Purpose |
|---|---|
| PostgreSQL audit table | Append-only table that stores every fix ever made — can't be deleted |
| Python logging module | Records what happened in plain text files as backup |
| ELK Stack (optional) | Elasticsearch + Kibana — lets you search and visualise logs on a dashboard |

### Self-Learning Tools

| Tool | Purpose |
|---|---|
| pgvector / Pinecone | Saves what was fixed as memory the Doctor can search next time |
| Claude API (embedding) | Converts each fix into a searchable fingerprint for the memory bank |

### Dashboard / Reporting Tools

| Tool | Purpose |
|---|---|
| Grafana | Live dashboard showing how many fixes were made, what types, how often |
| Metabase (simpler option) | Easier dashboard tool — good for non-technical managers to see reports |

---

## 🎯 Project Goals

- Build a scalable, production-ready database monitoring platform
- Enable real-time, event-driven processing with no polling overhead
- Detect, correct, and verify anomalies automatically without manual auditing
- Build AI memory so the system gets smarter with every fix
- Deliver a fully auditable, self-healing database observability system

---

## 🔮 Future Enhancements

- ML-based anomaly detection models
- Multi-database support (PostgreSQL, MongoDB)
- Historical trend analysis
- Natural language querying of database events
- Auto-tuning of detection thresholds based on past false positives

---

## 👨‍💻 Author

**Rohit Kumar**  
GitHub: [@RohitKumar186](https://github.com/RohitKumar186)
