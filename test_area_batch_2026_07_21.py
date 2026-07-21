"""Post the first evidence-led, no-LLM test-area batch for codex-bot.

This dated audit script is deliberately limited to the eight open question IDs that
were present in Metaculus's bot-testing-area on 2026-07-21. It posts a private note
before every forecast, refuses any account that is not still marked secondary, and
verifies every write with a fresh API read. It cannot touch a prize tournament.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from typing import Any

import requests
from forecasting_tools import NumericDistribution, Percentile


API_BASE = "https://www.metaculus.com/api"
TEST_AREA_SLUG = "bot-testing-area"
MAX_NEW_FORECASTS_PER_RUN = 2
# Checkpointed after fresh post-level API reads. The tournament list endpoint omits
# per-user history, so explicit state prevents a dated recovery run from reforecasting
# questions whose writes were already verified.
VERIFIED_QUESTION_IDS = {
    43322,
    43323,
    43324,
    43325,
    43326,
    43329,
    43330,
    43331,
}
SECONDARY_LABEL = (
    "SECONDARY BOT — direct operator forecast in the Metaculus bot-testing-area. "
    "The account API currently reports is_primary_bot=false; this forecast is not "
    "represented as prize-eligible."
)


FORECASTS: list[dict[str, Any]] = [
    {
        "post_id": 43321,
        "question_id": 43322,
        "type": "discrete",
        # Two private notes were accepted before Metaculus exposed its minimum-CDF-
        # increment validation error; do not create a third on the corrected retry.
        "note_already_posted": True,
        "pmf": {
            3: 0.12,
            4: 0.25,
            5: 0.28,
            6: 0.19,
            7: 0.10,
            8: 0.04,
            9: 0.015,
            10: 0.005,
        },
        "reasoning": (
            "Forecast date: 2026-07-21. Brookings reported 38% A-team turnover and "
            "20% Cabinet turnover (three Cabinet positions) as of 2026-07-09, while "
            "the question counts a fixed 15-person list through year-end. Recent AP "
            "reporting also names replacements in roles on that list. I therefore "
            "put no mass below three, center the remaining five-month distribution "
            "on five departures, and retain a right tail for further second-year "
            "turnover. Evidence: https://www.brookings.edu/articles/tracking-"
            "turnover-in-the-second-trump-administration/"
        ),
    },
    {
        "post_id": 43322,
        "question_id": 43323,
        "type": "numeric",
        "percentiles": {10: 3.34, 25: 3.39, 50: 3.45, 75: 3.52, 90: 3.62},
        "reasoning": (
            "Forecast date: 2026-07-21. The resolution source's API reports 3.409% "
            "for Total Interest-bearing Debt on 2026-06-30. Only three months remain "
            "before FY2026 ends and the stock's average rate changes gradually as "
            "debt matures, so the distribution is narrow around 3.45%. Evidence: "
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/"
            "accounting/od/avg_interest_rates"
        ),
    },
    {
        "post_id": 43322,
        "question_id": 43324,
        "type": "numeric",
        "percentiles": {10: 2.80, 25: 3.15, 50: 3.55, 75: 4.05, 90: 4.75},
        "reasoning": (
            "Forecast date: 2026-07-21. The June 2026 source value is 3.409%. By "
            "FY2028, refinancing can move the stock rate materially in either "
            "direction, so I keep the median near the current/CBO-style mid-3% "
            "baseline but use a much wider rate-path distribution. Evidence: "
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/"
            "accounting/od/avg_interest_rates"
        ),
    },
    {
        "post_id": 43323,
        "question_id": 43325,
        "type": "numeric",
        "percentiles": {
            5: -32.0,
            10: -28.0,
            25: -23.0,
            50: -18.0,
            75: -13.0,
            90: -8.0,
            95: -4.0,
        },
        "reasoning": (
            "Forecast date: 2026-07-21. Silver Bulletin's current adjusted polling "
            "average is -17.4 net, after a May low of -20.2. Five months allows "
            "meaningful movement, but presidential approval is persistent; I center "
            "on -18 and allow broad political/economic tails. Evidence: "
            "https://www.natesilver.net/p/trump-approval-ratings-nate-silver-bulletin"
        ),
    },
    {
        "post_id": 43324,
        "question_id": 43326,
        "type": "date",
        "percentiles": {
            10: "2026-11-15",
            25: "2027-02-15",
            50: "2027-07-15",
            75: "2028-01-15",
            90: "2028-07-15",
        },
        "reasoning": (
            "Forecast date: 2026-07-21. Ukraine's parliament extended nationwide "
            "martial law for the twentieth time, through 2026-10-31, while the war "
            "continues. Lifting it in three quarters of eligible oblasts therefore "
            "requires a major security transition, and I assign more than half the "
            "mass beyond the question's May 2027 upper display bound. Evidence: "
            "https://en.interfax.com.ua/news/general/1184808.html"
        ),
    },
    {
        "post_id": 43325,
        "question_id": 43329,
        "type": "binary",
        "prediction": 0.12,
        "reasoning": (
            "Forecast date: 2026-07-21. Four times the specified $2.6bn baseline is "
            "$10.4bn. Forbes estimated about $6.5bn in March 2026: substantial growth "
            "and volatile holdings make a crossing possible, but it still requires "
            "roughly another 60% within five months. Probability: 12%. Evidence: "
            "https://www.forbes.com/sites/danalexander/article/the-definitive-"
            "networth-of-donaldtrump/"
        ),
    },
    {
        "post_id": 43325,
        "question_id": 43330,
        "type": "binary",
        "prediction": 0.25,
        "reasoning": (
            "Forecast date: 2026-07-21. The same $10.4bn threshold remains well above "
            "Forbes's March 2026 estimate, but the 2027-2028 window is four times "
            "longer than the remaining 2026 window and the underlying media/crypto "
            "assets are volatile. I raise, but do not make dominant, the crossing "
            "scenario. Probability: 25%. Evidence: https://www.forbes.com/sites/"
            "danalexander/article/the-definitive-networth-of-donaldtrump/"
        ),
    },
    {
        "post_id": 43326,
        "question_id": 43331,
        "type": "multiple_choice",
        "prediction": {"Democrats": 0.625, "Republicans": 0.36, "Other": 0.015},
        "reasoning": (
            "Forecast date: 2026-07-21. Decision Desk HQ's model gives Democrats a "
            "62% House-majority chance, consistent with a Democratic generic-ballot "
            "lead and the usual midterm penalty for the president's party. A narrow "
            "Republican hold remains substantial; exact ties/third-party control are "
            "rare. Forecast: Democrats 62.5%, Republicans 36%, Other 1.5%. Evidence: "
            "https://www.decisiondeskhq.com/press/decision-desk-hq-releases-2026-"
            "congressional-forecast-model"
        ),
    },
]


def api_headers() -> dict[str, str]:
    token = os.environ["METACULUS_TOKEN"]
    return {
        "Authorization": f"Token {token}",
        "User-Agent": "codex-bot-direct-test-operator/1.0",
    }


def get_post(post_id: int) -> dict[str, Any]:
    response = requests.get(
        f"{API_BASE}/posts/{post_id}/?with_cp=true",
        headers=api_headers(),
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def get_open_test_posts() -> dict[int, dict[str, Any]]:
    response = requests.get(
        f"{API_BASE}/posts/",
        headers=api_headers(),
        params={"tournaments": TEST_AREA_SLUG, "statuses": "open", "limit": 100},
        timeout=30,
    )
    response.raise_for_status()
    return {post["id"]: post for post in response.json()["results"]}


def find_question(post: dict[str, Any], question_id: int) -> dict[str, Any]:
    questions = (
        [post["question"]]
        if post.get("question")
        else post["group_of_questions"]["questions"]
    )
    return next(question for question in questions if question["id"] == question_id)


def assert_safe_account() -> None:
    account = requests.get(
        f"{API_BASE}/users/me/", headers=api_headers(), timeout=30
    )
    account.raise_for_status()
    account_data = account.json()
    if account_data.get("is_bot") is not True or account_data.get("is_primary_bot") is not False:
        raise RuntimeError("Dated secondary test script refuses this account classification")


def assert_safe_post(post: dict[str, Any]) -> None:
    project = post.get("projects", {}).get("default_project") or {}
    if project.get("slug") != TEST_AREA_SLUG or project.get("id") != 32977:
        raise RuntimeError("Refusing to write outside the official bot-testing-area")


def as_timestamp(date_text: str) -> float:
    return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()


def make_continuous_cdf(question: dict[str, Any], plan: dict[str, Any]) -> list[float]:
    raw_percentiles = plan["percentiles"]
    declared = [
        Percentile(
            percentile=float(percentile) / 100,
            value=(as_timestamp(value) if plan["type"] == "date" else float(value)),
        )
        for percentile, value in raw_percentiles.items()
    ]
    scaling = question["scaling"]
    distribution = NumericDistribution(
        declared_percentiles=declared,
        open_upper_bound=scaling["open_upper_bound"],
        open_lower_bound=scaling["open_lower_bound"],
        upper_bound=scaling["range_max"],
        lower_bound=scaling["range_min"],
        zero_point=scaling["zero_point"],
        cdf_size=201,
    )
    return [point.percentile for point in distribution.get_cdf()]


def make_discrete_cdf(question: dict[str, Any], pmf: dict[int, float]) -> list[float]:
    outcome_count = question["scaling"]["inbound_outcome_count"]
    probabilities = [float(pmf.get(outcome, 0)) for outcome in range(outcome_count)]
    if not math.isclose(sum(probabilities), 1.0, abs_tol=1e-10):
        raise ValueError("Discrete PMF must sum to one")
    # Metaculus requires at least 0.000625 probability between every adjacent CDF
    # point. A 0.001 floor preserves the stated shape while satisfying that rule.
    floor = 0.001
    probabilities = [
        floor + probability * (1 - floor * outcome_count)
        for probability in probabilities
    ]
    cdf = [0.0]
    for probability in probabilities:
        cdf.append(cdf[-1] + probability)
    cdf[-1] = 1.0
    return cdf


def make_payload(question: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    question_type = plan["type"]
    if question_type == "binary":
        return {
            "probability_yes": plan["prediction"],
            "probability_yes_per_category": None,
            "continuous_cdf": None,
        }
    if question_type == "multiple_choice":
        return {
            "probability_yes": None,
            "probability_yes_per_category": plan["prediction"],
            "continuous_cdf": None,
        }
    cdf = (
        make_discrete_cdf(question, plan["pmf"])
        if question_type == "discrete"
        else make_continuous_cdf(question, plan)
    )
    return {
        "probability_yes": None,
        "probability_yes_per_category": None,
        "continuous_cdf": cdf,
    }


def post_private_note(post_id: int, reasoning: str) -> None:
    response = requests.post(
        f"{API_BASE}/comments/create/",
        headers=api_headers(),
        json={
            "text": f"{SECONDARY_LABEL}\n\n{reasoning}",
            "parent": None,
            "included_forecast": True,
            "is_private": True,
            "on_post": post_id,
        },
        timeout=30,
    )
    response.raise_for_status()
    time.sleep(1)


def post_forecast(question_id: int, payload: dict[str, Any]) -> None:
    response = requests.post(
        f"{API_BASE}/questions/forecast/",
        headers=api_headers(),
        json=[{"question": question_id, "source": "api", **payload}],
        timeout=30,
    )
    if not response.ok:
        raise RuntimeError(
            f"Forecast API rejected question {question_id}: "
            f"HTTP {response.status_code} {response.text}"
        )
    time.sleep(1)


def main() -> None:
    assert_safe_account()
    completed: list[int] = []
    newly_posted = 0
    post_cache = get_open_test_posts()
    for plan in FORECASTS:
        if plan["question_id"] in VERIFIED_QUESTION_IDS:
            print(f"Skipping checkpointed question {plan['question_id']}")
            completed.append(plan["question_id"])
            continue
        post = post_cache.get(plan["post_id"]) or get_post(plan["post_id"])
        post_cache[plan["post_id"]] = post
        assert_safe_post(post)
        question = find_question(post, plan["question_id"])
        if question["status"] != "open":
            raise RuntimeError(f"Question {question['id']} is no longer open")
        if question.get("my_forecasts", {}).get("latest") is not None:
            print(f"Skipping already forecasted question {question['id']}")
            completed.append(question["id"])
            continue
        if question["type"] != plan["type"]:
            raise RuntimeError(f"Type changed for question {question['id']}")

        payload = make_payload(question, plan)
        if not plan.get("note_already_posted"):
            post_private_note(plan["post_id"], plan["reasoning"])
        post_forecast(question["id"], payload)

        refreshed_post = get_post(plan["post_id"])
        post_cache[plan["post_id"]] = refreshed_post
        refreshed = find_question(refreshed_post, question["id"])
        latest = refreshed.get("my_forecasts", {}).get("latest")
        if latest is None or latest.get("question_id") != question["id"]:
            raise RuntimeError(f"Forecast verification failed for {question['id']}")
        completed.append(question["id"])
        newly_posted += 1
        print(f"Verified private note + forecast for question {question['id']}")
        if newly_posted >= MAX_NEW_FORECASTS_PER_RUN:
            print("Reached the conservative two-forecast API pacing limit for this pass")
            break

    print(f"Verified {len(completed)} test-area questions: {completed}")


if __name__ == "__main__":
    main()
