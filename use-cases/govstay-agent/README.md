# GovStay Agent

An Agent Kernel based multi-agent system designed to assist government employees with checking circuit bungalow availability, verifying employee IDs, and creating bookings.

## Architecture

This project is built using LangGraph and orchestrated via a Supervisor pattern:

- **Supervisor (Triage) Agent**: Evaluates user queries and routes them to specialized agents.
- **Search Agent**: Connects to the local PostgreSQL database to find available rooms based on location.
- **Verification Agent**: Queries the `users` table to verify a government employee ID.
- **Booking Agent**: Manages booking requests for circuit bungalows.

### Security
A custom Agent Kernel `PreHook` (`GeminiPromptInjectionHook`) is attached to the main supervisor. It intercepts all user input and uses a fast LLM pass to detect and block Prompt Injections, SQL injections, and malicious commands before they can execute any tools.

## Setup

1. Create a `.env` file in this directory with the following variables:
   ```env
   AK_EXECUTION__MODE=stream
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
   GEMINI_API_KEY=your_google_gemini_api_key
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Agent

You can run the agent locally in the terminal using the Agent Kernel CLI:

```bash
python demo.py
```
