# Reflection Loop — Proactive Agent Follow-Ups

## Overview

Make the nicode-claw agent proactive: instead of only responding when messaged or when a cron job fires, the agent periodically reflects on recent interactions and decides what's worth following up on, checking silently, or reporting to the user.

## Goals

- Agent creates follow-up intents during normal conversations
- A periodic reflection loop processes intents — executes checks, reasons about results, messages user only when noteworthy
- Reflection loop can also generate new intents by connecting patterns across conversations
- Respects user attention: quiet hours, rate limiting, priority-based filtering
- Architected to evolve toward a continuously-running event-driven agent (Approach C)

## Core Concept

After each conversation, the agent may decide something is worth checking on later and creates a **follow-up intent**. Separately, a **reflection loop** runs every 15 minutes (configurable) and:

1. Loads pending intents
2. Reviews recent conversation context from Agno memory
3. Reasons about what's worth acting on right now
4. Executes silent checks using the agent's full toolset
5. Decides whether results are worth messaging the user
6. Generates new intents from patterns it notices
7. Prunes expired intents

The reflection loop is itself an agent run — same agent, same tools, different system prompt focused on proactive reasoning.

## Follow-Up Intents

### Structure

```python
{
    "id": "uuid",
    "what": "check if AAPL price dropped below $150",
    "why": "user was watching AAPL position on 2026-04-05",
    "check_at": "2026-04-06T09:00:00",       # absolute datetime, next check
    "how": "silent_check",                     # "silent_check" or "direct_ask"
    "priority": "medium",                      # "low", "medium", "high"
    "max_checks": 3,
    "checks_done": 0,
    "status": "pending",                       # "pending", "checked", "reported", "expired"
    "created_at": "2026-04-05T14:30:00",
    "source_session_id": "abc123"              # links back to the conversation that created it
}
```

### Creation

Intents are created in two ways:

1. **During conversations** — the agent calls `create_follow_up()` as part of its normal response when it identifies something worth tracking
2. **During reflection** — the reflection loop generates new intents by reviewing recent conversations and noticing patterns

### Storage

`data/follow_up_intents.json` — consistent with existing `data/scheduled_jobs.json` pattern. Future evolution: migrate to SQLite table.

## FollowUpTools

A new Agno toolkit added to the agent with three tools:

### `create_follow_up`

```python
def create_follow_up(
    what: str,         # what to check
    why: str,          # conversational context that triggered this
    check_in: str,     # relative time: "1h", "30m", "tomorrow morning", "3 days"
    how: str = "silent_check",   # "silent_check" or "direct_ask"
    priority: str = "medium",    # "low", "medium", "high"
    max_checks: int = 3
) -> str
```

Parses `check_in` to an absolute datetime and persists the intent.

### `list_follow_ups`

```python
def list_follow_ups() -> str
```

Returns all active (non-expired) intents for the user.

### `delete_follow_up`

```python
def delete_follow_up(intent_id: str) -> str
```

Removes an intent by ID.

## Agent Instruction Addition

Added to the main agent's system prompt:

> When a conversation involves something that might benefit from a follow-up (a task in progress, a decision pending, something the user is tracking, an interesting topic), use `create_follow_up` to schedule one. Be eager — it's better to create a follow-up and have the reflection loop decide it's not worth reporting than to miss something the user would have appreciated.

## Reflection Runner

### Module: `src/nicode_claw/reflection.py`

Orchestrates the reflection loop. Called by the existing scheduler infrastructure on a configurable interval.

### Reflection System Prompt

> You are reviewing your recent interactions with the user to decide what's worth following up on. You have access to all your tools. Be proactive but respect the user's attention — only message them if you have something genuinely useful to say. A silent check that finds nothing interesting is a success, not a failure.

### Loop Logic

```
1. Load all pending intents where check_at <= now
2. Load recent conversation summaries from Agno memory (last N runs)
3. For each due intent:
   a. Execute the check using available tools (search, API, code, etc.)
   b. Evaluate: is this result noteworthy?
   c. If yes → compose message, send via Telegram
   d. If no → increment checks_done, reschedule or expire
4. Review recent conversations for new intent opportunities
5. Prune intents where checks_done >= max_checks
```

### Message Format

Proactive messages use a prefix convention so the user knows the agent is reaching out unprompted:

- **"Thinking of you"** — pattern-based, connecting dots (e.g., "You've been asking about Tokyo flights — prices just dropped")
- **"Quick follow-up"** — task follow-up (e.g., "That deploy you mentioned — did it go smoothly?")
- **"Heads up"** — monitoring alert (e.g., "AAPL dropped 5% in the last hour")

The agent selects the prefix based on intent context.

## Quiet Hours & Rate Limiting

### Quiet Hours

Configurable window where no proactive messages are sent. Intents due during quiet hours are deferred to when quiet hours end.

```
QUIET_HOURS_START=23    # 11pm
QUIET_HOURS_END=7       # 7am
```

### Rate Limiting

Maximum proactive messages per hour (default: 5). When more intents are due than the cap allows, prioritize by priority field and defer the rest.

```
MAX_PROACTIVE_MESSAGES_PER_HOUR=5
```

## Configuration

New settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `QUIET_HOURS_START` | `23` | Hour (0-23) when quiet hours begin |
| `QUIET_HOURS_END` | `7` | Hour (0-23) when quiet hours end |
| `MAX_PROACTIVE_MESSAGES_PER_HOUR` | `5` | Rate limit for proactive messages |
| `REFLECTION_INTERVAL_MINUTES` | `15` | How often the reflection loop runs |

## Files

| File | Change |
|------|--------|
| `src/nicode_claw/follow_up.py` | **New** — FollowUpTools, intent CRUD, storage |
| `src/nicode_claw/reflection.py` | **New** — ReflectionRunner, reflection loop logic |
| `src/nicode_claw/agent/agent.py` | **Modified** — add FollowUpTools to agent, add reflection prompt, create reflection agent factory |
| `src/nicode_claw/config.py` | **Modified** — add new settings |
| `src/nicode_claw/main.py` | **Modified** — start reflection loop via scheduler in post_init |
| `.env.example` | **Modified** — document new config variables |

## Evolution Toward Approach C

This architecture is intentionally shaped for future evolution:

- `follow_up_intents.json` → event store / SQLite table with richer event types
- Reflection loop's "load context → reason → act" pattern → continuously running event processor
- New event sources (webhooks, RSS feeds, APIs, GitHub notifications) become additional intent creators feeding the same loop
- The reflection prompt can grow more sophisticated with user preference modeling

The key constraint: keep the intent structure and reflection runner interface stable so new event sources and richer reasoning can be added incrementally.
