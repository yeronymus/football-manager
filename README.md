# Prague Football Manager

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-316192?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Orchestration-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?style=flat-square&logo=github-actions&logoColor=white)](https://github.com/features/actions)

A production-ready ecosystem designed to streamline match organization, player signups, team balancing, and rating calculations for amateur football communities.

## Table of Contents
- [Purpose and Solution](#purpose-and-solution)
- [Telegram Bot Link](#telegram-bot-link)
- [Tech Stack](#tech-stack)
- [Application Features](#application-features)
- [Deployment Guide](#deployment-guide)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Docker Compose Deployment](#docker-compose-deployment)
  - [CI/CD and Security Audits](#cicd-and-security-audits)
  - [Monitoring](#monitoring)

---

## Purpose and Solution
Coordinating amateur sports games often suffers from coordination overhead: tracking signups, handling late cancellations, dividing players into balanced teams, and maintaining active interest. 

This project solves these issues by providing:
- Automated, real-time signup slots with queues for backup players.
- Algorithmic team balancing to match players based on historical ELO ratings and position preferences.
- Telegram Mini App integration for an interactive, native user interface showing profiles and team lists.
- Decoupled notification routing so critical game alerts reach players instantly.

---

## Telegram Bot Link
Active Production Instance: [https://t.me/fm_metabot](https://t.me/fm_metabot)

---

## Tech Stack
- **Backend Framework:** FastAPI (REST API & Webhook hub)
- **Telegram Interface:** Aiogram 3.x (Asynchronous Telegram Bot API wrapper)
- **Database Layer:** PostgreSQL 15, SQLAlchemy 2.0 ORM, Alembic migrations
- **Caching & Broker:** Redis 7 (Look-aside cache & Redis Streams event broker)
- **CI/CD & Testing:** GitHub Actions, Ruff, pytest
- **Security Audits:** Trivy configuration scanning
- **Metrics & Logging:** Prometheus (Metrics endpoint), Elasticsearch (Structured logs)
- **Orchestration:** Docker, Docker Compose, Watchtower (CD automation), Nginx Proxy Manager (SSL termination)

---

## Application Features
- **Match Lifecycle Orchestration:** Full state tracking (created, active, completed, canceled) with transaction safety (row-level locks to prevent race conditions during signups).
- **Asymmetric Balancing Algorithms:** Multiple draft strategies (Snake draft based on rating, role balancing, and random distribution).
- **Telemetry & Interceptors:** Event-driven telemetry forwarding matching API calls to Elasticsearch backend async.
- **Robust Integration:** Resilience to Telegram Discussion forwarding mechanisms through zero-width link parsing and auto-replace procedures.

---

## Deployment Guide

### Prerequisites
- Docker Engine and Docker Compose.
- An Nginx Proxy (such as Nginx Proxy Manager) forwarding SSL traffic (port 443) to port 8000 on the host system.

### Environment Configuration
Clone the configuration template to initialize your workspace:
```bash
cp .env.example .env
```
Populate the configuration values:
- `BOT_TOKEN`: The API credential obtained from @BotFather.
- `POSTGRES_USER` & `POSTGRES_PASSWORD`: Production database credentials.
- `REDIS_PASSWORD`: Secure string password for Redis authorization.

### Docker Compose Deployment
Start the production services:
```bash
docker compose up -d
```
The database migrations (`alembic upgrade head`) execute automatically as an entrypoint hook before the application starts.

### CI/CD and Security Audits
The project is protected by a GitHub Actions workflow (`.github/workflows/deploy.yml`) on `main` and `develop` branches:
- **Linting & Code Quality:** Codebase check using Ruff.
- **Security scan:** Config scanning using Trivy to detect security vulnerabilities (e.g. running containers as root).
- **Testing:** Unit tests executed via pytest.
- **Compilation:** Automatical building of the multi-stage Docker image and publishing to GitHub Container Registry (GHCR).

### Monitoring
Application metrics are exposed via a `/metrics` Prometheus endpoint implemented through FastAPI instrumentation. 

Prometheus is configured using [monitoring/prometheus.yml](monitoring/prometheus.yml) to scrape metrics:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'football-manager-app'
    metrics_path: '/metrics'
    static_configs:
      - targets: ['app:8000']
```
