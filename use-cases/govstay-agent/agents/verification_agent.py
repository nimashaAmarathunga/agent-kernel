from langgraph.prebuilt import create_react_agent
from tools.verification_tools import verify_employee, process_payment_slip
from config import get_model

model = get_model(role="reasoning", temperature=0.0)

verification_agent = create_react_agent(
    model=model,
    tools=[verify_employee, process_payment_slip],
    prompt=(
        "You are GovStay's strict compliance officer. "
        "To verify an employee, use `verify_employee(emp_id)`. "
        "If they upload a payment slip, use the `process_payment_slip` tool to trigger the OCR pipeline. "
        "IMPORTANT: Do NOT narrate your tool calls or say what functions you are using. Just give the final answer naturally."
        "Do NOT make financial decisions yourself. The tool will return AUTO_APPROVE or REJECT. "
        "Relay the final decision to the user."
    )
)
