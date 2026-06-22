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
- **Worker 5** *(coming)* safely writes the approved fix back to the database
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
        ↓  (approved fixes only)
Worker 5 — Fixer    [upcoming]  ← writes fix safely to database
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
| Notifications | smtplib (Email) + Slack Webhook |
| Dashboard | Vanilla HTML/JS + WebSocket (Worker 2 → port 5500, Worker 3 → port 5501, Worker 4 → port 5502) |
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
| `watchman_redis` | 6379 | Redis queue (Worker 4) |
| `watchman_dashboard` | 5500 | Worker 2 dashboard |
| `watchman_doctor_dashboard` | 5501 | Worker 3 dashboard |
| `watchman_checker_dashboard` | 5502 | Worker 4 approval dashboard |

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

### Dashboards
| Dashboard | URL |
|---|---|
| Inspector (Worker 2) | http://localhost:5500 |
| Doctor (Worker 3) | http://localhost:5501 |
| Checker (Worker 4) | http://localhost:5502 |
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
                                                         write to MySQL          Redis queue + notify
```

| Layer | File | What it checks |
|---|---|---|
| Layer 1 — JSON Schema | `validators/schema_validator.py` | Fix payload shape — required fields, types, enum values |
| Layer 2 — Pydantic v2 | `validators/pydantic_models.py` | Field-level value rules — name format, phone regex, id > 0 |
| Layer 3 — DB dry-run | `validators/db_validator.py` | Attempts a rolled-back INSERT/UPDATE against MySQL to catch constraint violations |
| Confidence gate | `checker_agent.py` | If confidence ≥ 80% AND layers 1-3 pass → auto-approve. Otherwise → human review |

### Routing Logic

**AUTO-APPROVE path** (confidence ≥ 80%, all validations pass):
- `applier.py` writes the fix directly to MySQL
- Slack notification: "Fix applied ✅"
- No human involvement needed

**HUMAN REVIEW path** (low confidence OR validation errors):
- Fix pushed to Redis `watchman:pending` queue
- Slack + Email alert sent with original → fixed diff and Approve/Reject buttons
- Fix appears in the approval dashboard (port 5502) in real time
- Manager clicks **Approve** → `applier.py` writes to MySQL
- Manager clicks **Reject** → fix discarded, reason logged

### Approval API (port 8000)

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/pending` | List all fixes waiting for human decision |
| `GET` | `/fix/{fix_id}` | Get full payload for a specific fix |
| `POST` | `/approve/{fix_id}` | Approve a fix → immediately writes to MySQL |
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
   ✅ Fix written to MySQL — fix_id=fix_3_112843

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
├── applier.py                  # The ONLY place that writes to MySQL
├── validators/
│   ├── schema_validator.py     # Layer 1 — JSON Schema
│   ├── pydantic_models.py      # Layer 2 — Pydantic v2 models
│   └── db_validator.py         # Layer 3 — SQLAlchemy dry-run
├── approval/
│   ├── api.py                  # FastAPI — approve/reject endpoints + WebSocket
│   ├── queue.py                # Redis queue (pending / approved / rejected)
│   └── notifier.py             # Slack webhook + SMTP email alerts
├── requirements.txt
└── Dockerfile
```

## 🔜 Worker 5 — Fixer Agent *(Coming)*

The only worker that actually writes back to MySQL. Uses SQL transactions with SAVEPOINT so if anything goes wrong, it rolls back automatically — like a video game checkpoint.

**Planned tech:** SQLAlchemy + MySQL transactions + SAVEPOINT + read-back verification



## 🔜 Worker 6 — Diary Keeper *(Coming)*

Logs every fix permanently in an append-only audit table. Also feeds fixes back into the ChromaDB memory so Worker 3 gets smarter over time.

**Planned tech:** MySQL audit table + Python logging + ChromaDB memory update



## 🎯 Project Goals

- Build a production-ready, self-healing database monitoring system
- Zero polling — pure event-driven CDC architecture
- AI that gets smarter with every fix it makes
- Human in the loop for sensitive data corrections
- Full audit trail of every change ever made

