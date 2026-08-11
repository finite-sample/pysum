# pysum — product requirements

## 1. What this is

**A diagnostic profiler for analysis-ready data.** It describes every column, and it flags the
things that quietly change results: missingness that differs by group, values that look like
sentinel codes, zeros that are really missing, shares outside `[0,1]`, distributions that break
the method you were about to use.

The distinction from everything else in this space is the second half. Existing tools *describe*.
pysum describes **and diagnoses**.

Everything it reports is a **candidate, not a verdict**. "This column is 47% missing and the rate
differs by treatment arm" is a fact that needs a person; "this is a bug" is a claim the tool is
not entitled to make. Deciding is the analyst's job, and the output is written so that it reads
that way.

### Where it sits

| tool | what it is | why pysum is not that |
|---|---|---|
| [skimpy](https://github.com/aeturrell/skimpy) | console summary, a port of R's `skimr`; pandas + polars | mature and good at descriptive summary. pysum is not competing on prettier `describe()` |
| [fg-data-profiling](https://github.com/ydataai/ydata-profiling) (was ydata-profiling) | heavyweight HTML report | slow, large, and now partly commercial. pysum is not building a dashboard |
| `pandas.describe()` | five numbers | no missingness, no types, no diagnosis |
| **pysum** | **diagnostic sweep + per-variable table** | says what will break the analysis, not just what the data looks like |

### Why this is worth building

The logic already exists and is stranded. `audit-analysis/scripts/audit_data.py` is **433 lines,
pandas-only, untested, unpackaged**, living in a skill directory. It encodes real opinions —
*"differential missingness MANUFACTURES trends and gaps; constant missingness only attenuates"* —
that nothing on PyPI ships.

And `build-data` makes **sentinel codes its very first checkpoint** (`-999`, `999`, `88`), yet
nothing implements sentinel detection at all.

Success means that script can be deleted and the skill can `pip install pysum` instead.

## 2. The checks

Every check must name the mistake it prevents. **A check that cannot is cut** — an alert nobody
can act on trains people to ignore alerts.

Checks are **hard** or **soft**. Hard means the data is definitely wrong and the process exits
non-zero so it can gate a pipeline. Soft means it needs judgement.

| # | check | catches | hard? |
|---|---|---|---|
| 1 | **Shape and keys** | a declared key that is not unique, or does not exist | **hard** |
| 2 | **Missingness, level and differential** | missingness that differs by group. Constant missingness attenuates; differential missingness *manufactures* trends. Threshold: max−min fill rate > 2pp | soft |
| 3 | **Sentinel candidates** *(new)* | a spike at `-999`, `999`, `98`, `99`, `88`, `-1`. Is it missing, not-applicable, or a real top-code? Each implies a different denominator | soft |
| 4 | **Zeros vs missing** | a column with many zeros and no missing — zeros encoding absence | soft |
| 5 | **Dtype traps** | numbers stored as text, booleans as `object`, IDs silently cast to float | soft |
| 6 | **Values outside their logical range** | a share outside `[0,1]`, a negative count, a probability above 1 | **hard** |
| 7 | **Distributions, skew and tails** | skew > 2 or max/median > 20 — the choice of method depends on this | soft |
| 8 | **Rate columns vs reconstructed denominators** | a rate whose implied denominator disagrees with the column that should be it | soft |
| 9 | **Leverage on the headline outcome** | a single row moving a coefficient; DFBETAS above ~0.5 | soft |
| 10 | **Per-variable table** | the descriptive layer: type, stats, top values with frequencies, valid and missing counts | — |

Check 3 is new. Checks 1–2 and 4–9 come from `audit_data.py` and must reproduce its findings.
Check 10 is what pysum does today, kept because it is the thing you read first.

## 3. API

The current design is the problem: `summarizeDF(df)` writes a file, returns nothing, and requires
a monkey-patched `df.name`.

```python
import pysum

report = pysum.profile(df)              # pure; returns an object, writes nothing
report.findings                          # list of Finding(check, column, severity, message)
report.variables                         # the per-variable table
print(report.summary())                  # the console slice
report.to_markdown(path) / .to_html(path)
```

Rules:

- **`profile()` has no side effects.** No files, no printing, no global state.
- **Rendering and writing are separate calls.** Producing a summary and putting it on disk are
  different decisions.
- **No required attributes on the input.** A name is an optional argument, never a monkey-patch.
- **HTML is generated in-process.** The current code shells out to `pandoc` through `os.system`,
  which fails silently when pandoc is absent and interpolates a user-supplied filename into a
  shell command.
- **Exit code is part of the contract for the CLI**: non-zero when a hard check fails.

## 4. Output

Taken from `build-data`: *"Full output goes to a file. Inline goes the slice that decides
something."*

- **Console**: one screen. The findings that change a decision, then a path to the rest. Not a
  wall of tables — a table needing more than ~15 rows means the point is a summary statistic.
- **File**: everything, in markdown or HTML.

```
literacy   183 rows at -999 (12.5%), and the rate is 13.1% / 11.3% across arms
turnout    94 rows at 999 (6.4%)
full profile: profile.md
```

## 5. Backends

pandas and polars from the start, through
[narwhals](https://github.com/narwhals-dev/narwhals) — the standard way to write
dataframe-agnostic libraries, and what skimpy uses for the same reason.

No dtype comparison against strings. The current code tests `dtype == 'object'`, which pandas 3
silently broke: string columns are now `str`, so every categorical column lost its analysis while
still producing output.

## 6. Success criteria

Checkable, not aspirational:

1. `audit_data.py` is **deleted**, and `audit-analysis` calls pysum. Until pysum reproduces its
   findings on a dataset with known problems, the rewrite has not earned its thesis.
2. **Every check has a fixture that trips it and a fixture that does not.** A diagnostic that never
   fires and one that always fires are equally useless.
3. Sentinel detection validated against real data carrying real codes — the Assam electoral-roll
   work and `notnews` data are to hand.
4. Runs on pandas and polars, verified by the same test suite over both.
5. `preen check --strict` clean; py-canon adopted.

## 7. Out of scope

- Modelling, imputation, or fixing anything. It reports; the analyst decides.
- Plots and HTML dashboards — that is fg-data-profiling's product.
- Competing with skimpy on console aesthetics.
- Backward compatibility. The old entry point requires a monkey-patched attribute, is broken on
  current pandas, and has ~31 downloads a month. It goes.
