# openclaw-evals

Multi-provider LLM eval harness. Tests Claude, GPT-4o-mini, and Mistral against a ~50-case eval set drawn from a real-world trading-strategy corpus. Results are logged to **W&B Weave** and **LangSmith** for public inspection.

## Status

Day 1 scaffold. Smoke test works. Full eval runner lands Day 2+.

## Run the smoke test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
python run_evals.py --smoke-test
```

Expected output: three lines like `[claude] 'Paris' (input=17, output=2)` — one per provider.

## What's coming

- 50 grounded questions + refusal + jailbreak + framing-sensitivity cases
- W&B Weave + LangSmith dashboards (both publicly linkable)
- Full writeup in `BLOG.md`
