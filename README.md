# pysum: summarize pandas dataframes

[![CI](https://github.com/finite-sample/pysum/actions/workflows/ci.yml/badge.svg)](https://github.com/finite-sample/pysum/actions/workflows/ci.yml)
[![Docs](https://github.com/finite-sample/pysum/actions/workflows/docs.yml/badge.svg)](https://finite-sample.github.io/pysum/)
[![PyPI version](https://img.shields.io/pypi/v/pysum.svg)](https://pypi.org/project/pysum/)
[![Downloads](https://static.pepy.tech/badge/pysum)](https://pepy.tech/project/pysum)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

`pysum` takes a pandas dataframe (and a few other arguments to customize the
output) and creates a markdown, html, or xlsx report with a summary of each of
the variables in the dataframe.

The program iterates through each of the columns in the dataframe and, based on
the datatype, creates summary statistics for each, and prints them out to a
table.

## Install

```bash
pip install pysum
```

The `html` output shells out to [pandoc](https://pandoc.org/), so that one
output format additionally needs `pandoc` on your `PATH`. It also depends on
[`custom.css`](https://github.com/finite-sample/pysum/blob/master/custom.css) in
the working directory.

## Inputs

The function takes the following arguments:

1. `dataframe`: pandas dataframe. No default. The passed dataframe must also
   have an attribute `name` that carries the `name` of the dataframe. See
   examples for clarification.
2. `round_digits`: Integer. Digits to which the numbers reported should be
   rounded. The default is 2.
3. `var_numbers`: Boolean. Whether or not to add a column indicating the column
   number. The default is `True`.
4. `missing_col`: Boolean. Adds a column that reports the proportion missing.
   The default is `True`.
5. `max_distinct_values`: Numeric. The maximum number of values to display
   frequencies for. If a variable has more distinct values than this number, the
   remaining frequencies will be reported as a whole, along with the number of
   additional distinct values. Defaults to 10.
6. `max_string_width`: Integer. Limits the number of characters to display in
   the frequency tables. The default is 25.
7. `output_type`: String. The file format of the output file: `xlsx`, `html`, or
   `markdown`. The default is `html`.
8. `output_file`: String. The path and filename to which the script should
   output the results. The default is `summary.html` in the local directory.
9. `append`: Boolean. If there is an existing file, should we append the results,
   or should we overwrite the file? The default is `True`. When append is `True`,
   the results are appended. When it is `False`, the file is overwritten.

## Output

The output is an xlsx, html, or markdown file. For numeric columns, it reports
mean, standard deviation, minimum, maximum, median, IQR, number of distinct
values, percentage that are valid, and percentage missing, by default.

**Definitions of things in the output**

1. Valid = entries with non-missing values
2. mean (sd) = mean (standard deviation)
3. min = minimum
4. med = median
5. max = maximum
6. IQR = interquartile range
7. CV = coefficient of variation

For character vectors, it reports as many as `max_distinct_values`, reports the
number of other values, and their percentage. It also reports the percentage of
observations that are valid and that are missing by default.

Limitations: dates by default are parsed as characters. Dates are best handled
as numeric. But given the variety of formats in which dates appear, no standard
support is offered for now.

## Examples

[Iris data](https://archive.ics.uci.edu/ml/datasets/iris):

```python
import pandas

import pysum

url = "https://archive.ics.uci.edu/ml/machine-learning-databases/iris/iris.data"
names = ["sepal-length", "sepal-width", "petal-length", "petal-width", "class"]
dataset = pandas.read_csv(url, names=names)

# Pass the name of the dataset; it is required
dataset.name = "iris"

pysum.summarizeDF(dataset)
pysum.summarizeDF(dataset, output_type="xlsx", append=False)
pysum.summarizeDF(dataset, output_type="markdown", append=False)
```

[Markdown output](https://github.com/finite-sample/pysum/blob/master/examples/summary.md),
[HTML output](https://github.com/finite-sample/pysum/blob/master/examples/summary.html),
and
[XLSX output](https://github.com/finite-sample/pysum/blob/master/examples/summary.xlsx)

## Attribution

The package is based on <https://github.com/dcomtois/summarytools>

## License

MIT
