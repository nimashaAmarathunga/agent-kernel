# Specification: GovStay Multi-Agent System

## Overview

The GovStay agent provides natural language interactions for government employees to browse circuit
bungalows, verify their credentials, and create accommodation bookings. It uses a LangGraph-based
multi-agent architecture orchestrated by Agent Kernel.

---

## Components

### 1. Agents (LangGraph via Supervisor)

| Agent | Role | Model |
|-------|------|-------|
| **Triage Agent** (Supervisor) | Evaluates user intent and routes to the appropriate specialist | `llama3.2:3b` |
| **Travel Agent** | Queries the database for available rooms, locations, and facilities | `qwen2.5:7b` |
| **Verification Agent** | Verifies a government employee ID against the database | `qwen2.5:7b` |
| **Booking Agent** | Manages the booking process for circuit bungalows | `qwen2.5:7b` |
| **Notification Agent** | Handles sending notifications (e.g. via Telegram) | `qwen2.5:7b` |

The system runs on local Ollama models. The smaller, faster `llama3.2:3b` model is used for the supervisor to ensure rapid intent routing without consuming heavy compute, while the larger `qwen2.5:7b` model handles the complex reasoning required for native tool calling in the specialist agents.

### 2. Tools (Pydantic validated)

All tool inputs use strict Pydantic models to prevent malformed arguments from reaching the database. Tools are connected directly to the reasoning agent for efficient querying.

### 3. Security and Tracing (Middleware Hooks)

#### `RegexSecurityHook` (PreHook)

- Intercepts every `AgentRequestText` before it reaches the supervisor.
- Uses a fast regex-based blocklist to detect prompt injections, jailbreaks, and SQL injection attempts (e.g., matching "ignore previous instructions", "drop table", etc.).
- Instantly blocks malicious queries without any LLM API latency or cost.

#### `AuditTraceHook` (PostHook)

- Records a complete audit trail of the conversation.
- Logs interactions and ensures that session responses are traced appropriately for debugging and accountability.

### 4. Server and Execution

The application is split into two primary execution modes:
- **`server.py`**: Boots up the `RESTAPI` using Agent Kernel, listening on port 8000. It also registers the LangGraph module and applies the middleware security and tracing hooks.
- **`cli_client.py`**: A fast, terminal-based CLI client that streams responses from the REST API to the user, syncing UI state when applicable.
- **`start_all.py`**: A convenient script that concurrently starts both the server and a background `batch_verifier.py`.

---

## Future Enhancements

- **Next.js SSE integration**: Connect the Agent Kernel `RESTAPI` stream directly to the Next.js frontend application.
- **JWT authentication**: Implement an `AuthValidator` to secure REST endpoints and tie sessions to verified users.
- **Redis session persistence**: Upgrade `session.type` to `redis` in `config.yaml` for durable cross-session memory (e.g., remembering a verified employee ID across restarts).
