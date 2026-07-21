"""Pure prompt builders for the Calibration Bridge secondary bot.

The architecture deliberately differs from the stock template. It separates an
outside-view analyst from an inside-view adversary, then asks an ensemble of judges to
bridge the two views with explicit anchors and uncertainty. Keeping prompt construction
pure makes the compliance label and forecasting protocol easy to test offline.
"""

from __future__ import annotations

from textwrap import dedent


SECONDARY_NOTE = (
    "SECONDARY BOT — Calibration Bridge v1. "
    "Outside-view/inside-view ensemble; not this maker's prize-eligible primary bot."
)


def _question_packet(
    *,
    question_text: str,
    background: str,
    resolution_criteria: str,
    fine_print: str,
) -> str:
    return dedent(
        f"""
        Question: {question_text}

        Background:
        {background}

        Resolution criteria:
        {resolution_criteria}

        Fine print:
        {fine_print}
        """
    ).strip()


def build_research_prompts(
    *,
    question_text: str,
    background: str,
    resolution_criteria: str,
    fine_print: str,
    today: str,
) -> tuple[str, str]:
    packet = _question_packet(
        question_text=question_text,
        background=background,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
    )
    outside = dedent(
        f"""
        You are the OUTSIDE-VIEW analyst in a forecasting system. Today is {today}.
        Work independently. Do not give a final forecast.

        {packet}

        Produce a compact dossier with:
        1. A precise restatement of what resolves and by when.
        2. Two or three defensible reference classes, with plausible base-rate ranges.
        3. The default/status-quo path and how much time is left for deviation.
        4. Boundary conditions or selection effects that make each analogy imperfect.
        5. A prior range before question-specific evidence.

        Never invent a statistic, source, or current event. Label unavailable facts as
        unknown and widen the range instead. Distinguish facts supplied by the question
        from general background knowledge.
        """
    ).strip()
    inside = dedent(
        f"""
        You are the INSIDE-VIEW ADVERSARY in a forecasting system. Today is {today}.
        Work independently. Do not give a final forecast.

        {packet}

        Produce a compact dossier with:
        1. A causal decomposition into the few events required for each outcome.
        2. Evidence in the question text that should update an outside-view prior.
        3. The strongest case for the less obvious outcome.
        4. The top three cruxes and what observation would move the forecast most.
        5. Resolution, wording, and deadline traps.

        Do not treat missing live information as evidence. Never fabricate news, quotes,
        prices, polls, or expert views. State uncertainty explicitly.
        """
    ).strip()
    return outside, inside


def build_binary_prompt(
    *,
    question_text: str,
    background: str,
    resolution_criteria: str,
    fine_print: str,
    research: str,
    today: str,
    conditional_disclaimer: str = "",
) -> str:
    packet = _question_packet(
        question_text=question_text,
        background=background,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
    )
    return dedent(
        f"""
        You are one judge in the Calibration Bridge forecasting ensemble.
        Today is {today}.

        {packet}

        Independent analyst dossiers:
        {research}

        {conditional_disclaimer}

        Reconcile the dossiers rather than averaging them mechanically:
        - state an outside-view prior and range;
        - list only question-specific updates that change the odds;
        - estimate the direction and rough strength of each update;
        - steelman the opposite result and check deadline/resolution traps;
        - shrink unsupported extremes toward the prior;
        - give one central probability and a brief calibration warning.

        Begin the rationale with exactly:
        {SECONDARY_NOTE}

        End with exactly: Probability: ZZ%
        """
    ).strip()


def build_multiple_choice_prompt(
    *,
    question_text: str,
    background: str,
    resolution_criteria: str,
    fine_print: str,
    options: list[str],
    research: str,
    today: str,
    conditional_disclaimer: str = "",
) -> str:
    packet = _question_packet(
        question_text=question_text,
        background=background,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
    )
    return dedent(
        f"""
        You are one judge in the Calibration Bridge forecasting ensemble.
        Today is {today}. Options, in required output order: {options}

        {packet}

        Independent analyst dossiers:
        {research}

        {conditional_disclaimer}

        Set an outside-view prior across every option, update only on supplied evidence,
        reserve probability for surprise, and test whether any options overlap or hide a
        resolution trap. Probabilities must be non-negative and sum to 100%.

        Begin the rationale with exactly:
        {SECONDARY_NOTE}

        End with one line per option in the exact order above:
        Option name: Probability%
        """
    ).strip()


def build_numeric_prompt(
    *,
    question_text: str,
    background: str,
    resolution_criteria: str,
    fine_print: str,
    research: str,
    today: str,
    units: str,
    lower_bound_message: str,
    upper_bound_message: str,
    conditional_disclaimer: str = "",
) -> str:
    packet = _question_packet(
        question_text=question_text,
        background=background,
        resolution_criteria=resolution_criteria,
        fine_print=fine_print,
    )
    return dedent(
        f"""
        You are one judge in the Calibration Bridge forecasting ensemble.
        Today is {today}. Required units: {units or "infer from the question"}.

        {packet}

        Independent analyst dossiers:
        {research}

        Bounds supplied by the question:
        {lower_bound_message}
        {upper_bound_message}

        {conditional_disclaimer}

        Build the distribution from the outside in: choose a reference-class median,
        identify lower- and upper-tail mechanisms, apply question-specific updates, then
        check units, monotonicity, open bounds, and whether the 10–90 interval is wide
        enough for unknown unknowns. Never use scientific notation.

        Begin the rationale with exactly:
        {SECONDARY_NOTE}

        End with exactly these increasing percentiles in the requested units:
        Percentile 10: XX
        Percentile 20: XX
        Percentile 40: XX
        Percentile 60: XX
        Percentile 80: XX
        Percentile 90: XX
        """
    ).strip()
