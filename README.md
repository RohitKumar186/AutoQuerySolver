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
* Enables scalable event-driven processing.
* Forms the foundation for anomaly detection and automated query analysis.
* Supports future AI-powered monitoring and alerting systems.

---

## 🛠️ Tech Stack

* **MySQL** — Primary Database
* **Apache Kafka** — Event Streaming Platform
* **Debezium** — Change Data Capture (CDC)
* **Docker** — Containerized Deployment
* **Python** — Data Processing & Analysis
* **Git & GitHub** — Version Control

---

## 🏗️ Architecture

MySQL Database
↓
Debezium Connector
↓
Apache Kafka Topics
↓
Workers / Agents
↓
Analytics & Anomaly Detection

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

## 🔄 Upcoming Workers

### Worker 2 — Processing Agent

* Consumes events from Kafka.
* Cleans and validates incoming data.
* Filters unnecessary events.
* Prepares structured data for analysis.

### Worker 3 — Anomaly Detection Agent

* Detects suspicious or unusual database activities.
* Identifies abnormal update patterns.
* Generates alerts for critical events.
* Supports future ML-based anomaly detection.

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
