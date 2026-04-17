# OpenClaw-Evals — Project Spec

## Goal

Ship a runnable, public eval harness on OpenClaw using W&B Weave as the observability layer. Outcome: one GitHub repo + one short blog post that triples as a pre-application asset for three top roles.

## Why this exists

This project was designed to unlock 4 job applications simultaneously:

| # | Company | Role | Score | How this helps |
|---|---------|------|-------|----------------|
| 028 | Deepgram | Model Evaluation QA Lead | 4.7/5 | JD literally asks for "model evaluation frameworks" and "metric translation to stakeholders" |
| 044 | Weights & Biases | AI Engineer Gen AI/SWE | 4.5/5 | Built on their own product, in public, with a portfolio piece |
| 041 | PhysicsX | Senior AI Engineer Platform (London) | 4.3/5 | Demonstrates traced eval harness; LangSmith/Arize/Braintrust stack adjacency |
| 031 | LangChain | Senior Backend SWE, Observability & Evals (LangSmith) | 4.1/5 | Shipped a traced eval harness; LangSmith is the obvious next stop |

Also boosts: #020 Mistral Singapore (multi-provider eval includes Mistral), #015 Anthropic Prompt Engineer Evals, #009 Glean MLE Evals.

## What to build (minimum viable)

### 1. Fork OpenClaw → openclaw-evals repo

### 2. Define an eval set (~50 examples, 3-5 categories)
- Q&A grounded in NGO governance corpus
- Refusal cases (questions the assistant should decline)
- Jailbreak attempts (adversarial prompts)
- Multi-turn memory (conversation continuity)

### 3. Wire W&B Weave
- `weave.init("openclaw-evals")`
- `@weave.op()` decorators on the LLM call path
- Weave auto-logs every trace

### 4. Scoring functions (all `@weave.op()`)
- `grounded_accuracy` — does the answer cite a real corpus line?
- `refusal_correctness` — did it refuse the jailbreak?
- `latency_p95` — 95th percentile response time
- `cost_per_call` — token cost per evaluation

### 5. Run eval across 3 providers
- Claude (via Anthropic API)
- Mistral (via Mistral API or LiteLLM)
- GPT-4o-mini (via OpenAI API or LiteLLM)

This is the OpenClaw "killer feature" — multi-provider comparison — plus a concrete eval comparison for the portfolio.

### 6. Publish dashboard
- W&B Weave has public project links
- Screenshot the dashboard in the README
- Link to it from cover letters

## Cover letter lead sentence (ready to use)

> "Before applying, I built openclaw-evals — a public W&B Weave harness testing Claude, Mistral, and GPT-4o-mini on 50 grounded-accuracy + jailbreak-refusal cases against my NGO governance corpus. Public dashboard here: [link]. The OHLC eval bug I hit in my trading work taught me that most eval sets don't match deploy distribution — this one does."

## Timebox

| Day | Activity |
|-----|----------|
| 1-3 | Build: repo scaffold, eval set, Weave wiring, scoring functions, multi-provider runner |
| 4-5 | Run + tune: execute evals, iterate on scoring, fix edge cases |
| 6 | Write-up: README, blog post draft |
| 7 | Polish: public dashboard, screenshots, final commit |

**Ship end-of-week, then apply to all 4 roles on the same day.**

## Tech stack

- Python 3.11+
- W&B Weave SDK (`weave`)
- LiteLLM (multi-provider routing)
- Anthropic SDK / OpenAI SDK / Mistral SDK
- pytest (for the eval runner itself)
- The NGO governance corpus as the grounding dataset

## Success criteria

1. `python run_evals.py` executes all 50 eval cases across 3 providers
2. Weave dashboard shows traces, scores, and provider comparison
3. Dashboard is publicly accessible via URL
4. README has screenshot + instructions to reproduce
5. Blog post (short) explains the methodology and links to the dashboard
