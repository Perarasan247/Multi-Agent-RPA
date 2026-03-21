"""Tests for Agent 4: Download — filename building."""

import re
import unittest
from unittest.mock import patch, MagicMock


class TestFilenameBuild(unittest.TestCase):
    """Test the build_filename node output format."""

    def _run_build(self, dealer="D10836", branch="BR001",
                   report_key="spareparts_sales_statement",
                   from_date="01/03/2026", to_date="31/03/2026"):
        """Helper to run build_filename_node with mocked settings."""
        with patch("agents.agent4_download.nodes.build_filename.settings") as mock_s:
            mock_s.dealer_code = dealer
            mock_s.branch_code = branch
            mock_s.report_key = report_key
            mock_s.filter_from_date = from_date
            mock_s.filter_to_date = to_date

            from agents.agent4_download.nodes.build_filename import build_filename_node

            state = {
                "error": None,
                "report_key": report_key,
                "from_date": from_date,
                "to_date": to_date,
            }
            return build_filename_node(state)

    def test_filename_format_correct(self):
        """Filename should include dealer, branch, report key, and .xlsx."""
        result = self._run_build()
        fn = result.get("filename_built", "")
        self.assertTrue(fn.endswith(".xlsx"), f"Expected .xlsx extension: {fn}")
        self.assertIn("D10836", fn)
        self.assertIn("BR001", fn)
        self.assertIn("spareparts_sales_statement", fn)
        self.assertIsNone(result.get("error"))

    def test_filename_no_spaces(self):
        """Filename must never contain spaces."""
        result = self._run_build()
        fn = result.get("filename_built", "")
        self.assertNotIn(" ", fn, f"Filename contains spaces: {fn}")

    def test_filename_date_format(self):
        """Slashes in dates must be converted — no / in filename."""
        result = self._run_build()
        fn = result.get("filename_built", "")
        self.assertNotIn("/", fn, f"Filename contains slashes: {fn}")

    def test_filename_only_safe_chars(self):
        """Filename should only contain alphanumeric, underscore, hyphen, and dot."""
        result = self._run_build()
        fn = result.get("filename_built", "")
        # Remove .xlsx extension for the check
        name_part = fn.replace(".xlsx", "")
        self.assertTrue(
            re.match(r"^[a-zA-Z0-9_\-]+$", name_part),
            f"Filename contains unsafe characters: {fn}",
        )

    def test_filename_with_different_dealer(self):
        """Different dealer code should be reflected in filename."""
        result = self._run_build(dealer="D99999")
        fn = result.get("filename_built", "")
        self.assertIn("D99999", fn)
        self.assertNotIn("D10836", fn)

    def test_filename_includes_date_range(self):
        """Filename should include from and to date info."""
        result = self._run_build(from_date="15/01/2026", to_date="28/02/2026")
        fn = result.get("filename_built", "")
        # Dates are converted: 15/01/2026 → 15-01-2026
        self.assertIn("15-01-2026", fn)
        self.assertIn("28-02-2026", fn)

    def test_build_does_not_set_error(self):
        """Normal build should never set error."""
        result = self._run_build()
        self.assertIsNone(result.get("error"))


if __name__ == "__main__":
    unittest.main()
