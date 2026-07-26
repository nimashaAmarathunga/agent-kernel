# GovStay — Remaining Work (Decisions Locked)

## ✅ What's Already Done
- Database schema, migrations, seed data
- Multi-agent Python service (govstay-agent in agent-kernel/use-cases/)
  - `search_agent` → `search_available_rooms`
  - `verification_agent` → `verify_employee`
  - `booking_agent` → `create_booking` (real DB insert)
  - `GeminiPromptInjectionHook` + `SanitiseOutputPostHook`
  - Connection pool, tenacity retry, config.yaml, pyproject.toml, SPEC.md

---

## 🔴 Remaining — Python Agent Side (agent-kernel/use-cases/govstay-agent/)

### A. `verify_document` Tool + Document Agent
- The **chat agent asks the user to upload their approval slip** mid-conversation
- Agent Kernel's **multimodal support** handles the file (PDF or image)
- Gemini vision extracts: Name, Employee ID, Dates, Purpose
- Compares extracted data against the booking record already in the session
- Returns a structured verdict: `{match: bool, confidence: float, extracted: {...}}`
- **Config needed**: enable `AK_MULTIMODAL__ENABLED=true` in `.env` and `config.yaml`

### B. `approve_booking` Tool + Approval Agent
- **Fully automated** — no human in the loop
- If document verification passes (correct name + ID + dates): `status = CONFIRMED`
- If it fails: `status = REJECTED` with reason
- Writes to DB: `approvalReason / rejectionReason`, `confidenceScore`, `auditTrace` (JSON)
- `auditTrace` records every agent step for the competition demo

### C. `send_whatsapp_notification` Tool
- Uses **Agent Kernel's built-in WhatsApp integration** (`AgentWhatsAppRequestHandler`)
- Sends confirmation message to the employee's `phoneNumber` field from the DB
- Requires: Meta WhatsApp Business API credentials (Phone Number ID + Access Token)
- **For development**: use ngrok/pinggy tunnel + your personal WhatsApp number as test recipient

---

## 🔴 Remaining — Next.js Frontend (govstay-ai/)

### D. `app/api/chat/route.ts` — Agent Kernel Proxy
- Next.js API route that forwards user messages + session_id to Agent Kernel REST API
- **Streaming**: uses `ReadableStream` + `text/event-stream` to stream SSE chunks back to the browser
- For file uploads: forwards the document as `multipart/form-data` to `/api/v1/chat-multipart`

### E. Chat UI — Real Agent Responses
- The existing chat page uses mock responses — **replace with real streaming** from the proxy route
- Show the active agent label in the chat (e.g. `[Verification Agent]`, `[Document Agent]`)
- Show an **upload button** when the agent asks for the approval slip document

### F. Admin Dashboard (per govstay-agent.md spec)
- Surface booking decisions (CONFIRMED / REJECTED)
- Show `auditTrace` for each booking — who the agent called, what it decided, confidence score
- This is the **competition demo view** that shows the real agentic workflow

---

## 🛠️ Recommended Build Order

```
Step 1 (Agent - Python):
  1. Test agent CLI end-to-end (search → verify → book)
  2. Build verify_document tool + Document Agent (multimodal)
  3. Build approve_booking tool + Approval Agent
  4. Wire send_whatsapp_notification via Agent Kernel WhatsApp API
  5. Add audit trace logging per turn → agent_sessions table

Step 2 (Frontend - Next.js):
  6. Build Next.js /api/chat/route.ts proxy (REST + SSE)
  7. Wire chat UI to real agent (streaming + upload button)
  8. Improve Admin dashboard with booking decisions + audit trace
```

---

## 🎯 Competition Demo Flow (End-to-End Target)

```
User types in Chat UI
    ↓
Next.js /api/chat route
    ↓
Agent Kernel REST API (Python)
    ↓
Triage Agent routes to:
  - Search Agent → finds available rooms
  - Verification Agent → validates employee ID
  - Document Agent → reads uploaded approval slip
  - Approval Agent → confirms/rejects booking
  - Notification → WhatsApp message sent
    ↓
DB updated (bookings + audit trace)
    ↓
Response streamed back to Chat UI
```

---

## ⚠️ Action Needed Before Building WhatsApp (Step C)

You will need a [Meta Developer account](https://developers.facebook.com/) with a WhatsApp Business App to get:
1. **Phone Number ID**
2. **Permanent Access Token**
3. **Verify Token** (any random string you choose)

For local testing, use `ngrok` or `pinggy` to tunnel the local port so Meta can reach your machine.
Your personal WhatsApp number can be the test recipient during development.
