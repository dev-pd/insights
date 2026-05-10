from app.llm.prompts.summary_v1 import SUMMARY_PROMPT, SUMMARY_VERSION
from app.llm.prompts.v1 import PROMPT as V1_PROMPT
from app.llm.prompts.v1 import VERSION as V1_VERSION

# Switching the active prompt is a one-line change here. Keep old version
# files in the repo indefinitely so traces of past extractions can be
# reproduced. Same convention applies to the summary prompt family.
ACTIVE_PROMPT = V1_PROMPT
ACTIVE_VERSION = V1_VERSION

ACTIVE_SUMMARY_PROMPT = SUMMARY_PROMPT
ACTIVE_SUMMARY_VERSION = SUMMARY_VERSION

__all__ = [
    "ACTIVE_PROMPT",
    "ACTIVE_SUMMARY_PROMPT",
    "ACTIVE_SUMMARY_VERSION",
    "ACTIVE_VERSION",
    "SUMMARY_PROMPT",
    "SUMMARY_VERSION",
    "V1_PROMPT",
    "V1_VERSION",
]
