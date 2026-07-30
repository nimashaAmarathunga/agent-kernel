from __future__ import annotations

import logging
from dotenv import load_dotenv

load_dotenv()

from agentkernel.api import RESTAPI
from agentkernel.langgraph import LangGraphModule

from agent import AGENTS, triage_agent
from security import GeminiPromptInjectionHook, SanitiseOutputPostHook, AuditTracePostHook

logger = logging.getLogger("ak.govstay_server")

def main() -> None:
    logger.info("Starting GovStay Multi-Agent REST Server...")

    # Register all agents with Agent Kernel
    module = LangGraphModule(AGENTS)

    # Attach PreHook: blocks prompt injections before reaching any agent
    module.pre_hook(triage_agent, [GeminiPromptInjectionHook()])

    # Attach PostHook: sanitises output and appends disclaimer, and logs audit trace
    module.post_hook(triage_agent, [SanitiseOutputPostHook(), AuditTracePostHook()])

    logger.info("GovStay agent API ready on port 8000.")
    # Run the Agent Kernel REST API (FastAPI under the hood)
    RESTAPI.run()

if __name__ == "__main__":
    main()
