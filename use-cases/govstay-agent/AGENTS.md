# GovStay Agents Documentation

This document describes the roles and topology of the agents powering the GovStay system.

## Topology

The system is built as a **LangGraph Supervisor architecture**. All conversations begin at the **Triage Agent** (Supervisor). The Supervisor does not answer questions directly; its only job is to route the user's intent to one of the available specialist agents.

Once a specialist agent completes its task, the control is returned to the user (via the `END` node) rather than looping endlessly.

### The Supervisor (`supervisor.py`)

- **Role:** Router.
- **Model:** `llama3.2:3b` (via Ollama).
- **Prompt Logic:** Analyzes the last 3 messages of the conversation history. It strictly outputs a single word corresponding to the appropriate specialist agent (`travel_agent`, `booking_agent`, `verification_agent`, or `notification_agent`).
- **Performance:** Configured with `temperature=0.0` and `max_tokens=5` to ensure ultra-fast and deterministic routing decisions.

### Specialist Agents

All specialist agents are initialized using LangGraph's `create_react_agent` with the `qwen2.5:7b` model, which excels at tool calling and complex reasoning.

#### 1. Travel Agent (`travel_agent.py`)
- **Role:** Handles queries related to circuit bungalow locations, availability, and facilities.
- **Tools:** `search_bungalows`, `get_locations`, `get_facilities`.
- **Behavior:** Acts as a travel planning expert. If the user wants to initiate a booking, it guides them to provide the necessary details (Employee ID, dates, room number) so the Booking Agent can take over.

#### 2. Booking Agent (`booking_agent.py`)
- **Role:** Manages the actual booking process and reservation inquiries.
- **Tools:** Equipped with tools to verify booking availability and create reservations.
- **Behavior:** Ensures all required constraints (like valid dates and verified user status) are met before confirming a booking.

#### 3. Verification Agent (`verification_agent.py`)
- **Role:** Dedicated to verifying government employee credentials.
- **Tools:** Accesses the employee database to cross-reference provided IDs.
- **Behavior:** Confirms identity securely before allowing users to finalize sensitive actions like booking.

#### 4. Notification Agent (`notification_agent.py`)
- **Role:** Handles external communications.
- **Tools:** Integrates with Telegram via `telegram_helper.py` to send alerts and booking confirmations.
- **Behavior:** Dispatches messages to the user asynchronously.
