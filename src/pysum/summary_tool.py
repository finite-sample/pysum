"""Build per-column summaries of a pandas DataFrame and render them to a file."""

from __future__ import annotations

import shutil
import subprocess
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
import pytablewriter
from tabulate import tabulate

if TYPE_CHECKING:
    from collections.abc import Sequence

# The three column kinds the report knows how to describe. Everything else
# (datetimes, booleans, categoricals) falls through with an empty stats cell,
# which is the documented limitation.
_FLOAT = "float"
_INTEGER = "integer"
_CHARACTER = "character"


def _as_int(value: Any) -> int:
    """Narrow a pandas aggregate to a Python int.

    ``Series.min()`` and friends are typed as possibly returning a Series, which
    they do not for the single-column aggregates used here. This keeps the cast
    in one place instead of scattering per-call type ignores.

    Args:
        value: A pandas scalar aggregate.

    Returns:
        The value truncated to an int.
    """
    return int(value)


def _column_kind(dtype: Any) -> str | None:
    """Classify a dtype into one of the report's three column kinds.

    The original code compared ``dtype`` against the literal strings
    ``'float64'``, ``'int64'`` and ``'object'``. pandas 3 gives string columns a
    ``StringDtype`` rather than ``object``, so the character branch stopped
    firing and text columns rendered with an empty stats cell. Asking the dtype
    what it is, rather than what it prints as, also picks up float32/int32.

    Args:
        dtype: A pandas dtype, as found in ``DataFrame.dtypes``.

    Returns:
        One of the module's kind constants, or None for a dtype the report has
        nothing to say about.
    """
    if pd.api.types.is_float_dtype(dtype):
        return _FLOAT
    if pd.api.types.is_integer_dtype(dtype) and not pd.api.types.is_bool_dtype(dtype):
        return _INTEGER
    if isinstance(dtype, pd.StringDtype) or pd.api.types.is_object_dtype(dtype):
        return _CHARACTER
    return None


class SummaryTool:
    """Summarize a DataFrame column by column and write the result out."""

    def __init__(self) -> None:
        """Set up an unconfigured tool; :meth:`summarizeDF` supplies the rest."""
        self.summary_cols: list[str] = [
            "No",
            "Variable",
            "Stats / Values",
            "Freqs (% of Valid)",
            "Valid",
            "Missing",
        ]
        self.df: pd.DataFrame = pd.DataFrame()
        self.round_digits: int = 2
        self.var_numbers: bool = True
        self.missing_col: bool = True
        self.max_distinct_values: int = 10
        self.max_string_width: int = 25
        self.output_type: str = "html"
        self.output_file: Path = Path("summary.html")
        self.append: bool = True
        self.row_count: int = 0
        self.df_summary: list[list[Any]] = []
        self._kinds: dict[str, str | None] = {}

    def _summary_for_column(self, no: int, col_name: str) -> list[Any]:
        """Build one row of the summary table.

        Args:
            no: 1-based position of the column in the frame.
            col_name: Name of the column to summarize.

        Returns:
            The cells of the row, in ``summary_cols`` order.
        """
        col_set = self.df[col_name]
        kind = self._kinds[col_name]
        col_summary: list[Any] = []

        if self.var_numbers is True:
            col_summary.append(no)

        variable = col_name
        if kind is not None:
            variable += "\n" + f"[{kind}]"
        col_summary.append(variable)

        col_summary.append(self._stats_and_values(col_name))

        if kind == _CHARACTER:
            col_summary.append(self._freqs_for_character(col_name))
        else:
            col_summary.append(f"{len(col_set.value_counts())} distinct val.")

        missing_count = _as_int(col_set.isna().sum())
        valid_count = self.row_count - missing_count
        col_summary.append(self._count_with_share(valid_count))

        if self.missing_col is True:
            col_summary.append(self._count_with_share(missing_count))

        return col_summary

    def _count_with_share(self, count: int) -> str:
        """Render a count above its share of the row count.

        Args:
            count: Number of rows the cell is reporting on.

        Returns:
            The count and its percentage, separated by a newline.
        """
        if count == 0:
            return "0\n(0%)"
        share = 100 * (count / self.row_count)
        return f"{count}\n({share:.{self.round_digits}f}%)"

    def _iqr(self, col_name: str) -> Any:
        """Return the interquartile range of a numeric column.

        Args:
            col_name: Name of the column.

        Returns:
            The third quartile minus the first.
        """
        col_set = self.df[col_name]
        return col_set.quantile(0.75) - col_set.quantile(0.25)

    def _sorted_counts(self, col_name: str) -> list[tuple[Any, Any]]:
        """Return ``(value, count)`` pairs for a character column.

        Pairs are sorted by descending count when the column has more distinct
        values than the report will show, and alphabetically otherwise.

        Args:
            col_name: Name of the column.

        Returns:
            The value/count pairs in display order.
        """
        counts = list(self.df.groupby(col_name)[col_name].count().items())
        if len(counts) > self.max_distinct_values:
            counts.sort(key=itemgetter(1), reverse=True)
        else:
            counts.sort(key=itemgetter(0))
        return counts

    def _stats_and_values(self, col_name: str) -> str:
        """Render the "Stats / Values" cell for a column.

        Args:
            col_name: Name of the column.

        Returns:
            The cell contents; empty for a dtype the report does not describe.
        """
        col_set = self.df[col_name]
        kind = self._kinds[col_name]
        digits = self.round_digits
        ret_val = ""

        if kind == _FLOAT:
            mean, sd = col_set.mean(), col_set.std()
            ret_val += "\n" + f"mean (sd) : {mean:.{digits}f} ({sd:.{digits}f})"
            ret_val += "\n" + "min < med < max :"
            ret_val += "\n" + (
                f"{col_set.min():.{digits}f} < {col_set.median():.{digits}f}"
                f" < {col_set.max():.{digits}f}"
            )
            iqr = self._iqr(col_name)
            ret_val += "\n" + f"IQR (CV) : {iqr:.{digits}f} ({sd / mean:.{digits}f})"
        elif kind == _INTEGER:
            mean, sd = col_set.mean(), col_set.std()
            ret_val += "\n" + f"mean (sd) : {mean:.{digits}f} ({sd:.{digits}f})"
            ret_val += "\n" + "min < med < max :"
            ret_val += "\n" + (
                f"{_as_int(col_set.min())} < {_as_int(col_set.median())}"
                f" < {_as_int(col_set.max())}"
            )
            iqr = self._iqr(col_name)
            ret_val += "\n" + f"IQR (CV) : {_as_int(iqr)} ({sd / mean:.{digits}f})"
        elif kind == _CHARACTER:
            counts = self._sorted_counts(col_name)
            for idx, (group_name, _count) in enumerate(counts, start=1):
                label = str(group_name)
                if len(label) > self.max_string_width:
                    label = label[: self.max_string_width] + "..."
                ret_val += "\n" + f"{idx}. {label}"
                if idx == self.max_distinct_values:
                    others = len(counts) - self.max_distinct_values
                    ret_val += "\n" + f"[ {others} others ]"
                    break

        return ret_val

    def _freqs_for_character(self, col_name: str) -> str:
        """Render the "Freqs (% of Valid)" cell for a character column.

        Args:
            col_name: Name of the column.

        Returns:
            One count-and-share line per displayed value, plus a pooled line for
            everything past ``max_distinct_values``.
        """
        digits = self.round_digits
        ret_val = ""
        other_count = 0

        for idx, (_group_name, count) in enumerate(
            self._sorted_counts(col_name), start=1
        ):
            if idx <= self.max_distinct_values:
                share = 100 * (count / self.row_count)
                ret_val += "\n" + f"{count} ( {share:.{digits}f}%)"
            else:
                other_count += count

        if other_count > 0:
            share = 100 * (other_count / self.row_count)
            ret_val += "\n" + f"{other_count} ( {share:.{digits}f}%)"

        return ret_val

    def _write_excel_file(self) -> None:
        """Write the summary to an xlsx workbook."""
        writer = pytablewriter.ExcelXlsxTableWriter()
        writer.open(str(self.output_file))
        writer.make_worksheet(self.df.name)
        writer.headers = self.summary_cols
        writer.value_matrix = self.df_summary
        writer.write_table()
        writer.close()

    def _output_markdown(self) -> None:
        """Print the summary to stdout as a markdown table."""
        writer = pytablewriter.MarkdownTableWriter()
        writer.table_name = self.df.name
        writer.headers = self.summary_cols
        writer.value_matrix = self.df_summary
        writer.write_table()

    def _report_lines(self, centered: bool) -> Sequence[str]:
        """Build the header lines that precede the table in a written report.

        Args:
            centered: Whether to wrap each line in an HTML ``<center>`` tag.

        Returns:
            The header lines, without trailing newlines.
        """
        lines = ["Data Frame Summary", str(self.df.name), f"N: {self.row_count}"]
        if centered:
            return [f"<center>{line}</center>" for line in lines]
        return lines

    def _write_report(self, path: Path, centered: bool) -> None:
        """Write the header lines and the tabulated table to ``path``.

        Args:
            path: File to write.
            centered: Whether to wrap the header lines in ``<center>`` tags.
        """
        mode = "a" if self.append is True else "w"
        table = tabulate(self.df_summary, tablefmt="simple", headers=self.summary_cols)
        with path.open(mode, encoding="utf-8") as handle:
            for line in self._report_lines(centered):
                handle.write("\n")
                handle.write(line)
            handle.write("\n")
            handle.write(table)
            handle.write("\n")

    def _write_html_file(self) -> None:
        """Write a markdown report and convert it to HTML with pandoc.

        Raises:
            RuntimeError: If pandoc is not installed.
        """
        temp_file = self.output_file.with_suffix(".md")
        self._write_report(temp_file, centered=True)

        pandoc = shutil.which("pandoc")
        if pandoc is None:
            msg = (
                "html output needs pandoc on PATH; "
                "install it or use output_type='markdown'"
            )
            raise RuntimeError(msg)
        # The argument list is fixed and passed without a shell; only the two
        # file paths vary, and they cannot be read as options.
        subprocess.run(  # noqa: S603
            [
                pandoc,
                "-s",
                "-c",
                "custom.css",
                "-o",
                str(self.output_file),
                str(temp_file),
            ],
            check=True,
        )

    def summarizeDF(  # noqa: N802 - public API since 0.1.1; renaming would break callers
        self,
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
            dataframe: Frame to summarize. It must carry a ``name`` attribute,
                which is used as the report and worksheet title.
            round_digits: Digits to round reported numbers to.
            var_numbers: Whether to include the column-number column.
            missing_col: Whether to include the proportion-missing column.
            max_distinct_values: Most distinct values to list for a character
                column before the rest are pooled into an "others" line.
            max_string_width: Longest value label to print before truncating.
            output_type: One of ``html``, ``markdown`` or ``xlsx``.
            output_file: Path to write. Its extension is replaced to match
                ``output_type``.
            append: Whether to append to an existing file rather than overwrite
                it. Ignored for ``xlsx``, which is always rewritten.
        """
        self.df = dataframe
        self.round_digits = round_digits
        self.var_numbers = var_numbers
        self.missing_col = missing_col
        self.max_distinct_values = max_distinct_values
        self.max_string_width = max_string_width
        self.output_type = output_type
        suffix = {"html": ".html", "markdown": ".md", "xlsx": ".xlsx"}.get(output_type)
        self.output_file = Path(output_file)
        if suffix is not None:
            self.output_file = self.output_file.with_suffix(suffix)
        self.append = append

        self.summary_cols = []
        if self.var_numbers is True:
            self.summary_cols.append("No")
        self.summary_cols.append("Variable")
        self.summary_cols.append("Stats / Values")
        self.summary_cols.append("Freqs (% of Valid)")
        self.summary_cols.append("Valid")
        if self.missing_col is True:
            self.summary_cols.append("Missing")

        self.row_count = len(self.df)
        cols = list(self.df.columns.values)
        self._kinds = {col: _column_kind(self.df.dtypes[col]) for col in cols}

        self.df_summary = [
            self._summary_for_column(idx, col) for idx, col in enumerate(cols, start=1)
        ]

        if self.output_type == "xlsx":
            self._write_excel_file()
        elif self.output_type == "markdown":
            self._output_markdown()
            self._write_report(self.output_file, centered=False)
        elif self.output_type == "html":
            self._output_markdown()
            self._write_html_file()
