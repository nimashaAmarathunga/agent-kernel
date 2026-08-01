from __future__ import annotations
import logging
import re
from agentkernel.core import Agent, PreHook, Session
from agentkernel.core.model import AgentRequest, AgentRequestText, AgentReplyText

logger = logging.getLogger("ak.govstay.security")

# Regex-based security blocklist to replace the slow LLM classifier
BLOCKLIST_PATTERNS = [
    re.compile(r"ignore previous instructions", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"drop table", re.IGNORECASE),
    re.compile(r"delete database", re.IGNORECASE),
    re.compile(r"truncate table", re.IGNORECASE),
]

class RegexSecurityHook(PreHook):
    """
    Fast middleware security layer replacing the LLM classifier.
    Instantly blocks prompt injections and SQL attacks using regex.
    """
    def name(self) -> str:
        return "RegexSecurityHook"

    async def on_run(
        self, session: Session, agent: Agent, requests: list[AgentRequest]
    ) -> list[AgentRequest] | AgentReplyText:
        logger.info("Security regex check | session_id=%s", session.id)

        for request in requests:
            if not isinstance(request, AgentRequestText):
                continue

            prompt_text = request.text
            
            for pattern in BLOCKLIST_PATTERNS:
                if pattern.search(prompt_text):
                    logger.warning(f"Malicious pattern blocked by RegexSecurityHook | session_id={session.id}")
                    return AgentReplyText(
                        session_id=session.id,
                        text=(
                            "⚠️ SECURITY ALERT: Your request contains blocked terminology "
                            "and cannot be processed. Please rephrase your query."
                        ),
                    )

        logger.info("Security regex check passed | session_id=%s", session.id)
        return requests
