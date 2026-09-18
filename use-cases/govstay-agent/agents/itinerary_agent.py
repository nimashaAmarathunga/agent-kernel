from langgraph.prebuilt import create_react_agent
from config import get_model

# Use the creative model for generating itineraries
model = get_model(role="creative", temperature=0.7)

itinerary_agent = create_react_agent(
    model=model,
    tools=[], # No tools needed, just raw generation
    prompt=(
        "You are an expert Sri Lankan travel planner for GovStay.\n"
        "The user will provide a location (where their bungalow is), "
        "their travel group, their interests, and a list of nearby attractions.\n"
        "Your task is to generate a beautiful, day-by-day travel itinerary using Markdown.\n"
        "IMPORTANT RULES:\n"
        "- NEVER use Markdown tables (e.g. | Time | Activity |). They do not render correctly.\n"
        "- Format each day with a Heading 2 (## Day 1: ...).\n"
        "- Format each activity as a bolded bullet point (e.g. - **08:00 AM - Breakfast**: Enjoy...).\n"
        "- Do NOT output markdown code blocks (e.g. ```markdown ... ```), just output the raw text.\n"
        "- Keep it concise, engaging, and highly readable using emojis.\n"
        "- Only include the attractions provided by the user if possible.\n"
    )
)
