"""
SAFE OCR Service (Tier A — Canned Parse)
-----------------------------------------
Simulates lab-report OCR for the demo. When a user uploads a file,
parse_lab_report() returns a fixed dict of realistic lab values as if
it had actually parsed the document.

Later this is swapped for:
  - Tier B: pytesseract + regex extraction
  - Tier C: pytesseract + LLM-assisted parsing

The public interface — parse_lab_report(uploaded_file) -> dict — stays
identical across tiers, so only the internals change.
"""

from typing import Optional
import time


# Canned lab values that will "appear" when any file is uploaded.
# Chosen to look like a realistic sepsis-workup result set.
_CANNED_PARSE_RESULT = {
    "lactate":    2.8,
    "wbc":       13.6,
    "creatinine": 1.4,
    "platelets": 178,
    "bun":       26,
    "glucose":  148,
}


def parse_lab_report(uploaded_file, simulate_latency_sec: float = 1.2) -> Optional[dict]:
    """Parse an uploaded lab report and return a dict of lab values.

    Args:
        uploaded_file: Streamlit UploadedFile object (we ignore its contents
                       in Tier A — any upload returns the canned result).
        simulate_latency_sec: Pause to make the parse feel real during demo.

    Returns:
        Dict of {lab_name: numeric_value} or None if no file provided.

    TODO (Tier B): run pytesseract.image_to_string(file) and regex-match
                   common patterns like r"Lactate[:\s]+([\d.]+)".
    TODO (Tier C): pass OCR'd text to an LLM with a structured-output prompt.
    """
    if uploaded_file is None:
        return None

    # Demo pacing — a zero-latency parse feels fake
    time.sleep(simulate_latency_sec)

    # In real implementations you'd parse the file here. Tier A returns canned.
    return dict(_CANNED_PARSE_RESULT)