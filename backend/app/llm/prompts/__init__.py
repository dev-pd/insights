from app.llm.prompts.v1 import PROMPT as V1_PROMPT
from app.llm.prompts.v1 import VERSION as V1_VERSION

# Switching the active prompt is a one-line change here. Keep old version
# files in the repo indefinitely so traces of past extractions can be
# reproduced.
ACTIVE_PROMPT = V1_PROMPT
ACTIVE_VERSION = V1_VERSION

__all__ = ["ACTIVE_PROMPT", "ACTIVE_VERSION", "V1_PROMPT", "V1_VERSION"]
