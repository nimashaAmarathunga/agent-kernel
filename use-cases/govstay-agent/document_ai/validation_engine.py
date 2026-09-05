import logging

logger = logging.getLogger("ak.govstay.document_ai")


async def run_validation_pipeline(booking_id: str, slip_url: str) -> str:
    """
    Document AI OCR Pipeline placeholder.

    IMPORTANT: This module is NOT used by the active batch_verifier.py.
    The batch verifier handles document extraction and verification directly.

    This function exists only as a reference for future vision-model integration.
    It does NOT perform any actual verification and must NOT be used in production.
    """
    logger.warning(
        f"run_validation_pipeline called for booking {booking_id}, but this module is deprecated. "
        "Use batch_verifier.py for actual verification."
    )
    return "ERROR: This validation pipeline is deprecated. Use batch_verifier.py instead."
