# Technical SEO & AI Discoverability Audit Agent

A bounded LangGraph workflow that samples a public business website, extracts compact technical signals, applies deterministic SEO checks, uses Gemini for contextual interpretation, and returns an evidence-backed audit with developer remediation briefs.

## Requirements

- Python 3.12 or newer
- `uv`
- A Gemini API key for real audits

## Setup

```bash
cp .env.example .env
uv sync
```

Set `SEO_AGENT_GEMINI_API_KEY` in `.env`. PageSpeed and Firecrawl keys are optional; unavailable optional measurements are reported as audit warnings.

## Run the API

```bash
uv run uvicorn seo_agent.main:app --reload
```

Submit an audit:

```bash
curl -X POST http://127.0.0.1:8000/audits \
  -H 'Content-Type: application/json' \
  -d '{"website_url":"https://example.com"}'
```

The request runs one bounded audit workflow and returns JSON. It does not persist audits or modify the target website.

## Run the frontend

The React, TypeScript, and Tailwind frontend lives in `frontend/`. Its Vite development server proxies `/audits` to the API on port 8000.

```bash
cd frontend
npm install
npm run dev
```

Keep the API running in a second terminal. The interface supports the synchronous audit flow, report JSON download, browser printing, expandable evidence, copyable remediation briefs, and responsive report navigation.

## Verify

```bash
uv sync
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run basedpyright src tests
cd frontend
npm test
npm run typecheck
npm run build
npm run test:sites
```

The default tests are offline. Live provider validation is intentionally separate because it requires credentials and external network access.

## Configuration

All runtime configuration is read through the typed settings model in `src/seo_agent/config.py`. See `.env.example` for supported environment variables and `implementation_plan.md` for the default resource budgets and safety policy.

Ordinary website requests default to a 10-second timeout. PageSpeed runs use a separate 45-second bounded timeout because Lighthouse analysis can take longer; override it with `SEO_AGENT_LIMITS__PAGESPEED_TIMEOUT_SECONDS` when needed.

## Scope

This is a representative five-page audit, not an exhaustive crawler. Missing or inaccessible information is reported as a limitation rather than interpreted as proof that a technical element does not exist.
