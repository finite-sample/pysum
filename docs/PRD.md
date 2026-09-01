# pysum — product requirements

## 1. What this is

> **pysum finds the things in a dataset that quietly bias an estimate** — sentinel codes hiding as
> real values, missingness that differs by treatment arm, zeros that mean "never asked". It
> **discovers** them without being told what to look for, which is the part a schema validator
> structurally cannot do.

That second sentence is the whole design. `pandera` and `great_expectations` take a declaration and
confirm it: you say the key is unique, that income is a positive float, and they check. They are
good at that and pysum does not compete with them. But you can only declare what you already
suspect, and the errors that survive to publication are the ones nobody suspected — the column read
numerically that swallowed 183 rows of `-999`, the arm that lost 13% of its observations while the
other lost 11%.

Everything pysum reports is a **candidate, not a verdict**. "This column is 47% missing and the
rate differs by treatment arm" is a fact that needs a person; "this is a bug" is a claim the tool
is not entitled to make. Deciding is the analyst's job, and the output is written so that it reads
that way.

### Where it sits

| tool | what it is | why pysum is not that |
|---|---|---|
| [pandera](https://pandera.readthedocs.io/) / [great_expectations](https://greatexpectations.io/) | schema validation: you declare, it verifies | the closest neighbour and the sharpest line. They confirm what you suspected; pysum surfaces what you didn't |
| [skimpy](https://github.com/aeturrell/skimpy) | console summary, a port of R's `skimr`; pandas + polars | mature and good at descriptive summary. pysum is not competing on prettier `describe()` |
| [fg-data-profiling](https://github.com/ydataai/ydata-profiling) (was ydata-profiling) | heavyweight HTML report | slow, large, and now partly commercial. pysum is not building a dashboard |
| [naniar](https://naniar.njtierney.com/) (R) | missing-data tooling incl. `miss_scan_count(data, search)` | the nearest thing to check 1 anywhere, but **you supply the values to search for**. It counts; it does not discover |
| `pandas.describe()` | five numbers | no missingness, no types, no diagnosis |
| **pysum** | **discovery sweep + per-variable table** | names the threats to an estimate, none of which you had to declare first |

### Why this is worth building

The logic already exists and is stranded. `audit-analysis/scripts/audit_data.py` is **433 lines,
pandas-only, untested, unpackaged**, living in a skill directory. It encodes real opinions —
*"differential missingness MANUFACTURES trends and gaps; constant missingness only attenuates"* —
that nothing on PyPI ships.

And `build-data` makes **sentinel codes its very first checkpoint** (`-999`, `999`, `88`).
`profile_columns.R` implements that thoroughly — a catalogue of numeric, string and date
sentinels, and the subtle part: it reads delimited text as *character* on purpose so `-999`
survives, then builds a numeric shadow, because a naive numeric read coerces and reports "none
found" over a column holding 183 rows of `-999`.

That logic is real and hard-won. It is also **760 lines of untested R in a skill directory**, and
nothing *packaged* does it. `naniar::miss_scan_count(data, search)` is the closest thing on CRAN
and it requires you to supply the values to look for — it counts what you already suspected
rather than discovering anything.

Success means that script can be deleted and the skill can `pip install pysum` instead.

## 2. The checks

### The line

An earlier draft listed ten checks, which made pysum a general profiler competing with skimpy from
behind. The rule that decides what stays:

> **pysum discovers. `pandera` verifies.**

If a check requires you to *declare* something first — this is the key, this column lives in
`[0,1]`, this is an integer — then you already suspected the problem, and `pandera` or
`great_expectations` will confirm it better than pysum would. Those tools are mature and own that
job.

What is left is what you did not know to look for. Nothing packaged does it, because a schema
validator structurally cannot: it checks a column against a declaration, and an identification
threat is a *relationship* — between missingness and treatment arm, between a value spike and a
denominator, between a zero and a question that was never asked.

### The four

Every check must name the mistake it prevents. **A check that cannot is cut** — an alert nobody
can act on trains people to ignore alerts. None of these require a declaration; the group column
in check 2 is one optional argument, and its finding is a measured difference rather than a
violated assertion.

| # | check | catches |
|---|---|---|
| 1 | **Sentinel candidates** | a spike at `-999`, `999`, `98`, `99`, `88`, `-1`. Is it missing, not-applicable, or a real top-code? Each implies a different denominator |
| 2 | **Differential missingness** | missingness that differs by group. Constant missingness attenuates an estimate; differential missingness *manufactures* trends and gaps. Threshold: max−min fill rate > 2pp |
| 3 | **Zeros vs missing** | a column with many zeros and no missing — zeros encoding absence, which is survey skip logic leaking into the data |
| 4 | **Dtype traps** | numbers stored as text, IDs silently cast to float and losing their tail digits, a column read numerically that swallowed its own sentinels |

Plus the **per-variable table** pysum ships today — type, stats, top values with frequencies, valid
and missing counts — kept because it is what you read first and it is the surface the findings hang
off. It is not the product.

Check 1 is the flagship and the reason to build this. Checks 2–4 come from `audit_data.py` and
must reproduce its findings.

Every finding is **soft**. There is no exit code and no gating, because none of these are ever
definitely wrong — a spike at `-999` might be a legitimate measurement, and a column that is 40%
zeros might really be 40% zeros. Gating on a judgement call is how a diagnostic becomes something
people route around. Hard, declarative gating is `pandera`'s job and it is good at it.

### Deliberately not here

| dropped | why | where it goes |
|---|---|---|
| shape and keys | you must declare the key first | `pandera`; the join case is `joincontract` |
| values outside a logical range | you must declare the range first | `pandera` |
| distributions, skew, tails | changes which *method* is defensible, not whether the data is sound | `infercheck` |
| rate vs reconstructed denominator | about a specification, not a column | `infercheck` |
| leverage / DFBETAS | needs an outcome and covariates — that is "audit my regression", a different act | `infercheck` |
| join contracts | a merge is its own operation with its own contract | `joincontract` |

## 3. API

The current design is the problem: `summarizeDF(df)` writes a file, returns nothing, and requires
a monkey-patched `df.name`.

```python
import pysum

report = pysum.profile(df, by="arm")    # pure; returns an object, writes nothing
report.findings                          # list of Finding(check, column, message, stat)
report.variables                         # the per-variable table
print(report.summary())                  # the console slice
report.to_markdown(path) / .to_html(path)
```

`by=` is the only argument that changes what is found — it turns on check 2. Everything else runs
unprompted.

Rules:

- **`profile()` has no side effects.** No files, no printing, no global state.
- **Rendering and writing are separate calls.** Producing a summary and putting it on disk are
  different decisions.
- **No required attributes on the input.** A name is an optional argument, never a monkey-patch.
- **A `Finding` carries the number it was derived from**, in `stat`, not just prose. Someone will
  want to assert on it in their own test, and a string is the wrong thing to assert on.
- **HTML is generated in-process.** The current code shells out to `pandoc` through `os.system`,
  which fails silently when pandoc is absent and interpolates a user-supplied filename into a
  shell command.
- **The CLI exits zero when it finds things.** Findings are candidates, and a tool that fails a
  build over a judgement call gets `|| true` appended to it within a week. `--fail-on-findings`
  exists for anyone who wants the other behaviour, off by default.

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

1. **The four checks are deleted from `audit_data.py`**, and `audit-analysis` calls pysum for them.
   The script's remaining checks — skew, denominators, leverage — stay put until `infercheck`
   exists to take them. Until pysum reproduces the script's findings on a dataset with known
   problems, the rewrite has not earned its thesis.
2. **Every check has a fixture that trips it and a fixture that does not.** A diagnostic that never
   fires and one that always fires are equally useless.
3. **The sentinel check is validated on data that has already fooled a numeric read.** The
   character-shadow read is the non-obvious part of `profile_columns.R` and the thing that
   distinguishes this from `naniar`; a test that only exercises a clean pandas frame does not
   verify it. The Assam electoral-roll work and `notnews` data carry real codes.
4. **The differential-missingness check reports a number, not a verdict**, and that number is
   asserted on in a test — a fill-rate gap the fixture was built to have.
5. Runs on pandas and polars, verified by the same test suite over both.
6. `preen check --strict` clean; py-canon adopted.

## 7. Out of scope

- **Anything you have to declare first.** Keys, ranges, dtypes, nullability — `pandera` and
  `great_expectations` own that and are better at it. This is the boundary the check list is
  derived from, not a footnote to it.
- Modelling, imputation, or fixing anything. It reports; the analyst decides.
- Plots and HTML dashboards — that is fg-data-profiling's product.
- Competing with skimpy on console aesthetics.
- Backward compatibility. The old entry point requires a monkey-patched attribute, is broken on
  current pandas, and has ~31 downloads a month. It goes.
