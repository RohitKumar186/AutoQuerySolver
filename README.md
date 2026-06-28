# 🔍 AutoQuery Solver Agent

> A real-time database monitoring and AI-powered auto-correction system built on Change Data Capture (CDC) architecture.

---

## 🚀 What Is This Project?

AutoQuery Solver Agent watches your MySQL database 24/7. Every time someone inserts, updates, or deletes a row — the system catches it instantly, checks if the data is valid, and if something is wrong, an AI agent figures out the best fix and corrects it automatically.

The system is built as a pipeline of independent workers, each doing one job:

- **Worker 1** captures every database change in real time
- **Worker 2** inspects each record for errors using rules + AI
- **Worker 3** fixes the errors intelligently using Groq AI and past experience
- **Worker 4** validates every fix through 3 layers, auto-approves high-confidence fixes, and routes low-confidence ones to a human approval UI
- **Worker 5** safely writes the approved fix back to the database with SAVEPOINT transactions + read-back verification
- **Worker 6** logs everything forever in an append-only audit table and makes the system smarter over time via ChromaDB self-learning

---

## 🏗️ Architecture

```
MySQL Database (binlog enabled)
        ↓
Debezium CDC Connector          ← captures every INSERT / UPDATE / DELETE
        ↓
Apache Kafka                    ← streams events to all workers
        ↓
Worker 2 — Inspector            ← detects anomalies (3-layer check)
        ↓  (same Kafka topic, different consumer group)
Worker 3 — Doctor               ← AI fixes the anomalies
        ↓  (reads fixes from ChromaDB)
Worker 4 — Checker              ← validates + auto-approves or routes to human
        ↓  (approved fixes pushed to Redis)
Worker 5 — Executor             ← writes fix safely to database (SAVEPOINT + read-back)
        ↓  (Debezium captures the write → Kafka again)
Worker 6 — Logger               ← logs everything to audit_log + updates ChromaDB memory
```

---

## 🛠️ Tech Stack

| Layer | What We Actually Use |
|---|---|
| Database | MySQL 8.0 (binlog enabled) |
| CDC | Debezium 2.4 |
| Event Streaming | Apache Kafka (Confluent 7.5, KRaft — no Zookeeper) |
| Rule Validation | Python Regex + Pandera |
| Duplicate Detection | FuzzyWuzzy + Double Metaphone |
| AI Inspection | Groq API (llama-3.3-70b-versatile) |
| AI Correction | Groq API (llama-3.3-70b-versatile) |
| Agent Framework | LangGraph |
| Vector Memory | ChromaDB (cosine similarity) |
| Embeddings | n-gram hash (pure Python, no API key needed) |
| Fix Validation | JSON Schema + Pydantic v2 + SQLAlchemy dry-run |
| Human Approval Queue | Redis |
| Approval API | FastAPI + uvicorn |
| DB Write Safety | SQLAlchemy + SAVEPOINT + read-back verification + mysqldump |
| Audit Logging | SQLAlchemy → MySQL audit_log table (append-only) |
| Notifications | smtplib (Email) + Slack Webhook |
| Dashboard | Vanilla HTML/JS + WebSocket |
| Containerization | Docker + Docker Compose |

---

## 🐳 Running Services

| Container | Port | Role |
|---|---|---|
| `watchman_mysql` | 3307 | MySQL database |
| `watchman_kafka` | 9092 | Kafka broker |
| `watchman_debezium` | 8083 | CDC connector |
| `watchman_kafka_ui` | 8080 | Kafka browser UI |
| `watchman_inspector` | 8765 | Worker 2 WebSocket |
| `watchman_doctor` | 8766, 8767 | Worker 3 WebSocket + HTTP API |
| `watchman_checker` | 8000 | Worker 4 FastAPI approval API |
| `watchman_redis` | 6379 | Redis queue (Workers 4 & 5) |
| `watchman_executor` | 8768 | Worker 5 WebSocket |
| `watchman_logger` | 8769, 8770 | Worker 6 WebSocket + Audit REST API |
| `watchman_dashboard` | 5500 | Worker 2 Inspector dashboard |
| `watchman_doctor_dashboard` | 5501 | Worker 3 Doctor dashboard |
| `watchman_checker_dashboard` | 5502 | Worker 4 Approval dashboard |
| `watchman_dashboard_executor` | 5503 | Worker 5 Executor dashboard |
| `watchman_logger_dashboard` | 5504 | Worker 6 Audit Logger dashboard |

---

## ⚙️ Quick Start

### Prerequisites
- Docker Desktop → https://www.docker.com/products/docker-desktop
- Git → https://git-scm.com
- Groq API key → https://console.groq.com (free)

### Step 1 — Clone
```bash
git clone https://github.com/RohitKumar186/AutoQuerySolver.git
cd AutoQuerySolver
```

### Step 2 — Environment
```bash
cp .env.example .env
```

Open `.env` and fill in your values:
```env
DB_ROOT_PASSWORD=your_root_password
DB_NAME=autoquery_db
DB_USER=solver_admin
DB_PASSWORD=your_db_password
MYSQL_PORT=3307
KAFKA_TOPIC=dbserver1.autoquery_db.customers
GROK_API_KEY=your_groq_api_key_here

# Worker 4 — notifications (optional)
SLACK_WEBHOOK=https://hooks.slack.com/services/...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_EMAIL_TO=manager@yourcompany.com

# Worker 5 — executor
BACKUP_DIR=/backups
BACKUP_EVERY_N=10
```

### Step 3 — Start everything
```bash
docker compose up --build -d
```
> First run takes 15-20 minutes. All images are downloaded fresh.

### Step 4 — Register Debezium connector

**Linux / Mac / Git Bash:**
```bash
curl -X POST "http://localhost:8083/connectors" \
  -H "Content-Type: application/json" \
  -d @config/debezium-connector.json
```

**Windows PowerShell:**
```powershell
$body = Get-Content -Raw "config/debezium-connector.json"
Invoke-WebRequest -Uri "http://localhost:8083/connectors" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body `
  -UseBasicParsing
```

### Step 5 — Verify all containers
```bash
docker compose ps
```

All containers should show **Up**.

### Step 6 — Test the full pipeline
Insert a bad record:
```bash
docker exec -it watchman_mysql mysql -uroot -pYour_Root_Password autoquery_db -e \
  "INSERT INTO customers (name, phone) VALUES ('Rohit Sin11', '935684243A');"
```

Watch all workers process it:
```bash
docker logs -f watchman_inspector   # anomaly detected
docker logs -f watchman_doctor      # fix generated
docker logs -f watchman_checker     # fix validated
docker logs -f watchman_executor    # fix written to DB
docker logs -f watchman_logger      # fix logged to audit table
```

### Dashboards

| Dashboard | URL | What you see |
|---|---|---|
| Inspector (Worker 2) | http://localhost:5500 | Live anomaly detection feed |
| Doctor (Worker 3) | http://localhost:5501 | AI fix feed + live DB table |
| Checker (Worker 4) | http://localhost:5502 | Human approval queue |
| Executor (Worker 5) | http://localhost:5503 | DB write execution feed |
| Logger (Worker 6) | http://localhost:5504 | Audit log + stats |
| Kafka UI | http://localhost:8080 | Kafka topic browser |
| Audit REST API | http://localhost:8770/docs | Swagger docs |

---

## ✅ Worker 1 — Monitoring Agent *(Completed)*

Watches MySQL using Debezium CDC. Captures every INSERT, UPDATE, DELETE from the binlog and publishes them as events to a Kafka topic in real time — no polling, no delay.

**Key config:**
```
binlog-format=ROW
binlog-row-image=FULL
server-id=1
```

---

## ✅ Worker 2 — Inspector Agent *(Completed)*

Consumes every CDC event from Kafka and runs 3 layers of checks on every record.

### 3-Layer Inspection

**Layer 1 — Rule-Based**
- Regex patterns for `name`, `phone`, `email`, `date` fields
- Pandera schema validation for types and ranges

**Layer 2 — AI Check (Groq)**
- Only fires if Layer 1 passes
- Sends record to Groq `llama-3.3-70b` to flag typos, inconsistencies, suspicious values
- Returns a JSON array of issue strings

**Layer 3 — Duplicate Detection**
- FuzzyWuzzy token sort ratio ≥ 85% for near-duplicate names
- Double Metaphone for phonetically similar names (e.g. "Singh" vs "Sinng")
- Exact email and phone deduplication

### Dashboard (port 5500)
Live event feed, anomaly counts, issue type breakdown, filter by clean/anomaly/AI/duplicate.

### Sample Output
```
📥 Event [C] — {'id': 11, 'name': 'R4hul $hmara', 'phone': 'not-a-phone'}
⚠️  Rule issues: ["[FORMAT] name does not match pattern", "[FORMAT] phone does not match pattern"]
🤖 AI issues  : ["Name 'R4hul $hmara' appears to be a typo"]
❌ ANOMALY DETECTED — 3 issue(s)
```

### File Structure
```
worker2/
├── inspector_agent.py      # Kafka consumer + WebSocket broadcast
├── checks/
│   ├── rule_based.py       # Regex + Pandera
│   ├── ai_checker.py       # Groq API
│   └── duplicate.py        # FuzzyWuzzy + Metaphone
├── dashboard.html          # Live dashboard
├── requirements.txt
└── Dockerfile
```

---

## ✅ Worker 3 — Doctor Agent *(Completed)*

Consumes the same Kafka topic (separate consumer group) and runs a LangGraph pipeline to intelligently fix every anomalous record.

### Pipeline
```
[check_issues] → clean? → skip
              → issues? → [embed] → [search] → [fixer] → [validator] → [saver]
```

| Step | File | What it does |
|---|---|---|
| check_issues | `nodes/check_issues.py` | Re-runs rule + duplicate checks |
| embed | `issues/embed.py` | Generates n-gram hash vector |
| search | `issues/search.py` | Finds top-3 similar past fixes in ChromaDB |
| fixer | `issues/fixer.py` | Asks Groq to generate the fix |
| validator | `issues/validator.py` | Re-runs rule checks on fixed record |
| saver | `issues/saver.py` | Saves fix to ChromaDB + broadcasts to dashboard |

### Smart Fixing Logic

| Input | Output | Reason |
|---|---|---|
| `Rohit Sin11` | `Rohit Singh` | Real name with typo → fixed |
| `rahul shrma` | `Rahul Sharma` | Real name with typo → fixed |
| `B@d Us3r!` | `UNKNOWN` | Pure garbage → cannot fix |
| `935684243A` | `NEEDS_CORRECTION` | Phone is private → user must correct |
| `not-a-phone` | `NEEDS_CORRECTION` | Phone is private → user must correct |

### File Structure
```
worker3/
├── doctor_agent.py         # Kafka consumer + WebSocket + HTTP API
├── doctor_dashboard.html   # Fix Feed + Live Table dashboard
├── graph/
│   └── pipeline.py         # LangGraph pipeline definition
├── nodes/
│   └── check_issues.py     # Step 0 — re-run checks
├── issues/
│   ├── embed.py            # Step 1 — n-gram hash embedding
│   ├── search.py           # Step 2 — ChromaDB similarity search
│   ├── fixer.py            # Step 3 — Groq fix generation
│   ├── validator.py        # Step 4 — validate fix
│   └── saver.py            # Step 5 — save + broadcast
├── utils/
│   └── chroma_client.py    # ChromaDB client
├── requirements.txt
└── Dockerfile
```

---

## ✅ Worker 4 — Checker Agent *(Completed)*

Polls ChromaDB every 10 seconds for new fixes saved by Worker 3. Runs each fix through a 3-layer validation pipeline, then either auto-approves it or routes it to a human manager via Slack/Email notification and a live approval UI.

### Validation Pipeline

```
[fetch from ChromaDB] → [Layer 1: JSON Schema] → [Layer 2: Pydantic v2] → [Layer 3: DB dry-run]
                                                                                    ↓
                                                              confidence ≥ 80% AND all passed?
                                                                    ↙                    ↘
                                                            AUTO-APPROVE            HUMAN REVIEW
                                                     push to Redis (W5)       Redis pending + notify
```

### Approval API (port 8000)

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/pending` | List all fixes waiting for human decision |
| `POST` | `/approve/{fix_id}` | Approve a fix → pushed to Worker 5 queue |
| `POST` | `/reject/{fix_id}` | Reject a fix → moves to rejected queue |
| `GET` | `/stats` | Queue depth and Redis health |
| `WS` | `/ws` | Live updates pushed to approval dashboard |

### File Structure
```
worker4/
├── checker_agent.py            # Main polling loop + routing logic
├── checker_dashboard.html      # Manager approval UI
├── validators/
│   ├── schema_validator.py     # Layer 1 — JSON Schema
│   ├── pydantic_models.py      # Layer 2 — Pydantic v2
│   └── db_validator.py         # Layer 3 — SQLAlchemy dry-run
├── approval/
│   ├── api.py                  # FastAPI endpoints + WebSocket
│   ├── queue.py                # Redis queue management
│   └── notifier.py             # Slack + Email alerts
├── requirements.txt
└── Dockerfile
```

---

## ✅ Worker 5 — Executor Agent *(Completed)*

The **only worker that permanently writes to MySQL**. Polls the Redis `approved_fixes` queue, takes a mysqldump backup, then applies each fix inside a SAVEPOINT transaction with read-back verification.

### Execution Flow

```
[Redis brpop] → [mysqldump backup] → [SAVEPOINT] → [UPDATE] → [SELECT read-back]
                                                                       ↓
                                                            values match expected?
                                                              ↙               ↘
                                                    RELEASE SAVEPOINT    ROLLBACK TO SAVEPOINT
                                                         COMMIT ✅              ❌
```

### Result States

| Status | Meaning |
|---|---|
| `SUCCESS` | UPDATE executed, read-back matched, committed |
| `ROLLED_BACK` | Read-back mismatch or zero rows affected — change undone |
| `ERROR` | Exception before or during execution |

### Sample Output
```
📬 Fix dequeued — record_id=3 approved_by=AUTO confidence=0.95
📸 Backup triggered → /backups/backup_20260623_194914.sql (42 KB)
💾 SAVEPOINT created for record id=3
✏️  UPDATE executed — 1 row(s) affected
✅ Fix COMMITTED — id=3 fields=['name'] values=['Rohit Singh']
```

### File Structure
```
worker5/
├── executor_agent.py           # Main loop — Redis poll + backup + write + broadcast
├── db/
│   ├── connection.py           # SQLAlchemy engine factory
│   └── writer.py               # SAVEPOINT + UPDATE + read-back
├── redis_queue/
│   └── redis_consumer.py       # brpop consumer
├── safety/
│   └── backup.py               # mysqldump + cleanup
├── dashboard/
│   └── dashboard.html          # Execution feed dashboard
├── tests/
│   ├── test_writer.py          # 6 pytest tests
│   └── test_backup.py          # 5 pytest tests
├── requirements.txt
└── Dockerfile
```

Run tests:
```bash
pytest worker5/tests/ -v
```

---

## ✅ Worker 6 — Logger / Auditor *(Completed)*

Sits at the very end of the pipeline. Every database event captured by Debezium — including the fixes written by Worker 5 — is logged permanently to a MySQL `audit_log` table. The table is append-only: no UPDATE, no DELETE, ever. Worker 6 also feeds every confirmed fix back into ChromaDB so Worker 3 gets smarter with every correction made.

### What It Does

**Job 1 — Append-Only Audit Log**
Every event gets one row in `audit_log` containing: original record, fixed record, issues found, confidence score, who approved it (auto or human email), and timestamp. SQLAlchemy ORM guards block any UPDATE or DELETE at the code level — the audit trail cannot be tampered with.

**Job 2 — ChromaDB Self-Learning**
Every confirmed fix (confidence ≥ 0.7 or fix_valid=True) is upserted into the same ChromaDB collection that Worker 3 reads from. The more fixes happen → the more similar examples Worker 3 has → the better future fixes become. This is the self-learning loop.

**Job 3 — REST API + Live Dashboard**
FastAPI on port 8770 exposes the audit log for external queries. The live dashboard on port 5504 shows every fix event in real time via WebSocket.

### Pipeline (LangGraph)
```
[ingest] → [audit] → [memory] → [reporter] → [broadcast]
```

| Step | File | What it does |
|---|---|---|
| ingest | `nodes/ingest_node.py` | Parse and normalize the raw CDC event |
| audit | `nodes/audit_node.py` | Write one row to audit_log (MySQL) |
| memory | `nodes/memory_node.py` | Upsert fix pair into ChromaDB |
| reporter | `nodes/reporter_node.py` | Build stats + dashboard payload |
| broadcast | `nodes/broadcast_node.py` | Push to WebSocket clients |

### Audit REST API (port 8770)

| Method | Endpoint | What it returns |
|---|---|---|
| `GET` | `/api/v1/audit` | Last 100 audit log rows |
| `GET` | `/api/v1/stats` | Total events, fix rate, avg confidence, op breakdown |
| `GET` | `/api/v1/report` | Full human-readable report with narrative |
| `GET` | `/api/v1/memory` | ChromaDB memory bank size |
| `GET` | `/health` | Container health check |

Swagger docs → http://localhost:8770/docs

### audit_log Table Schema

```sql
CREATE TABLE audit_log (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    worker       VARCHAR(20)  NOT NULL DEFAULT 'worker5',
    op           VARCHAR(10)  NOT NULL,
    record_id    INT,
    original     TEXT,                    -- JSON: bad record
    fixed        TEXT,                    -- JSON: corrected record
    issues       TEXT,                    -- JSON: list of issues found
    confidence   FLOAT,
    fix_valid    TINYINT(1),
    approved_by  VARCHAR(100),            -- 'auto' or email address
    explanation  TEXT,
    ts           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
```

### Dashboard (port 5504)
- Live audit feed — every event shown as a card with original → fixed diff
- Stats row — total logged, valid fixes, invalid fixes, avg confidence, memory entries
- Sidebar — fix rate, auto vs human approved, issue type breakdown
- API quick links — one click to open any REST endpoint

### Sample Output
```
✅ MySQL connected on attempt 1.
✅ audit_log table ready.
🧠 ChromaDB ready — 21 fix(es) in memory.
🌐 Logger WebSocket on ws://0.0.0.0:8769
🌐 FastAPI audit API on http://0.0.0.0:8770
✅ Logger Agent ready — listening for events …

📥 Logger received [U] — record_id=3
  💾 Audit row saved — id=14 op=u record_id=3 confidence=0.95
  🧠 Memory updated — fix_id=w6_fix_3_143001 total=22
  📡 Dashboard broadcast sent.
  ✅ Pipeline complete — audit_id=14 memory=True
```

### File Structure
```
worker6/
├── logger_agent.py             # Entry point — Kafka consumer + WS + FastAPI
├── pipeline.py                 # LangGraph state machine
├── config.py                   # All env vars and constants
├── nodes/
│   ├── ingest_node.py          # Parse raw CDC event
│   ├── audit_node.py           # Write to audit_log
│   ├── memory_node.py          # Update ChromaDB
│   ├── reporter_node.py        # Build stats payload
│   └── broadcast_node.py       # Push to dashboard
├── services/
│   ├── audit_writer.py         # SQLAlchemy audit_log writer
│   ├── memory_writer.py        # ChromaDB upsert
│   └── report_builder.py       # Stats aggregation + narrative
├── models/
│   ├── audit_log.py            # SQLAlchemy model (append-only guards)
│   └── db_setup.py             # create_all() on startup
├── api/
│   ├── app.py                  # FastAPI app + CORS
│   └── routes.py               # /audit /stats /report /memory endpoints
├── dashboard/
│   ├── dashboard.html          # Live audit dashboard
│   └── nginx.conf              # Nginx config
├── requirements.txt
└── Dockerfile
```

---

## 🎯 Project Goals

- Build a production-ready, self-healing database monitoring system
- Zero polling — pure event-driven CDC architecture
- AI that gets smarter with every fix it makes
- Human in the loop for sensitive data corrections
- Full append-only audit trail of every change ever made
- Complete observability — every worker has its own live dashboard

---

## 👨‍💻 Author

**Rohit Kumar**
GitHub → https://github.com/RohitKumar186
