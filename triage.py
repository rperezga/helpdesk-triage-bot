"""
IT Helpdesk Ticket Triage Bot
--------------------------------
Takes a raw IT support ticket (email or free text) and returns a structured triage:
category, priority (P1-P4), suggested team, a short summary, and a draft first response.

Works in three modes:
  - anthropic : uses the Claude API   (set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY)
  - openai    : uses the OpenAI API   (set LLM_PROVIDER=openai + OPENAI_API_KEY)
  - mock      : no API key required; deterministic keyword-based fallback (default)

Usage:
  python triage.py "Outlook won't open and I can't get to my email"
  python triage.py --batch sample_tickets.json --out report.csv
  python triage.py --text "VPN keeps dropping" --pretty

Author: Roger Perez
License: MIT
"""

import argparse
import csv
import json
import os
import re
import sys

# Optional: load a local .env if python-dotenv is installed (not required for mock mode)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

CATEGORIES = [
    "Access/Account", "Hardware", "Network/Connectivity", "Software/Application",
    "Email/M365", "Security", "Other",
]
PRIORITIES = ["P1", "P2", "P3", "P4"]
TEAMS = [
    "Service Desk", "Identity/Access (AD)", "Endpoint/Desktop", "Network Team",
    "M365/Collaboration", "Security/IR", "Applications",
]

SYSTEM_INSTRUCTIONS = (
    "You are an experienced IT service desk analyst. Triage the support ticket below. "
    "Respond with ONLY a JSON object (no prose, no code fences) using exactly these keys:\n"
    '  "category"       : one of ' + str(CATEGORIES) + "\n"
    '  "priority"       : one of ["P1","P2","P3","P4"] '
    "(P1 = full outage / many users / security incident; P4 = minor request)\n"
    '  "suggested_team" : one of ' + str(TEAMS) + "\n"
    '  "summary"        : a one-sentence summary of the issue\n'
    '  "draft_response" : a short, professional first response to the user (2-4 sentences)\n'
    '  "confidence"     : a number from 0 to 1 indicating your confidence\n'
)


def build_prompt(ticket_text):
    return SYSTEM_INSTRUCTIONS + "\n--- TICKET ---\n" + ticket_text.strip() + "\n--- END ---\n"


def _extract_json(text):
    """Pull the first JSON object out of a model response, tolerating stray text/fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def classify_with_anthropic(ticket_text):
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    msg = client.messages.create(
        model=model,
        max_tokens=600,
        messages=[{"role": "user", "content": build_prompt(ticket_text)}],
    )
    return _extract_json(msg.content[0].text)


def classify_with_openai(ticket_text):
    from openai import OpenAI
    client = OpenAI()  # reads OPENAI_API_KEY
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": build_prompt(ticket_text)}],
        temperature=0,
    )
    return _extract_json(resp.choices[0].message.content)


# --- Deterministic fallback so the tool runs with zero setup -----------------
_KEYWORDS = {
    "Security": ["phish", "phishing", "malware", "virus", "ransomware", "hacked",
                 "suspicious", "breach", "spam", "compromis"],
    "Email/M365": ["outlook", "email", "mailbox", "teams", "sharepoint", "onedrive",
                   "office 365", "m365", "calendar"],
    "Network/Connectivity": ["vpn", "wifi", "wi-fi", "network", "internet", "connection",
                             "dns", "slow", "latency", "disconnect"],
    "Access/Account": ["password", "reset", "locked", "login", "log in", "account",
                       "mfa", "2fa", "access", "permission", "active directory", "ad "],
    "Hardware": ["laptop", "monitor", "printer", "keyboard", "mouse", "battery",
                 "screen", "docking", "device", "hardware"],
    "Software/Application": ["install", "application", "app ", "software", "license",
                             "update", "crash", "error", "freeze"],
}
_TEAM_BY_CATEGORY = {
    "Security": "Security/IR",
    "Email/M365": "M365/Collaboration",
    "Network/Connectivity": "Network Team",
    "Access/Account": "Identity/Access (AD)",
    "Hardware": "Endpoint/Desktop",
    "Software/Application": "Applications",
    "Other": "Service Desk",
}
_P1 = ["outage", "down", "everyone", "all users", "cannot work", "production",
       "ransomware", "breach", "hacked", "company-wide", "site is down"]
_P2 = ["urgent", "asap", "multiple", "department", "deadline", "cannot access", "blocked"]


def classify_mock(ticket_text):
    t = ticket_text.lower()
    category = "Other"
    for cat, words in _KEYWORDS.items():
        if any(w in t for w in words):
            category = cat
            break
    if any(w in t for w in _P1):
        priority = "P1"
    elif any(w in t for w in _P2) or category == "Security":
        priority = "P2"
    elif category in ("Network/Connectivity", "Email/M365", "Access/Account"):
        priority = "P3"
    else:
        priority = "P4"
    team = _TEAM_BY_CATEGORY.get(category, "Service Desk")
    summary = ticket_text.strip().split("\n")[0][:140]
    draft = (
        "Thanks for reaching out, and sorry for the trouble. I've logged this as a "
        f"{category} issue ({priority}) and routed it to the {team}. "
        "Could you confirm your device name/location and when the issue started so we can investigate quickly?"
    )
    return {
        "category": category,
        "priority": priority,
        "suggested_team": team,
        "summary": summary,
        "draft_response": draft,
        "confidence": 0.55,
    }


def classify_ticket(ticket_text, provider=None):
    provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
    try:
        if provider == "anthropic":
            result = classify_with_anthropic(ticket_text)
        elif provider == "openai":
            result = classify_with_openai(ticket_text)
        else:
            result = classify_mock(ticket_text)
    except Exception as exc:  # network/key error -> graceful fallback
        sys.stderr.write(f"[warn] {provider} call failed ({exc}); falling back to mock mode.\n")
        result = classify_mock(ticket_text)
    # Normalize / guard
    result.setdefault("confidence", 0.5)
    if result.get("priority") not in PRIORITIES:
        result["priority"] = "P3"
    return result


def print_result(ticket_text, result):
    print("=" * 64)
    print("TICKET:", ticket_text.strip().replace("\n", " ")[:120])
    print("-" * 64)
    print(f"  Category       : {result.get('category')}")
    print(f"  Priority       : {result.get('priority')}")
    print(f"  Suggested team : {result.get('suggested_team')}")
    print(f"  Summary        : {result.get('summary')}")
    print(f"  Confidence     : {result.get('confidence')}")
    print("  Draft response :")
    print("    " + str(result.get("draft_response", "")).replace("\n", "\n    "))
    print("=" * 64)


def run_batch(path, out_csv, provider=None):
    with open(path, "r", encoding="utf-8") as f:
        tickets = json.load(f)
    rows = []
    for item in tickets:
        text = item["text"] if isinstance(item, dict) else str(item)
        ticket_id = item.get("id", "") if isinstance(item, dict) else ""
        result = classify_ticket(text, provider)
        rows.append({
            "id": ticket_id,
            "ticket": text.replace("\n", " "),
            "category": result.get("category"),
            "priority": result.get("priority"),
            "suggested_team": result.get("suggested_team"),
            "summary": result.get("summary"),
            "confidence": result.get("confidence"),
            "draft_response": result.get("draft_response"),
        })
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Processed {len(rows)} tickets -> {out_csv}")


def main():
    parser = argparse.ArgumentParser(description="IT Helpdesk Ticket Triage Bot")
    parser.add_argument("text", nargs="?", help="Ticket text to triage")
    parser.add_argument("--text", dest="text_opt", help="Ticket text (alternative to positional)")
    parser.add_argument("--batch", help="Path to a JSON file of tickets")
    parser.add_argument("--out", default="report.csv", help="Output CSV path for --batch")
    parser.add_argument("--provider", help="anthropic | openai | mock (overrides LLM_PROVIDER)")
    parser.add_argument("--pretty", action="store_true", help="Print full JSON result")
    args = parser.parse_args()

    if args.batch:
        run_batch(args.batch, args.out, args.provider)
        return

    ticket = args.text or args.text_opt
    if not ticket:
        parser.error("Provide ticket text, or use --batch FILE.")
    result = classify_ticket(ticket, args.provider)
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print_result(ticket, result)


if __name__ == "__main__":
    main()
