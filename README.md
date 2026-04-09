<div align="center">

# 🌱💧 AquaSense AI

### AI-powered irrigation diagnostics for farmers — no sensors, no hardware, just a phone.

[![CI](https://github.com/Adir-html/aqua-sense-ai/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/Adir-html/aqua-sense-ai/actions/workflows/ci-cd.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Sponsor](https://img.shields.io/badge/Sponsor-%E2%9D%A4-pink?logo=github-sponsors)](https://github.com/sponsors/Adir-html)

</div>

---

> **70% of global freshwater is used in agriculture — much of it wasted due to undetected irrigation faults.**
> AquaSense AI gives every farmer precision diagnostics at zero hardware cost.

**Upload a field photo → AI instantly diagnoses water quality, irrigation faults, and crop health.**

---

## 🎥 Demo

> **[➡ Try the live demo](https://aqua-sense-ai-two.vercel.app)** · [Watch 60-second walkthrough](#)

![AquaSense AI Dashboard](docs/screenshot.png)

_Batch-analyze entire fields in seconds. Get clear, actionable recommendations per zone._

---

## 🚜 The Problem

Every year, farmers lose **billions of dollars** to irrigation failures that are invisible to the naked eye — until it's too late:

| Problem | Impact |
|---------|--------|
| Clogged drippers | Uneven watering → 20–40% yield loss |
| Undetected leaks | Wasted water, root disease, soil erosion |
| Late diagnosis | Issues found after crop damage, not before |
| Sensor alternatives | Cost $500–$5,000+ per field, require installation |

**Existing tools are expensive, complex, or too slow.** Smallholder farmers — who feed most of the world — are left with nothing.

---

## 💡 The Solution

AquaSense AI is a **free, open-source web app** that turns any smartphone photo into an irrigation audit:

1. 📷 **Capture** — take a photo of your field, drip line, or water source
2. ⬆️ **Upload** — drag and drop into the dashboard (or batch-upload an entire field)
3. 🤖 **Analyze** — Gemini Vision AI diagnoses issues in seconds
4. 📋 **Act** — get a clear recommendation with urgency level

No sensors. No installation. No expertise needed.

---

## ✨ Features

- **AI Vision Analysis** — Gemini 2.0 Flash detects turbid water, clogged emitters, algae, leaks, soil issues, crop stress, and more across 20+ issue types
- **Batch Upload** — analyze an entire field at once with progress tracking
- **Field Zone Dashboard** — track health per zone with historical trend charts
- **History & Search** — full scan history with date/issue filters and CSV export
- **Offline-ready PWA** — installable on any device, works on slow connections
- **API-first** — REST API with OpenAPI docs for integration with farm management systems
- **Self-hostable** — Docker Compose for on-premise deployment; no data leaves your server
- **Open dataset** — every analysis can contribute to an open agricultural image dataset

---

## 🚀 Quick Start

### Option A — One-click cloud deploy (free)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/Adir-html/aqua-sense-ai&env=GEMINI_API_KEY,DATABASE_URL&envDescription=Add%20your%20Gemini%20API%20key%20and%20a%20Postgres%20DATABASE_URL&project-name=aquasense-ai)

### Option B — Docker Compose (local / your own server)

```bash
git clone https://github.com/Adir-html/aqua-sense-ai.git
cd aqua-sense-ai

cp .env.example .env
# Edit .env and add your GEMINI_API_KEY (free at https://aistudio.google.com/app/apikey)

docker compose up --build
```

Open **http://localhost:3001** — the dashboard is live.

> **Get a free Gemini API key:** [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
> The free tier handles thousands of analyses per day.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser / PWA  (Vanilla JS + nginx)             │
│  - Drag & drop upload, batch queue               │
│  - Real-time results dashboard                   │
│  - Zone heatmap, trend charts, history           │
└────────────────────┬────────────────────────────┘
                     │ REST API
┌────────────────────▼────────────────────────────┐
│  FastAPI (Python)                                │
│  - /api/analyze   — AI inference endpoint        │
│  - /api/analyses  — history + filters + export   │
│  - /api/stats     — zone aggregates + trends     │
└────────────────────┬────────────────────────────┘
                     │
       ┌─────────────┴─────────────┐
       │                           │
┌──────▼──────┐           ┌────────▼───────┐
│ Gemini 2.0  │           │  PostgreSQL     │
│ Flash Vision│           │  (scan history) │
│ (AI engine) │           │                 │
└─────────────┘           └─────────────────┘
```

**AI inference tiers** (automatic fallback):
1. **Gemini 2.0 Flash** — production vision AI (recommended)
2. **ONNX local model** — offline / private deployment
3. **Heuristic engine** — always available, zero dependencies

---

## 📁 Repository Structure

```
aqua-sense-ai/
├── apps/
│   ├── api/          # FastAPI backend (Python)
│   ├── web/          # Frontend (Vanilla JS + nginx)
│   └── ai/           # AI inference package
├── src/
│   └── api/          # Shared API routers & inference
├── scripts/          # Setup, import, training scripts
├── models/           # ONNX model files
└── docs/             # Documentation
```

---

## 🌍 Roadmap

- [x] AI-powered single image analysis (Gemini 2.0 Flash)
- [x] Batch upload with progress tracking
- [x] Field zone dashboard with trend charts
- [x] CSV export & print reports
- [x] PWA — installable on mobile
- [ ] Mobile app (React Native)
- [ ] Video analysis (short clip → frame sampling)
- [ ] Drone image support (GeoTIFF / orthomosaic)
- [ ] WhatsApp bot for low-connectivity regions
- [ ] Multi-language support (Spanish, Hindi, Swahili)
- [ ] Open training dataset portal
- [ ] IoT sensor integration (optional enhancement)

---

## 🤝 Contributing

Contributions are warmly welcome — especially from farmers, agronomists, and developers in agricultural regions.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**High-priority contributions needed:**
- 🌾 Labeled field images for training data
- 🌍 Translations (Spanish, Arabic, Hindi, French)
- 🧪 Real-world testing & feedback from farmers
- 🐛 Bug reports and feature requests

---

## 💰 Support This Project

AquaSense AI is free and open source. If it helps you or you believe in its mission:

- ⭐ **Star this repo** — it's free and helps more farmers find it
- 💖 **[Sponsor on GitHub](https://github.com/sponsors/Adir-html)** — fund ongoing development
- ☕ **[Buy me a coffee](https://ko-fi.com/aidwithadir)** — one-time support
- 📢 **Share it** — post on LinkedIn, Reddit, or with your agricultural network
- 🤝 **Partner with us** — if you're an agricultural organization or NGO, let's talk
- ☕ Support the project: https://ko-fi.com/aidwithadir

Funds go toward: cloud hosting for the live demo, training data labeling, and development time for features that benefit smallholder farmers.

---

## 📄 License

MIT — free to use, modify, and deploy, including commercially. See [LICENSE](LICENSE).

---

## 📬 Contact

Built by **Adir Shohat** · Questions, partnerships, or press: open an [issue](https://github.com/Adir-html/aqua-sense-ai/issues) or reach out on [LinkedIn](https://www.linkedin.com/in/adir-shohat-6a3479384/).

---

<div align="center">

**If AquaSense AI saves even one farmer's harvest, it's worth building.**

⭐ Star this repo to help more farmers find it ⭐

</div>
