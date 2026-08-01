import os
from dotenv import load_dotenv

load_dotenv()

# Multi-Model Architecture Configuration
# -------------------------------------
# These models dictate which LLMs handle which specific tasks in the GovStay architecture.
# Adjust these based on your local hardware capacity.

# The Router Model needs to be extremely fast with low VRAM footprint.
# It uses temperature=0.0 and max_tokens=5 to quickly decide the next agent.
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "llama3.2:3b")

# The Reasoning Model handles complex logic, state manipulation, and native tool calling.
# qwen2.5 (7b or 14b) is highly recommended for structured tool calling accuracy.
REASONING_MODEL = os.environ.get("REASONING_MODEL", "qwen2.5:7b")

# The Vision Model is used exclusively by the Document AI pipeline to read uploaded slips.
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen2.5-vl")

# Ollama Endpoint
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
