# Specification: GovStay Multi-Agent System

## Overview

The GovStay agent provides natural language interactions for government employees to browse circuit
bungalows, verify their credentials, and create accommodation bookings. It uses a LangGraph-based
multi-agent architecture orchestrated by Agent Kernel.

---

## Components

### 1. Agents (LangGraph via `langgraph-supervisor`)

| Agent | Role | Model |
|-------|------|-------|
| **Triage Agent** (Supervisor) | Evaluates user intent and routes to the appropriate specialist | `gemini-2.5-flash-lite` |
| **Search Agent** | Queries the database for available rooms by location | `gemini-2.5-flash` |
| **Verification Agent** | Verifies a government employee ID against the `users` table | `gemini-2.5-flash` |
| **Booking Agent** | Creates a `PENDING` booking record in the `bookings` table | `gemini-2.5-flash` |

The lite model is intentionally used for the supervisor to conserve API rate-limit quota since
routing does not require heavy reasoning.

### 2. Tools (`tool.py` — Pydantic validated)

All tool inputs use strict Pydantic models to prevent malformed arguments from reaching the database.

| Tool | Input Schema | Database Operation |
|------|--------------|--------------------|
| `search_available_rooms` | `SearchRoomsInput(location?)` | `SELECT` join on `circuit_bungalows` + `rooms` |
| `verify_employee` | `VerifyEmployeeInput(emp_id)` | `SELECT` on `users` by `empId` |
| `create_booking` | `CreateBookingInput(emp_id, room_number, from_date, to_date)` | `INSERT` into `bookings` with `PENDING` status |

A module-level `asyncpg.Pool` (min 2, max 10 connections) is created once at startup and shared
across all tool calls, avoiding repeated TCP handshakes.

### 3. Security (`security.py` — Agent Kernel Hooks)

#### `GeminiPromptInjectionHook` (PreHook)

- Intercepts every `AgentRequestText` before it reaches any agent.
- Sends a YES/NO classification prompt to `gemini-2.5-flash-lite` to detect prompt injections,
  jailbreaks, and SQL injection attempts.
- Uses `tenacity` exponential backoff (10 s → 20 s → 40 s) to automatically retry on `429
  RESOURCE_EXHAUSTED` errors without crashing.
- Fail-open policy: if Gemini is unavailable after all retries, the request is allowed through
  to avoid blocking legitimate users during an API outage.

#### `SanitiseOutputPostHook` (PostHook)

- Scans every agent reply for internal error strings (`asyncpg`, `Traceback`, `sqlalchemy`, etc.).
- If a leak is detected, the reply is replaced with a safe generic error message.
- Appends a standard government AI disclaimer to all clean replies.

### 4. Configuration (`config.yaml`)

```yaml
execution:
  mode: rest_sync   # set to 'stream' for Next.js SSE integration

session:
  type: in_memory   # upgrade to 'redis' for durable cross-restart sessions

logging:
  level: INFO
```

### 5. Session Management

Agent Kernel's built-in session system is used via `config.yaml`. The current backend is
`in_memory` (suitable for development). For production, switch `session.type` to `redis` and
configure `session.redis.url` — no code changes are required.

---

## Future Enhancements

- **Next.js SSE integration**: Switch `config.yaml` to `execution.mode: stream` and update
  `main.py` to use Agent Kernel's built-in `RESTAPI` to stream responses to the frontend.
- **JWT authentication**: Implement `AuthValidator` in `main.py` to validate Next.js session
  tokens and bind the authenticated `userId` to each conversation.
- **Redis session persistence**: Upgrade `session.type` to `redis` for durable cross-session
  memory (e.g., remembering a verified employee ID across restarts).
- **Booking conflict detection**: Before inserting, query the `bookings` table to check whether
  the requested room is already booked for the overlapping date range.
