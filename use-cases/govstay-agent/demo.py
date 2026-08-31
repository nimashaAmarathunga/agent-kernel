from __future__ import annotations

import logging
from dotenv import load_dotenv

load_dotenv()

from agentkernel.cli import CLI
from agentkernel.langgraph import LangGraphModule

from workflows.graph import AGENTS, triage_agent
from middleware.security import RegexSecurityHook
from middleware.tracing import AuditTraceHook

logger = logging.getLogger("ak.govstay_demo")


def main() -> None:
    logger.info("Initialising GovStay Multi-Agent System...")

    # Register all agents with Agent Kernel
    module = LangGraphModule(AGENTS)

    # Attach PreHook: blocks prompt injections before reaching any agent
    module.pre_hook(triage_agent, [RegexSecurityHook()])
    
    # Attach PostHook: audit tracing
    module.post_hook(triage_agent, [AuditTraceHook()])


    logger.info("GovStay agent ready. Security hooks active.")
    CLI.main()


if __name__ == "__main__":
    main()
