from __future__ import annotations
import logging
from dotenv import load_dotenv

load_dotenv()

from agentkernel.api import RESTAPI
from agentkernel.langgraph import LangGraphModule

from workflows.graph import AGENTS, triage_agent
from middleware.security import RegexSecurityHook
from middleware.tracing import AuditTraceHook

logger = logging.getLogger("ak.govstay_server")

def main() -> None:
    logger.info("Starting GovStay Multi-Agent REST Server (Optimized v2)...")

    # Register all agents with Agent Kernel
    module = LangGraphModule(AGENTS)

    # Attach PreHook: fast regex blocks prompt injections
    module.pre_hook(triage_agent, [RegexSecurityHook()])

    # Attach PostHook: logs audit trace
    module.post_hook(triage_agent, [AuditTraceHook()])

    logger.info("GovStay agent API ready on port 8000.")
    RESTAPI.run()

if __name__ == "__main__":
    main()
