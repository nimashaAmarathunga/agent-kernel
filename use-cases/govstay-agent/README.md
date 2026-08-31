# GovStay Agent

## 1. Problem Statement
Government employees frequently struggle with the manual and time-consuming process of checking circuit bungalow availability, verifying their employee credentials, and making accommodation bookings. The lack of an integrated, natural-language interface makes accessing these services inefficient and prone to errors.

## 2. Solution Overview
GovStay is an AI-powered, multi-agent system built on the **Agent Kernel** framework. It provides a conversational interface for government employees to effortlessly browse circuit bungalows, verify their employee IDs, and manage bookings.

The architecture uses a **LangGraph-based Supervisor pattern** with local Ollama models:
- **Triage Agent (Supervisor):** Powered by `llama3.2:3b` for fast, lightweight intent routing.
- **Specialist Agents:** (Search, Verification, Booking, Notification) Powered by `qwen2.5:7b` for complex reasoning and precise tool-calling capabilities.
- **Security:** A custom `RegexSecurityHook` runs as a pre-hook to instantly detect and block prompt injections and SQL attack patterns without incurring API overhead or latency.

## 3. Setup Instructions

1. **Install Prerequisites:**
   - Python 3.12 or higher
   - [Ollama](https://ollama.com/) (running locally)

2. **Pull Local Models:**
   Ensure Ollama is running, then download the required models:
   ```bash
   ollama pull llama3.2:3b
   ollama pull qwen2.5:7b
   ```

3. **Configure the Environment:**
   Create a `.env` file in this directory based on the provided configuration in the code.
   ```env
   AK_EXECUTION__MODE=stream
   DATABASE_URL=postgresql://postgres.jcogzodipzjchvpcmqnu:BKGIkyfO8gkUBLMJ@aws-0-eu-west-1.pooler.supabase.com:6543/postgres?pgbouncer=true&sslmode=require&sslaccept=accept_invalid_certs
   GEMINI_API_KEY=your_google_gemini_api_key
   ```
   *(Note: The Gemini API key is currently bypassed in favor of local Ollama models, but may be required by underlying Agent Kernel initializations depending on your global settings).*

4. **Install Dependencies:**
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
   Open a **new terminal window**, activate the virtual environment, and run the CLI client:
   ```bash
   python cli_client.py
   ```
   You can now interact with the GovStay agent via the terminal prompt.
