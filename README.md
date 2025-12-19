# AquaSense AI 🌱💧

AI-powered detection of irrigation issues using simple images or short videos — no sensors required.

AquaSense AI helps farmers quickly identify clogged drip lines, leaks, and irrigation failures using computer vision, saving water, time, and crops.

---

## 🚜 The Problem

- Clogged or broken drippers often go unnoticed
- Issues are discovered too late, after crop damage
- Existing solutions often rely on expensive sensors or manual inspection

This leads to water waste, yield loss, and increased labor costs.

---

## 💡 The Solution

AquaSense AI provides a simple workflow:

1. Capture an image or short video of the irrigation line
2. Upload it via a web interface
3. Receive an AI-based analysis highlighting potential issues

No hardware. No installation. Just a phone and the field.

---

## 🧠 How It Works (High Level)

- Computer vision analyzes water flow patterns and visual indicators
- The system compares visual anomalies against learned patterns
- Results are returned as a simple, actionable response

This repository currently contains an MVP scaffold and placeholder logic to validate the system architecture.

---

## 🧱 Repository Structure

- `apps/web` — frontend static site (Vanilla JS + HTML + CSS)
- `apps/api` — backend API (FastAPI)
- `apps/ai`  — AI inference code (Python package)
- `docs`     — project docs and plans
- `scripts`  — helper run/deploy scripts

---

## ▶️ Run Locally (Docker Compose)

1. Copy `.env.example` to `.env` and set values if needed.
2. Build and start services:

```bash
docker compose up --build
