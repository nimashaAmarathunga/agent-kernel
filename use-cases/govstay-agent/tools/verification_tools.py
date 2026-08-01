import logging
from pydantic import BaseModel, Field
from database.db_pool import get_pool
from langchain_core.tools import tool

logger = logging.getLogger("ak.govstay.tools.verification")

class VerifyEmployeeInput(BaseModel):
    emp_id: str = Field(description="Government employee ID (e.g. '245503B').")

@tool("verify_employee", args_schema=VerifyEmployeeInput)
async def verify_employee(emp_id: str) -> str:
    """Verify a government employee by their employee ID."""
    logger.info(f"Verifying employee | emp_id={emp_id}")
    pool = await get_pool()
    async with pool.acquire() as conn:
        try:
            row = await conn.fetchrow(
                'SELECT name, "placeOfWork", position, status FROM users WHERE "empId" = $1',
                emp_id,
            )
            if not row:
                return f"Verification failed: no employee found with ID '{emp_id}'."
            return (
                f"Verified!\n"
                f"Name: {row['name']}\n"
                f"Department: {row['placeOfWork']}\n"
                f"Status: {row['status']}"
            )
        except Exception as exc:
            logger.error(f"Error verifying employee: {exc}")
            return "An error occurred during verification."

class ProcessPaymentSlipInput(BaseModel):
    booking_id: str = Field(description="The booking ID to attach the slip to.")
    slip_url: str = Field(description="The URL or file path of the uploaded payment slip.")

@tool("process_payment_slip", args_schema=ProcessPaymentSlipInput)
async def process_payment_slip(booking_id: str, slip_url: str) -> str:
    """Trigger the OCR Document AI pipeline to verify a payment slip."""
    # This tool acts as a bridge to the Python Validation Engine.
    # The LLM doesn't do the validation itself.
    from document_ai.validation_engine import run_validation_pipeline
    
    logger.info(f"Processing slip for booking {booking_id}")
    try:
        result = await run_validation_pipeline(booking_id, slip_url)
        return f"Payment Slip Processing Result: {result}"
    except Exception as exc:
        logger.error(f"Error processing slip: {exc}")
        return "An error occurred during slip processing."
