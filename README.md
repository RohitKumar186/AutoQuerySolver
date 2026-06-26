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
- **Worker 6** *(coming)* logs everything forever and makes the system smarter over time

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
        ↓
Worker 6 — Diary    [upcoming]  ← logs everything, teaches the system
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
| Notifications | smtplib (Email) + Slack Webhook |
| Dashboard | Vanilla HTML/JS + WebSocket (W2 → 5500, W3 → 5501, W4 → 5502, W5 → 5503) |
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
| `watchman_dashboard` | 5500 | Worker 2 dashboard |
| `watchman_doctor_dashboard` | 5501 | Worker 3 dashboard |
| `watchman_checker_dashboard` | 5502 | Worker 4 approval dashboard |
| `watchman_dashboard_executor` | 5503 | Worker 5 executor dashboard |

---

## ⚙️ Quick Start

### Prerequisites
- Docker Desktop
- Git
- Groq API key → https://console.groq.com

### Step 1 — Clone
```bash
git clone https://github.com/RohitKumar186/AutoQuerySolver.git
cd AutoQuerySolver
```

### Step 2 — Environment
```bash
cp .env.example .env
```
```
DB_ROOT_PASSWORD=
DB_NAME=
DB_USER=
DB_PASSWORD=
MYSQL_PORT=3307
KAFKA_TOPIC=dbserver1.autoquery_db.customers
GROK_API_KEY=write_your_api_key_here

# Worker 4 — notifications
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
docker compose up -d
```

### Step 4 — Register Debezium connector
```bash
curl -X POST "http://localhost:8083/connectors" \
  -H "Content-Type: application/json" \
  -d @config/debezium-connector.json
```

### Step 5 — Test it
```bash
docker exec -it watchman_mysql mysql -uroot -pYour_Password autoquery_db -e \
  "INSERT INTO customers (name, phone) VALUES ('Rohit Sin11', '935684243A');"
```

### Step 6 — Watch the Doctor fix it
```bash
docker logs -f watchman_doctor
```

Expected output:
```
name:  Rohit Sin11  →  Rohit Singh       ✅ typo fixed by AI
phone: 935684243A   →  NEEDS_CORRECTION  ⚠️  user must provide correct number
```

### Step 7 — Watch the Checker validate it
```bash
docker logs -f watchman_checker
```

Expected output:
```
🔎 Processing fix_id=fix_3_112843
   confidence=95% — all checks passed
🚀 AUTO-APPROVE — written to MySQL ✅

🔎 Processing fix_id=fix_4_113216
   confidence=72% < threshold 80%
👤 HUMAN REVIEW required — notification sent 📬
```

### Step 8 — Watch the Executor write to DB
```bash
docker logs -f watchman_executor
```

Expected output:
```
📬 Fix dequeued — record_id=3 approved_by=AUTO confidence=0.95
📸 Backup triggered → /backups/backup_20260623_194914.sql (42 KB)
💾 SAVEPOINT created for record id=3
✏️  UPDATE executed — 1 row(s) affected
✅ Fix COMMITTED — id=3 fields=['name', 'phone'] values=['Rohit Singh', 'NEEDS_CORRECTION']
```

### Dashboards
| Dashboard | URL |
|---|---|
| Inspector (Worker 2) | http://localhost:5500 |
| Doctor (Worker 3) | http://localhost:5501 |
| Checker (Worker 4) | http://localhost:5502 |
| Executor (Worker 5) | http://localhost:5503 |
| Kafka UI | http://localhost:8080 |

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
- Only fires if Layers 1 & 2 pass
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
| embed | `issues/embed.py` | Generates 384-dim n-gram hash vector |
| search | `issues/search.py` | Finds top-3 similar past fixes in ChromaDB |
| fixer | `issues/fixer.py` | Asks Groq to generate the fix |
| validator | `issues/validator.py` | Re-runs rule checks on fixed record |
| saver | `issues/saver.py` | Saves fix to ChromaDB + broadcasts to dashboard |

### Smart Fixing Logic

| Input | Output | Reason |
|---|---|---|
| `Rohit Sin11` | `Rohit Singh` | Real name with typo → fixed |
| `rahul shrma` | `Rahul Sharma` | Real name with typo → fixed |
| `Priya Patl` | `Priya Patel` | Real name with typo → fixed |
| `B@d Us3r!` | `UNKNOWN` | Pure garbage → cannot fix |
| `J0hn!!` | `UNKNOWN` | Pure garbage → cannot fix |
| `935684243A` | `NEEDS_CORRECTION` | Phone is private → user must correct |
| `not-a-phone` | `NEEDS_CORRECTION` | Phone is private → user must correct |

### ChromaDB Memory
Every fix is saved as a vector in ChromaDB. Next time a similar record comes in, the top-3 most similar past fixes are passed to Groq as examples — the system gets smarter with every fix.

Similarity scores after warming up:
```
Similar fix — similarity=0.922  ✅
Similar fix — similarity=0.910  ✅
```

### Dashboard (port 5501)
- **Fix Feed tab** — every fix as a card: original record → fixed record side by side, Groq explanation, issues detected
- **Live Table tab** — full database table updating in real time, FIXED / CLEAN / NEEDS INPUT badges

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

Polls ChromaDB every 10 seconds for new fixes saved by Worker 3. Runs each fix through a 3-layer validation pipeline, then either auto-approves it (high confidence + all checks pass) or routes it to a human manager via Slack/Email notification and a live approval UI.

### Validation Pipeline

```
[fetch from ChromaDB] → [Layer 1: JSON Schema] → [Layer 2: Pydantic v2] → [Layer 3: DB dry-run]
                                                                                    ↓
                                                              confidence ≥ 80% AND all passed?
                                                                    ↙                    ↘
                                                            AUTO-APPROVE            HUMAN REVIEW
                                                     push to Redis (W5)       Redis pending + notify
```

| Layer | File | What it checks |
|---|---|---|
| Layer 1 — JSON Schema | `validators/schema_validator.py` | Fix payload shape — required fields, types, enum values |
| Layer 2 — Pydantic v2 | `validators/pydantic_models.py` | Field-level value rules — name format, phone regex, id > 0 |
| Layer 3 — DB dry-run | `validators/db_validator.py` | Attempts a rolled-back INSERT/UPDATE against MySQL to catch constraint violations |
| Confidence gate | `checker_agent.py` | If confidence ≥ 80% AND layers 1-3 pass → auto-approve. Otherwise → human review |

### Routing Logic

**AUTO-APPROVE path** (confidence ≥ 80%, all validations pass):
- Fix payload pushed to Redis `approved_fixes` queue for Worker 5 to write
- Slack notification: "Fix queued for execution ✅"
- No human involvement needed

**HUMAN REVIEW path** (low confidence OR validation errors):
- Fix pushed to Redis `watchman:pending` queue
- Slack + Email alert sent with original → fixed diff and Approve/Reject buttons
- Fix appears in the approval dashboard (port 5502) in real time
- Manager clicks **Approve** → fix pushed to `approved_fixes` queue for Worker 5
- Manager clicks **Reject** → fix discarded, reason logged

### Approval API (port 8000)

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/pending` | List all fixes waiting for human decision |
| `GET` | `/fix/{fix_id}` | Get full payload for a specific fix |
| `POST` | `/approve/{fix_id}` | Approve a fix → pushed to Worker 5 queue |
| `POST` | `/reject/{fix_id}` | Reject a fix → moves to rejected queue |
| `GET` | `/stats` | Queue depth and Redis health |
| `WS` | `/ws` | Live updates pushed to approval dashboard |

### Dashboard (port 5502)
- Every pending fix shown as a card: original record → fixed record diff, Groq explanation, issues, validation errors
- **Approve** and **Reject** buttons on each card — one click, instant action
- Live status updates via WebSocket — no page refresh needed
- Sidebar shows pending / auto-approved / approved / rejected counts and auto-approve threshold

### Sample Output
```
📦 Found 2 new fix(es) to process.

🔎 Processing fix_id=fix_3_112843
   op=c confidence=95% fix_valid(W3)=True
   ✅ Layer 1 passed.   ✅ Layer 2 passed.   ✅ Layer 3 passed.
   🚀 AUTO-APPROVE — confidence=95% ≥ threshold=80%, all checks passed.
   ✅ Fix pushed to Redis for Worker 5 — fix_id=fix_3_112843

🔎 Processing fix_id=fix_4_113216
   op=c confidence=72% fix_valid(W3)=True
   ✅ Layer 1 passed.   ✅ Layer 2 passed.   ✅ Layer 3 passed.
   👤 HUMAN REVIEW required — confidence 72% < threshold 80%
   📬 Notification sent — pending human decision.
```

### File Structure
```
worker4/
├── checker_agent.py            # Main polling loop + routing logic
├── checker_dashboard.html      # Manager approval UI (port 5502)
├── applier.py                  # Legacy direct-write path (used for human approvals)
├── validators/
│   ├── schema_validator.py     # Layer 1 — JSON Schema
│   ├── pydantic_models.py      # Layer 2 — Pydantic v2 models
│   └── db_validator.py         # Layer 3 — SQLAlchemy dry-run
├── approval/
│   ├── api.py                  # FastAPI — approve/reject endpoints + WebSocket
│   ├── queue.py                # Redis queue (pending / approved / rejected / executor)
│   └── notifier.py             # Slack webhook + SMTP email alerts
├── requirements.txt
└── Dockerfile
```

---

## ✅ Worker 5 — Executor Agent *(Completed)*

The **only worker that permanently writes to MySQL**. Polls the Redis `approved_fixes` queue for fixes approved by Worker 4, takes a mysqldump backup before every batch, then applies each fix inside a SQL transaction with a SAVEPOINT checkpoint. After writing, it reads back the row to verify the data was actually stored correctly. If anything goes wrong at any step, the SAVEPOINT is rolled back — the database is never left in a bad state.

### Execution Flow

```
[Redis brpop] → [mysqldump backup] → [SAVEPOINT] → [UPDATE] → [SELECT read-back]
                                                                       ↓
                                                            values match expected?
                                                              ↙               ↘
                                                    RELEASE SAVEPOINT    ROLLBACK TO SAVEPOINT
                                                         COMMIT ✅              ❌
```

### Safety Layers

**Layer 1 — Pre-execution backup (mysqldump)**
Before every Nth fix (configurable via `BACKUP_EVERY_N`, default 10), Worker 5 runs `mysqldump` and saves a full snapshot of the database to `/backups/backup_YYYYMMDD_HHMMSS.sql`. If the dump fails, a warning is logged but execution continues. Old backups are automatically cleaned up — only the last 10 are kept.

**Layer 2 — SAVEPOINT transaction**
Every write is wrapped in a MySQL SAVEPOINT, not just a regular transaction. Think of it as a video game checkpoint inside the transaction: if the UPDATE or the read-back fails, we roll back only to the savepoint, not the entire session.

**Layer 3 — Read-back verification**
After the UPDATE, Worker 5 immediately runs a `SELECT` to read the row back and compares every written field against the expected value. If even one field doesn't match what was sent, the SAVEPOINT is rolled back and the result is reported as `ROLLED_BACK`.

### Result States

| Status | Meaning |
|---|---|
| `SUCCESS` | UPDATE executed, read-back matched, SAVEPOINT released, committed to DB |
| `ROLLED_BACK` | UPDATE ran but read-back mismatched, OR zero rows affected — change undone |
| `ERROR` | Exception before or during execution, or missing payload fields |

### Redis Queue

Worker 4 pushes approved fixes to the `approved_fixes` Redis list. Worker 5 uses `brpop` (blocking pop) — it waits idle until a fix arrives, then processes it immediately. This means there is zero polling delay.

```python
# Worker 4 pushes:
redis.lpush("approved_fixes", json.dumps({
    "record_id":    5,
    "table":        "customers",
    "fixed_record": {"name": "Rohit Singh", "phone": "NEEDS_CORRECTION"},
    "original":     {"id": 5, "name": "Rohit Sin11", "phone": "935684243A"},
    "confidence":   0.95,
    "approved_by":  "AUTO",
    "explanation":  "Fixed typo in name. Phone is invalid.",
    "ts":           "14:30:00"
}))

# Worker 5 picks up with brpop — zero polling delay
```

### Dashboard (port 5503)
- Live execution feed — every fix attempt shown as a card: original → applied fields, status badge, confidence, who approved
- Backup events shown inline with file path and size
- Sidebar: total executed, success count, rolled back count, errors, auto vs human approvals, last backup path
- WebSocket connection on port 8768 — updates in real time, auto-reconnects on disconnect

### Sample Output
```
⚡ Executor Agent starting — connecting to Redis …
✅ Executor ready — polling Redis queue 'redis:approved_fixes'
   Backup every 10 fix(es) | WebSocket on port 8768

📋 1 fix(es) waiting in queue.
📬 Fix dequeued — record_id=3 approved_by=AUTO confidence=0.95
🔧 Processing fix for record id=3 ...
📸 Backup triggered (every 10 fixes) ...
✅ Backup complete — /backups/backup_20260623_194914.sql (42 KB)
💾 SAVEPOINT created for record id=3
✏️  UPDATE executed — 1 row(s) affected
✅ Fix COMMITTED — id=3 fields=['name', 'phone'] values=['Rohit Singh', 'NEEDS_CORRECTION']
```

### Tests

Worker 5 ships with a full pytest suite covering all critical paths — no live database required:

| Test | What it covers |
|---|---|
| `test_missing_record_id` | Returns `ERROR` when `record_id` is absent |
| `test_missing_fixed_record` | Returns `ERROR` when `fixed_record` is absent |
| `test_empty_fixed_record` | Returns `ERROR` for empty `fixed_record` dict |
| `test_success_with_mock_db` | Mocks SQLAlchemy engine, verifies `SUCCESS` path end-to-end |
| `test_rollback_on_mismatch` | Simulates read-back mismatch, verifies `ROLLED_BACK` |
| `test_rollback_on_zero_rows` | Simulates unknown `record_id`, verifies `ROLLED_BACK` |
| `test_backup_mysqldump_not_found` | Returns clean failure when `mysqldump` is absent |
| `test_backup_success` | Verifies backup file is created and `success=True` |
| `test_backup_nonzero_exit` | Returns failure dict when mysqldump exits with error code |
| `test_clean_old_backups` | Verifies only last N backup files are kept |

Run tests:
```bash
pytest worker5/tests/ -v
```

### File Structure
```
worker5/
├── executor_agent.py           # Main loop — Redis poll + backup + write + broadcast
├── db/
│   ├── connection.py           # SQLAlchemy engine factory
│   └── writer.py               # Core write logic — SAVEPOINT + UPDATE + read-back
├── redis_queue/
│   └── redis_consumer.py       # brpop consumer + queue_length helper
├── safety/
│   └── backup.py               # mysqldump + clean_old_backups
├── dashboard/
│   └── dashboard.html          # Execution feed dashboard (WebSocket port 8768)
├── tests/
│   ├── test_writer.py          # 6 pytest tests for db/writer.py
│   └── test_backup.py          # 5 pytest tests for safety/backup.py
├── backups/                    # mysqldump .sql files saved here (host-mounted volume)
├── requirements.txt
└── Dockerfile
```

### Requirements
```
sqlalchemy==2.0.30
pymysql==1.1.0
redis==5.0.4
websockets==12.0
python-dotenv==1.0.1
pytest==8.2.0
```

The Dockerfile installs `default-mysql-client` (provides the `mysqldump` binary) alongside the Python dependencies.

---

## 🔜 Worker 6 — Diary Keeper *(Coming)*

Logs every fix permanently in an append-only audit table. Also feeds fixes back into the ChromaDB memory so Worker 3 gets smarter over time.

**Planned tech:** MySQL audit table + Python logging + ChromaDB memory update

---

## 🎯 Project Goals

- Build a production-ready, self-healing database monitoring system
- Zero polling — pure event-driven CDC architecture
- AI that gets smarter with every fix it makes
- Human in the loop for sensitive data corrections
- Full audit trail of every change ever made
