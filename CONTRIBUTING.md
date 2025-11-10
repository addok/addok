# Development Setup

This project uses modern Python packaging with `pyproject.toml` (PEP 621).

## Installing for development

```bash
pip install -e ".[dev]"
```

> **Note:** If using zsh, you need to quote `.[dev]` to avoid glob pattern expansion errors.

Or using the Makefile:

```bash
make develop
```

This will install the package in editable mode along with all development dependencies (pytest, pytest-cov, mkdocs, build, twine, hiredis).

## Running tests

```bash
make test
```

Or with coverage:

```bash
make testcoverage
```

## Building the package

```bash
make dist
```

This uses `python -m build` to create both source distribution (`.tar.gz`) and wheel (`.whl`) files.

# Publishing a new version of the package

- Update the version number in `pyproject.toml`
- Update the CHANGELOG
- git commit -m "vX.Y.Z"
- git tag vX.Y.Z
- make dist
- make upload
- git push
- git push --tag
