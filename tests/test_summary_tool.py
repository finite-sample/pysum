from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pandas as pd
import pytest

import pysum
from pysum.summary_tool import SummaryTool, _column_kind

if TYPE_CHECKING:
    from pathlib import Path


def make_frame(name: str = "fixture") -> pd.DataFrame:
    """A frame with one column of each kind the report handles, plus a gappy one."""
    df = pd.DataFrame(
        {
            "flt": [1.0, 2.0, 3.0, 4.0],
            "int": [1, 2, 3, 10],
            "chr": ["b", "a", "a", "b"],
            "withna": [1.0, None, 3.0, None],
        }
    )
    df.name = name
    return df


def summarize_to_markdown(tmp_path: Path, df: pd.DataFrame, **kwargs) -> str:
    out = tmp_path / "summary.md"
    pysum.summarizeDF(
        df, output_type="markdown", output_file=str(out), append=False, **kwargs
    )
    return out.read_text()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1.0, 2.0], "float"),
        ([1, 2], "integer"),
        (["a", "b"], "character"),
        ([True, False], None),
        (pd.to_datetime(["2020-01-01", "2020-01-02"]), None),
    ],
)
def test_column_kind(values, expected):
    assert _column_kind(pd.Series(values).dtype) == expected


def test_object_dtype_is_character():
    # A column of mixed objects still falls in the character branch.
    assert _column_kind(pd.Series([{"a": 1}, "b"], dtype=object).dtype) == "character"


def test_markdown_report_header(tmp_path):
    text = summarize_to_markdown(tmp_path, make_frame("iris"))
    assert "Data Frame Summary" in text
    assert "iris" in text
    assert "N: 4" in text


def test_numeric_columns_report_stats(tmp_path):
    text = summarize_to_markdown(tmp_path, make_frame())
    assert "mean (sd) : 2.50 (1.29)" in text  # flt
    assert "1.00 < 2.50 < 4.00" in text
    assert "IQR (CV) : 1.50 (0.52)" in text
    assert "mean (sd) : 4.00 (4.08)" in text  # int
    assert "1 < 2 < 10" in text


def test_character_column_lists_values_and_freqs(tmp_path):
    text = summarize_to_markdown(tmp_path, make_frame())
    assert "[character]" in text
    assert "1. a" in text
    assert "2. b" in text
    assert "2 ( 50.00%)" in text


def test_missing_counts(tmp_path):
    text = summarize_to_markdown(tmp_path, make_frame())
    assert "(50.00%)" in text  # withna: 2 of 4 valid, 2 missing


def test_round_digits_is_honoured(tmp_path):
    text = summarize_to_markdown(tmp_path, make_frame(), round_digits=4)
    assert "mean (sd) : 2.5000 (1.2910)" in text


def test_many_distinct_values_are_pooled(tmp_path):
    df = pd.DataFrame({"chr": [f"v{i}" for i in range(12)]})
    df.name = "wide"
    text = summarize_to_markdown(tmp_path, df, max_distinct_values=3)
    assert "[ 9 others ]" in text
    assert "9 ( 75.00%)" in text
    assert "4. v3" not in text


def test_long_labels_are_truncated(tmp_path):
    df = pd.DataFrame({"chr": ["x" * 40]})
    df.name = "long"
    text = summarize_to_markdown(tmp_path, df, max_string_width=5)
    assert "1. xxxxx..." in text


def test_optional_columns_can_be_dropped(tmp_path):
    text = summarize_to_markdown(
        tmp_path, make_frame(), var_numbers=False, missing_col=False
    )
    assert "No " not in text.splitlines()[4]
    assert "Missing" not in text


def test_append_adds_a_second_report(tmp_path):
    df = make_frame()
    out = tmp_path / "summary.md"
    pysum.summarizeDF(df, output_type="markdown", output_file=str(out), append=False)
    once = out.read_text()
    pysum.summarizeDF(df, output_type="markdown", output_file=str(out), append=True)
    twice = out.read_text()
    assert twice.count("Data Frame Summary") == 2
    assert twice.startswith(once)


def test_output_extension_matches_output_type(tmp_path):
    df = make_frame()
    pysum.summarizeDF(
        df,
        output_type="markdown",
        output_file=str(tmp_path / "report.html"),
        append=False,
    )
    assert (tmp_path / "report.md").exists()
    assert not (tmp_path / "report.html").exists()


def test_xlsx_output(tmp_path):
    out = tmp_path / "summary.xlsx"
    pysum.summarizeDF(make_frame(), output_type="xlsx", output_file=str(out))
    assert out.exists()
    assert out.stat().st_size > 0


def test_html_output_invokes_pandoc(tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        "pysum.summary_tool.shutil.which", lambda _name: "/usr/bin/pandoc"
    )
    monkeypatch.setattr("pysum.summary_tool.subprocess.run", fake_run)

    out = tmp_path / "summary.html"
    pysum.summarizeDF(make_frame(), output_type="html", output_file=str(out))

    assert (tmp_path / "summary.md").exists()
    assert len(calls) == 1
    assert calls[0][0] == "/usr/bin/pandoc"
    assert str(out) in calls[0]


def test_html_output_without_pandoc_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("pysum.summary_tool.shutil.which", lambda _name: None)
    with pytest.raises(RuntimeError, match="pandoc"):
        pysum.summarizeDF(
            make_frame(), output_type="html", output_file=str(tmp_path / "s.html")
        )


def test_class_entrypoint_matches_module_function(tmp_path):
    df = make_frame()
    via_module = tmp_path / "a.md"
    via_class = tmp_path / "b.md"
    pysum.summarizeDF(
        df, output_type="markdown", output_file=str(via_module), append=False
    )
    SummaryTool().summarizeDF(
        df, output_type="markdown", output_file=str(via_class), append=False
    )
    assert via_module.read_text() == via_class.read_text()
