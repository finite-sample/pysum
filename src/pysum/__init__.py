"""pysum: summarize pandas DataFrames into markdown, HTML, or xlsx reports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pysum.summary_tool import SummaryTool

if TYPE_CHECKING:
    import pandas as pd

__all__ = ["SummaryTool", "summarizeDF"]


def summarizeDF(  # noqa: N802 - public API since 0.1.1; renaming would break callers
    dataframe: pd.DataFrame,
    round_digits: int = 2,
    var_numbers: bool = True,
    missing_col: bool = True,
    max_distinct_values: int = 10,
    max_string_width: int = 25,
    output_type: str = "html",
    output_file: str = "summary.html",
    append: bool = True,
) -> None:
    """Summarize a DataFrame and write the report out.

    Args:
        dataframe: Frame to summarize. It must carry a ``name`` attribute, which
            is used as the report and worksheet title.
        round_digits: Digits to round reported numbers to.
        var_numbers: Whether to include the column-number column.
        missing_col: Whether to include the proportion-missing column.
        max_distinct_values: Most distinct values to list for a character column
            before the rest are pooled into an "others" line.
        max_string_width: Longest value label to print before truncating.
        output_type: One of ``html``, ``markdown`` or ``xlsx``.
        output_file: Path to write. Its extension is replaced to match
            ``output_type``.
        append: Whether to append to an existing file rather than overwrite it.
            Ignored for ``xlsx``, which is always rewritten.
    """
    SummaryTool().summarizeDF(
        dataframe,
        round_digits,
        var_numbers,
        missing_col,
        max_distinct_values,
        max_string_width,
        output_type,
        output_file,
        append,
    )
