# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A test suite covering every output format and both column kinds.
- `py.typed`: the package now ships its type information.

### Changed

- Adopted the [py-canon](https://github.com/gojiplus/py-canon) fleet standard:
  `uv_build` backend, reusable CI/docs/release workflows, ruff, pyright and
  pydoclint. Retired Travis, AppVeyor, tox, `.pep8speaks.yml`, `requirements.txt`
  and the readthedocs config.
- Moved the package to `src/pysum/` and the docs to the standard `docs/` layout;
  the README is now Markdown and is included into the docs rather than copied.
- Renamed the internal helpers on `SummaryTool` to snake_case. The public entry
  points, `pysum.summarizeDF` and `SummaryTool.summarizeDF`, keep their names.

### Fixed

- Character columns are summarized again. The dtype test compared against the
  literal string `'object'`; pandas 3 gives string columns a `StringDtype`, so
  text columns had been rendering with an empty stats cell and a distinct-value
  count in place of their frequency table.
- The markdown table printed to stdout has real column headers again.
  `pytablewriter` renamed `header_list` to `headers`, and assigning the old name
  silently did nothing, so the table printed with `A`, `B`, `C`, ... instead.
- `output_type="xlsx"` works on a clean install. `pytablewriter`'s Excel writer
  needs its `excel` extra, which was not declared.
- The pandoc call behind `output_type="html"` no longer goes through the shell,
  and raises a clear error when pandoc is not installed.

## [0.1.1] - 2018-06-23

Initial release on PyPI.

[Unreleased]: https://github.com/finite-sample/pysum/commits/master/
[0.1.1]: https://pypi.org/project/pysum/0.1.1/
