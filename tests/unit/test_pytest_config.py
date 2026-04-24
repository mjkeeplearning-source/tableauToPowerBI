"""Verify pytest markers are registered correctly."""
import subprocess
import sys


def test_feature_flag_markers_registered():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--markers"],
        capture_output=True, text=True, check=True,
    )
    for marker in (
        "feature_flag",
        "feature_flag_v1_1",
        "feature_flag_v1_2",
        "integration",
        "ai_snapshot",
        "validity_tmdl",
        "validity_pbir",
        "validity_dax_semantic",
        "desktop_open",
    ):
        assert f"@pytest.mark.{marker}" in result.stdout, f"missing marker: {marker}"
