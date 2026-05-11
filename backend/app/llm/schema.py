from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Sentiment = Literal["positive", "neutral", "negative"]


class ExtractionResult(BaseModel):
    """Structured insights extracted from a single piece of customer feedback.

    Field descriptions are part of the prompt — Anthropic feeds them into the
    tool definition. Write them like instructions to a human annotator.
    """

    model_config = ConfigDict(extra="forbid")

    sentiment: Sentiment = Field(
        description="Overall emotional tone of the feedback.",
    )
    themes: list[str] = Field(
        description=(
            "1-3 topical phrases capturing what the feedback is about. "
            "Lowercased noun phrases, 1-3 words each. "
            "Examples: 'shipping speed', 'customer service', 'pricing'."
        ),
        min_length=0,
        max_length=3,
    )
    action_items: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete improvements the company could make based on this feedback. "
            "Imperative phrasing ('improve X', 'fix Y'). Empty list if nothing clear is implied."
        ),
        min_length=0,
        max_length=5,
    )
    language: str = Field(
        description="ISO 639-1 language code of the feedback text (e.g. 'en', 'es', 'el').",
        min_length=2,
        max_length=5,
    )
