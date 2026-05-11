"""Summary prompt family — selects the ACTIVE version.

Each version is an immutable file in this package. To change behavior:
  1. Create a new file (e.g., v1_2.py) with the new PROMPT + VERSION
  2. Update the imports below to point ACTIVE_* at the new version
  3. Run the eval harness (if/when summary evals exist); commit when passing

Older versions stay forever — llm_usage rows reference them by their
VERSION string, and trace reproducibility requires the original text.
"""

from app.llm.prompts.summary.v1 import PROMPT as V1_PROMPT
from app.llm.prompts.summary.v1 import VERSION as V1_VERSION
from app.llm.prompts.summary.v1_1 import PROMPT as V1_1_PROMPT
from app.llm.prompts.summary.v1_1 import VERSION as V1_1_VERSION
from app.llm.prompts.summary.v1_2 import PROMPT as V1_2_PROMPT
from app.llm.prompts.summary.v1_2 import VERSION as V1_2_VERSION

ACTIVE_PROMPT = V1_2_PROMPT
ACTIVE_VERSION = V1_2_VERSION

__all__ = [
    "ACTIVE_PROMPT",
    "ACTIVE_VERSION",
    "V1_PROMPT",
    "V1_VERSION",
    "V1_1_PROMPT",
    "V1_1_VERSION",
    "V1_2_PROMPT",
    "V1_2_VERSION",
]
