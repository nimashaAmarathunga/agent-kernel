import logging
from dotenv import load_dotenv

load_dotenv()

from agentkernel.api import RESTAPI

# Import the agent graph to register it with Agent Kernel
import agent

logger = logging.getLogger("ak.govstay_server")

if __name__ == "__main__":
    logger.info("Starting GovStay Agent REST Server...")
    # Make sure to set AK_EXECUTION__MODE=stream for SSE streaming!
    RESTAPI.run()
