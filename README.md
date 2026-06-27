# 🎫 IT Helpdesk Ticket Triage Bot

> An **AI application** that turns a raw support ticket into structured, actionable triage — **category, priority (P1–P4), routing, summary, and a draft reply** — using an LLM, with a zero-setup offline mode so it runs anywhere.

A compact, production-minded example of building with LLMs: structured outputs, a provider-agnostic integration layer, graceful fallback, a CLI, batch processing, and a web UI.

<!-- TODO: record a 20–30s screen capture, convert to GIF (LICEcap / ShareX), save as docs/demo.gif, and uncomment: -->
<!-- ![Demo](docs/demo.gif) -->

---

## The problem

Support teams receive hundreds of free-form tickets a day. Before anyone can help, each one has to be read, categorized, prioritized, and routed — repetitive work that delays the fix. This app automates that first step consistently, and drafts a reply so the human starts from 80%, not zero.

## What it does

For any ticket, it returns structured JSON:

| Field | Example |
|-------|---------|
| `category` | `Email/M365` |
| `priority` | `P2` |
| `suggested_team` | `M365/Collaboration` |
| `summary` | One-line summary of the issue |
| `draft_response` | A professional first reply to the user |
| `confidence` | `0.82` |

See [`sample_output.md`](sample_output.md) for real output across all 12 sample tickets.

## How it works

```
ticket text ──> prompt builder ──> LLM (Claude / OpenAI) ──> JSON parser ──> triage result
                                        │
                                        └── no API key? ──> deterministic fallback classifier
```

Three modes, selected by the `LLM_PROVIDER` environment variable:

- **`mock`** (default) — rule-based classifier, **no API key or dependencies required**. Lets anyone run and demo the app instantly.
- **`anthropic`** — Claude API (`ANTHROPIC_API_KEY`).
- **`openai`** — OpenAI API (`OPENAI_API_KEY`).

If a live call fails (bad key, no network, malformed output), it logs a warning and **falls back to mock mode** instead of crashing.

## Engineering decisions

- **Structured outputs over free text** — the model is constrained to a fixed JSON schema, with a tolerant parser that strips code fences and extracts the JSON object, so downstream code can rely on it.
- **Provider-agnostic** — swapping Claude ↔ OpenAI is a single environment variable; the same abstraction you'd use to keep an app vendor-neutral.
- **Fails safe** — the app degrades to a deterministic mode rather than erroring in front of a user.
- **Domain-accurate taxonomy** — categories, priorities, and routing mirror how a real service desk actually triages (informed by hands-on IT operations experience).

## Quick start

```bash
# 1. Clone
git clone https://github.com/rperezga/helpdesk-triage-bot.git
cd helpdesk-triage-bot

# 2. Run a single ticket (mock mode — no setup needed)
python triage.py "Outlook won't open and I can't get my email"

# 3. Batch-process the sample tickets into a CSV report
python triage.py --batch sample_tickets.json --out report.csv
```

### Using a live LLM (optional)

```bash
pip install -r requirements.txt
cp .env.example .env        # then set LLM_PROVIDER and your API key
python triage.py --text "VPN keeps dropping at home" --provider anthropic --pretty
```

### Web UI (optional)

```bash
pip install streamlit
streamlit run app.py
```

## Tech stack

`Python` · `Anthropic / OpenAI APIs` · `LLM prompt engineering` · `argparse CLI` · `Streamlit` · standard-library `csv`/`json`

## Project structure

```
triage.py           # core logic + CLI (single ticket & batch)
app.py              # Streamlit UI
sample_tickets.json # 12 realistic sample tickets
sample_output.md    # example results
requirements.txt    # optional dependencies
.env.example        # configuration template
```

## Roadmap

- Pull tickets straight from an Outlook inbox or a Freshdesk/Jira queue (free tiers).
- A no-code version of the same flow in Power Automate / Make, documented side-by-side.
- Confidence-based routing: auto-resolve high-confidence FAQs, escalate the rest.
- Deploy the Streamlit app so it can be tried live.

---

**Author:** Roger Perez — AI Solutions Builder (LLM apps · Low-Code/No-Code) · Miami, FL
MIT licensed.
