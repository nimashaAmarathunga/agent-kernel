from __future__ import annotations

import logging
from dotenv import load_dotenv

load_dotenv()

from agentkernel.cli import CLI
from agentkernel.langgraph import LangGraphModule

from agent import AGENTS, triage_agent
from security import GeminiPromptInjectionHook, SanitiseOutputPostHook

logger = logging.getLogger("ak.govstay_demo")


def main() -> None:
    logger.info("Initialising GovStay Multi-Agent System...")

    # Register all agents with Agent Kernel
    module = LangGraphModule(AGENTS)

    # Attach PreHook: blocks prompt injections before reaching any agent
    module.pre_hook(triage_agent, [GeminiPromptInjectionHook()])

    # Attach PostHook: sanitises output and appends disclaimer
    module.post_hook(triage_agent, [SanitiseOutputPostHook()])

    logger.info("GovStay agent ready. Security hooks active.")
    CLI.main()


if __name__ == "__main__":
    main()
