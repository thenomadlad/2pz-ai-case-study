# LLM explanations model

How each call gets its written explanation, why it's built this way, and what it can't do. The calls
themselves come from the [decision model](decision-model.md): rules make every call, and the LLM only
explains it. How AI was used to build the app is in
[App and implementation](app-and-implementation.md#how-ai-was-used-to-build-this).

## Why explain the calls with an LLM

A footprint or capital call made on large amounts of data and a model built on
stand-in signals (reviews for services sold, area rents for leases) and judgement thresholds is easy
to misread: a 0.47 rent score, a low-confidence HOLD or a 4% growth figure each needs its context.
So every call comes with its interpretation, not just its numbers: an LLM writes each lounge's and
area's explanation and the Executive Summary's one-paragraph summary, and code vets it before anyone
sees it. The
decision-maker gets the data *and* the correct reading of it.

## How an explanation is made

Every explanation is a pyramid: a one-sentence answer, 2-5 arguments, each backed by data points.
- **The code picks the arguments** (`src/explain.py:prioritize`): which signals matter and in what order is computed, not left to the LLM.
- **The Executive Summary gets a one-paragraph summary.** The page itself (headline, cards, tables) is built by rules; the LLM adds a 4-5 sentence summary of it in pyramid order: the answer, then review, defend, search for sites, then how sure to be. It counts high-confidence calls first, never adds up growth areas (they overlap), and is rejected if it says "open" or "close": GROW starts a site search and SHRINK means review.
- **The LLM writes the prose; `verify()` checks it.** Every cited value must match the fact sheet and every number in the text must be a fact or a published threshold, correctly rounded. A failure falls back to a labelled template.
- **Precomputed for this prototype.** The explanations for the baseline are generated ahead of time (offline, from the app's own prompts), verified and cached, keyed by a hash of the exact numbers, so the app needs no API key. In production, changing an assumption in the What-if explorer would have the LLM write new conclusions and summaries on the spot, through the same checks; here a changed what-if shows the labelled template instead of a stale text.
- **Rules decide, the LLM explains.** A lease or capital call has to be defensible and reproducible: the same data must give the same call and the same reasons, so an earlier LLM classifier was removed. That doesn't rule out a chatbot; it sets its guardrails. A chat could take "what if rent at City Walk were 3,000?" or "be stricter on GROW", set those assumptions in the same engine the What-if explorer uses, and have the LLM explain the new calls, with `verify()` checking every answer. The chat changes inputs; the rules still make the call.
- **Regenerate** after changing the model or data: `just explain` (API, needs `ANTHROPIC_API_KEY`),
  or offline with `python -m src.explain prompts DIR` → write the answers → `check DIR` → `ingest DIR`
  (see `justfile`). The committed explanations were written in a Claude Code session from the same
  prompts the API would get, for the current baseline, all passing the check. NOT SCORED and SKIP
  always use the template.
- **Without it**, the portfolio team would read the factor table and write the memo themselves.
  The layer saves that drafting: it picks the arguments that matter, orders them and turns them
  into board-memo prose with every number checked. It adds no new information.
- **What it can't see:** anything outside the fact sheet. No P&L, no capacity, no site visits,
  no local knowledge. The check verifies numbers, not adjectives, so a word like "strong" is unchecked.
