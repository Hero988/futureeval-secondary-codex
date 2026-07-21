"""Hands-off Metaculus secondary bot using a two-lens calibrated ensemble."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import datetime, timezone

import dotenv
import requests

from bot_helpers import (
    check_environment,
    print_run_summary_banner,
    print_startup_banner,
    silence_noisy_dependencies,
)
from calibration_bridge import (
    SECONDARY_NOTE,
    build_binary_prompt,
    build_multiple_choice_prompt,
    build_numeric_prompt,
    build_research_prompts,
)

silence_noisy_dependencies()

from forecasting_tools import (  # noqa: E402
    BinaryQuestion,
    MetaculusClient,
    MetaculusQuestion,
    MultipleChoiceQuestion,
    NumericQuestion,
    ReasonedPrediction,
)

from template_bot import SummerTemplateBot2026  # noqa: E402

dotenv.load_dotenv()
logger = logging.getLogger(__name__)


def assert_secondary_account() -> dict:
    """Fail closed unless this token belongs to an explicitly secondary bot."""
    token = os.environ["METACULUS_TOKEN"]
    response = requests.get(
        "https://www.metaculus.com/api/users/me/",
        headers={
            "Authorization": f"Token {token}",
            "User-Agent": "Calibration-Bridge-secondary/1.0",
        },
        timeout=30,
    )
    response.raise_for_status()
    account = response.json()
    if account.get("is_bot") is not True or account.get("is_primary_bot") is not False:
        raise RuntimeError(
            "Refusing to forecast: token is not explicitly classified as a secondary bot"
        )
    logger.info(
        "Secondary-account gate passed for user_id=%s username=%s",
        account.get("id"),
        account.get("username"),
    )
    return account


class CalibrationBridgeBot(SummerTemplateBot2026):
    """Two independent evidence lenses followed by a repeated calibrated judge."""

    async def run_research(self, question: MetaculusQuestion) -> str:
        async with self._concurrency_limiter:
            today = datetime.now(timezone.utc).date().isoformat()
            outside_prompt, inside_prompt = build_research_prompts(
                question_text=question.question_text,
                background=question.background_info,
                resolution_criteria=question.resolution_criteria,
                fine_print=question.fine_print,
                today=today,
            )
            analyst = self.get_llm("default", "llm")
            outside = await analyst.invoke(outside_prompt)
            inside = await analyst.invoke(inside_prompt)
            dossier = (
                "## Outside-view analyst\n"
                f"{outside}\n\n"
                "## Inside-view adversary\n"
                f"{inside}"
            )
            logger.info("Built two-lens dossier for %s", question.page_url)
            return dossier

    @staticmethod
    def _tag(prediction: ReasonedPrediction) -> ReasonedPrediction:
        if not prediction.reasoning.startswith(SECONDARY_NOTE):
            prediction.reasoning = f"{SECONDARY_NOTE}\n\n{prediction.reasoning}"
        return prediction

    async def _run_forecast_on_binary(
        self, question: BinaryQuestion, research: str
    ) -> ReasonedPrediction[float]:
        prompt = build_binary_prompt(
            question_text=question.question_text,
            background=question.background_info,
            resolution_criteria=question.resolution_criteria,
            fine_print=question.fine_print,
            research=research,
            today=datetime.now(timezone.utc).date().isoformat(),
            conditional_disclaimer=self._get_conditional_disclaimer_if_necessary(
                question
            ),
        )
        return self._tag(await self._binary_prompt_to_forecast(question, prompt))

    async def _run_forecast_on_multiple_choice(
        self, question: MultipleChoiceQuestion, research: str
    ) -> ReasonedPrediction:
        prompt = build_multiple_choice_prompt(
            question_text=question.question_text,
            background=question.background_info,
            resolution_criteria=question.resolution_criteria,
            fine_print=question.fine_print,
            options=question.options,
            research=research,
            today=datetime.now(timezone.utc).date().isoformat(),
            conditional_disclaimer=self._get_conditional_disclaimer_if_necessary(
                question
            ),
        )
        return self._tag(await self._multiple_choice_prompt_to_forecast(question, prompt))

    async def _run_forecast_on_numeric(
        self, question: NumericQuestion, research: str
    ) -> ReasonedPrediction:
        upper_message, lower_message = self._create_upper_and_lower_bound_messages(
            question
        )
        prompt = build_numeric_prompt(
            question_text=question.question_text,
            background=question.background_info,
            resolution_criteria=question.resolution_criteria,
            fine_print=question.fine_print,
            research=research,
            today=datetime.now(timezone.utc).date().isoformat(),
            units=question.unit_of_measure or "",
            lower_bound_message=lower_message,
            upper_bound_message=upper_message,
            conditional_disclaimer=self._get_conditional_disclaimer_if_necessary(
                question
            ),
        )
        return self._tag(await self._numeric_prompt_to_forecast(question, prompt))

    async def _run_forecast_on_date(self, question, research):
        return self._tag(await super()._run_forecast_on_date(question, research))

    async def _run_forecast_on_conditional(self, question, research):
        return self._tag(await super()._run_forecast_on_conditional(question, research))


def run(mode: str, confirm_live: bool) -> None:
    check_environment(strict=True)
    account = assert_secondary_account()
    if mode == "tournament" and not confirm_live:
        raise RuntimeError("Live tournament mode requires --confirm-live")

    print_startup_banner(mode, will_publish=True)
    print(
        f"Secondary account confirmed: {account['username']} "
        f"(is_primary_bot={account['is_primary_bot']})"
    )
    bot = CalibrationBridgeBot(
        research_reports_per_question=1,
        predictions_per_research_report=3,
        use_research_summary_to_forecast=False,
        publish_reports_to_metaculus=True,
        folder_to_save_reports_to=None,
        skip_previously_forecasted_questions=mode == "tournament",
        extra_metadata_in_explanation=True,
    )
    client = MetaculusClient()
    if mode == "test_questions":
        reports = asyncio.run(
            bot.forecast_on_tournament("bot-testing-area", return_exceptions=True)
        )
        tournament_url = "https://www.metaculus.com/tournament/bot-testing-area/"
    else:
        seasonal = asyncio.run(
            bot.forecast_on_tournament(
                client.CURRENT_AI_COMPETITION_ID, return_exceptions=True
            )
        )
        minibench = asyncio.run(
            bot.forecast_on_tournament(
                client.CURRENT_MINIBENCH_ID, return_exceptions=True
            )
        )
        reports = seasonal + minibench
        tournament_url = (
            "https://www.metaculus.com/tournament/summer-futureeval-2026/"
        )

    bot.log_report_summary(reports)
    print_run_summary_banner(
        reports,
        will_publish=True,
        tournament_url=tournament_url,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    parser = argparse.ArgumentParser(description="Run Calibration Bridge secondary bot")
    parser.add_argument(
        "--mode",
        choices=["test_questions", "tournament"],
        default="test_questions",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required guard for live Summer FutureEval and MiniBench forecasts",
    )
    arguments = parser.parse_args()
    run(arguments.mode, arguments.confirm_live)
