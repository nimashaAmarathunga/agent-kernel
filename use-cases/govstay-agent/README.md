# GovStay Agent

## 1. Problem Statement
Government employees frequently struggle with the manual and time-consuming process of checking circuit bungalow availability, verifying their employee credentials, and making accommodation bookings. The lack of an integrated, natural-language interface makes accessing these services inefficient and prone to errors.

## 2. Solution Overview
GovStay is an AI-powered, multi-agent system built on the **Agent Kernel** framework. It provides a conversational interface for government employees to effortlessly browse circuit bungalows, verify their employee IDs, and manage bookings.

The architecture uses a **LangGraph-based Supervisor pattern**:
- **Triage Agent (Supervisor):** Powered by fast routing models for lightweight intent routing.
- **Specialist Agents:** (Search, Verification, Booking, Notification) Powered by advanced reasoning models via Groq for complex logic, state manipulation, and precise tool-calling capabilities.
- **Web Frontend Integration:** The backend seamlessly connects to the GovStay Next.js web application for a complete end-to-end user experience.
- **Database:** Connects directly to a cloud Postgres database (Supabase) to manage users and bookings.
- **Security:** A custom `RegexSecurityHook` runs as a pre-hook to instantly detect and block prompt injections and SQL attack patterns without incurring API overhead or latency.

## 3. Setup Instructions

1. **Install Prerequisites:**
   - Python 3.12 or higher

2. **Configure the Environment:**
   Create a `.env` file in this directory based on the provided configuration in the code.
   ```env
   AK_EXECUTION__MODE=stream
   DATABASE_URL=postgresql://<user>:<password>@<host>:6543/postgres?pgbouncer=true&sslmode=require
   LLM_PROVIDER=groq
   GROQ_API_KEY=your_groq_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_token
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_key
   ```

3. **Install Dependencies:**
   Create a virtual environment and install the required packages:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

## 4. How to run the solution

The application is split into a REST server/background worker and a CLI client.

1. **Start the Server and Batch Verifier:**
   In your terminal (with the virtual environment activated), start the main server:
   ```bash
   python start_all.py
   ```
   This script will launch the GovStay multi-agent REST server on `localhost:8000` and start the batch verifier in the background.

2. **Interact with the Agent:**
   You can interact with the agent via the GovStay Web Frontend UI, via the Telegram Bot integration, or by running the local CLI client:
   ```bash
   python cli_client.py
   ```
