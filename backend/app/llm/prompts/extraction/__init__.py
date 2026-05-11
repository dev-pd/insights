"""Extraction prompt family — selects the ACTIVE version.

Each version is an immutable file in this package. To change behavior:
  1. Create a new file (e.g., v1_2.py) with the new PROMPT + VERSION
  2. Update the imports below to point ACTIVE_* at the new version
  3. Run the eval harness; commit when it passes

Older versions stay forever — llm_usage rows reference them by their
VERSION string, and trace reproducibility requires the original text.
"""

from app.llm.prompts.extraction.v1 import PROMPT as V1_PROMPT
from app.llm.prompts.extraction.v1 import VERSION as V1_VERSION
from app.llm.prompts.extraction.v1_1 import PROMPT as V1_1_PROMPT
from app.llm.prompts.extraction.v1_1 import VERSION as V1_1_VERSION
from app.llm.prompts.extraction.v1_2 import PROMPT as V1_2_PROMPT
from app.llm.prompts.extraction.v1_2 import VERSION as V1_2_VERSION
from app.llm.prompts.extraction.v1_3 import PROMPT as V1_3_PROMPT
from app.llm.prompts.extraction.v1_3 import VERSION as V1_3_VERSION

# Single source of truth for "which version is live in production".
ACTIVE_PROMPT = V1_3_PROMPT
ACTIVE_VERSION = V1_3_VERSION

__all__ = [
    "ACTIVE_PROMPT",
    "ACTIVE_VERSION",
    "V1_PROMPT",
    "V1_VERSION",
    "V1_1_PROMPT",
    "V1_1_VERSION",
    "V1_2_PROMPT",
    "V1_2_VERSION",
    "V1_3_PROMPT",
    "V1_3_VERSION",
]
