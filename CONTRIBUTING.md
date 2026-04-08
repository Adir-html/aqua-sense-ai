# Contributing to AquaSense AI

Thank you for your interest in contributing! AquaSense AI is an open-source project built to help farmers — every contribution matters.

## Ways to Contribute

### 🌾 Field Images (Most Needed)
Labeled photos of irrigation systems, water sources, and crops are our most valuable resource. If you're a farmer or agronomist:
- Open an issue with the tag **`dataset`**
- Share photos of: drip lines, sprinklers, water channels, soil, crops (healthy or affected)
- Label what you see (optional but very helpful)

### 🐛 Bug Reports
Open an issue with the **`bug`** label. Include:
- What you did
- What you expected
- What actually happened
- Browser/OS if it's a UI issue

### 💡 Feature Requests
Open an issue with the **`enhancement`** label. Describe:
- The problem you're trying to solve
- Your proposed solution (or just the problem — we'll figure it out together)

### 🌍 Translations
The app is currently English-only. If you can translate the UI or documentation into another language, open an issue with the **`translation`** label.

### 💻 Code Contributions

1. Fork the repository
2. Create a branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run the tests: `cd apps/api && pytest tests/`
5. Open a pull request

#### Development Setup

```bash
git clone https://github.com/Adir-html/aqua-sense-ai.git
cd aqua-sense-ai
cp .env.example .env
# Add your GEMINI_API_KEY to .env
docker compose up --build
```

#### Code Style
- Python: follow PEP 8, use type hints
- JavaScript: vanilla JS, no build step required
- Keep PRs focused — one thing per PR

## Questions?

Open an issue or discussion — we respond to everything.
