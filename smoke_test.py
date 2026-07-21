"""One-question, no-LLM end-to-end smoke test for the permitted test area.

This is intentionally not the production architecture. It verifies account
classification, question retrieval, forecast posting, and the mandatory private note
while sponsored LLM access is pending. It will never select a live tournament question.
"""

from __future__ import annotations

from forecasting_tools import BinaryQuestion, MetaculusClient

from calibration_bridge import SECONDARY_NOTE
from secondary_bot import assert_secondary_account


def main() -> None:
    assert_secondary_account()
    client = MetaculusClient()
    questions = client.get_all_open_questions_from_tournament("bot-testing-area")
    candidates = [
        question
        for question in questions
        if isinstance(question, BinaryQuestion)
        and not question.already_forecasted
        and question.community_prediction_at_access_time is not None
    ]
    if not candidates:
        print("No unforecasted binary test-area question is available; nothing posted.")
        return

    question = candidates[0]
    assert question.id_of_post is not None
    assert question.id_of_question is not None
    community = question.community_prediction_at_access_time
    assert community is not None
    prediction = max(0.01, min(0.99, 0.9 * community + 0.1 * 0.5))
    explanation = (
        f"{SECONDARY_NOTE}\n\n"
        "Private API smoke-test note for bot-testing-area only. No LLM was invoked. "
        "The temporary test forecast takes the access-time community probability and "
        "shrinks it 10% toward 50% solely to validate retrieval, forecast posting, and "
        "note delivery before sponsored model access is enabled. This is not the live "
        "Calibration Bridge tournament method."
    )

    # Post the required private note first so a successful forecast can never be left
    # without its corresponding explanation if the second request fails.
    client.post_question_comment(question.id_of_post, explanation, is_private=True)
    client.post_binary_question_prediction(question.id_of_question, prediction)
    print(
        f"Posted one labelled test-area forecast: post={question.id_of_post} "
        f"prediction={prediction:.4f}"
    )


if __name__ == "__main__":
    main()
