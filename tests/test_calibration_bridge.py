import unittest

from calibration_bridge import (
    SECONDARY_NOTE,
    build_binary_prompt,
    build_numeric_prompt,
    build_research_prompts,
)


class CalibrationBridgePromptTests(unittest.TestCase):
    def setUp(self):
        self.common = {
            "question_text": "Will the event happen by 2030?",
            "background": "A bounded example.",
            "resolution_criteria": "Resolves yes only after an official announcement.",
            "fine_print": "No rumours.",
            "today": "2026-07-21",
        }

    def test_research_uses_two_distinct_lenses(self):
        outside, inside = build_research_prompts(**self.common)
        self.assertIn("OUTSIDE-VIEW", outside)
        self.assertIn("reference classes", outside)
        self.assertIn("INSIDE-VIEW ADVERSARY", inside)
        self.assertIn("causal decomposition", inside)
        self.assertNotEqual(outside, inside)

    def test_binary_prompt_requires_secondary_disclosure_and_probability(self):
        prompt = build_binary_prompt(**self.common, research="two-lens dossier")
        self.assertIn(SECONDARY_NOTE, prompt)
        self.assertIn("Probability: ZZ%", prompt)
        self.assertIn("outside-view prior", prompt)

    def test_numeric_prompt_requires_monotone_percentiles_and_units(self):
        prompt = build_numeric_prompt(
            **self.common,
            research="two-lens dossier",
            units="gigawatts",
            lower_bound_message="At least zero.",
            upper_bound_message="Likely below 100.",
        )
        self.assertIn("Required units: gigawatts", prompt)
        self.assertLess(prompt.index("Percentile 10"), prompt.index("Percentile 90"))
        self.assertIn(SECONDARY_NOTE, prompt)


if __name__ == "__main__":
    unittest.main()
