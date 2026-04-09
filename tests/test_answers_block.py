"""Unit tests for answer-key extraction and year segmentation."""

from __future__ import annotations

import unittest

from app.extraction.resolvers.answers.answers_block import (
    _answer_marker_positions,
    _collapse_split_answer_lines,
    _scan_answer_block_end,
    _year_segments_from_q_chunk,
    extract_answer_key,
    normalise_year_banners,
)


class TestAnswerMarkers(unittest.TestCase):
    def test_instruction_line_not_marker(self) -> None:
        text = (
            "Intro\nUse the diagram below to answer question 44 and 45.\n"
            "44. What is x?\nANSWER KEYS:\n1. A\n"
        )
        pos = _answer_marker_positions(text)
        self.assertEqual(len(pos), 1)

    def test_cover_answers_not_split(self) -> None:
        text = "JAMB\nQuestions And\nAnswers\n\n__YR__2010\n\n1. Stem?\nA. x\n"
        t = normalise_year_banners(text)
        pos = _answer_marker_positions(t)
        self.assertEqual(len(pos), 0)


class TestExtractAnswerKey(unittest.TestCase):
    def test_split_number_letter_lines(self) -> None:
        block = "ANSWER KEYS:\n1.\nC\n2.\nA\n"
        self.assertEqual(extract_answer_key(block), {1: "C", 2: "A"})

    def test_space_instead_of_dot(self) -> None:
        block = "12 C\n13. D\n"
        d = extract_answer_key(block)
        self.assertEqual(d.get(12), "C")
        self.assertEqual(d.get(13), "D")


class TestScanAnswerBlockEnd(unittest.TestCase):
    def test_stops_before_next_year_banner(self) -> None:
        text = (
            "ANSWER KEYS:\n26. A\n1.\nC\n50. C\n\n7\n\n"
            "__YR__2011\n\n1. Next year?\n"
        )
        start = text.index("ANSWER KEYS:")
        end = _scan_answer_block_end(text, start)
        self.assertTrue(end <= text.index("__YR__2011"))


class TestYearSegments(unittest.TestCase):
    def test_multi_year_q_chunk(self) -> None:
        q = "\n__YR__2015\n\n1. P\n\n__YR__2016\n\n1. Q\n\n__YR__2017\n\n1. R\n"
        segs = _year_segments_from_q_chunk(q)
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[0][0], "2015")
        self.assertIn("1. P", segs[0][1])
        self.assertEqual(segs[2][0], "2017")


class TestCollapse(unittest.TestCase):
    def test_collapse(self) -> None:
        s = "1.\nC\n2.\nD"
        self.assertEqual(_collapse_split_answer_lines(s), "1. C\n2. D")


if __name__ == "__main__":
    unittest.main()
