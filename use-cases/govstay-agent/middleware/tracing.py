from __future__ import annotations
import logging
import json
from agentkernel.core import Agent, PostHook, Session
from agentkernel.core.model import AgentReply, AgentRequest

logger = logging.getLogger("ak.govstay.tracing")

class AuditTraceHook(PostHook):
    """
    Log every agent interaction to the agent_sessions.auditTrace column for observability.
    """
    def name(self) -> str:
        return "AuditTraceHook"

    async def on_run(
        self,
        session: Session,
        requests: list[AgentRequest],
        agent: Agent,
        agent_reply: AgentReply,
    ) -> AgentReply:
        from database.db_pool import get_pool
        
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT "auditTrace" FROM agent_sessions WHERE "sessionId" = $1',
                    session.id
                )
                
                trace_array = []
                if row and row["auditTrace"]:
                    trace_array = json.loads(row["auditTrace"]) if isinstance(row["auditTrace"], str) else row["auditTrace"]
                
                trace_array.append({
                    "agent": agent.name if agent else "supervisor",
                    "request": [r.model_dump() for r in requests],
                    "reply": agent_reply.text
                })
                
                await conn.execute(
                    'UPDATE agent_sessions SET "auditTrace" = $1::jsonb WHERE "sessionId" = $2',
                    json.dumps(trace_array),
                    session.id
                )
        except Exception as exc:
            logger.error("Error writing audit trace: %s", exc)

        return agent_reply
