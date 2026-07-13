# Coding Conventions

- **Python Standards**:
  - Code formatter: **black** (88 characters line limit).
  - Linter: **ruff** for code quality.
  - Type hints: Required on all public function signatures.
  - Test suites: Standard library `unittest` or `pytest`. Run `pytest backend/tests/` to run all test cases.

- **JavaScript / Frontend Standards**:
  - Code formatter: **prettier**.
  - Code style: Modern ES6 syntax, react functional components only, hook-based state management.
  - CSS: Vanilla CSS + responsive flexbox/grid layout design (wow factor).

- **Commit Prefixes**:
  - For quick scanning in a 3-person log, prefix commit messages with owner initials:
    - `a: ...` for Person A (Frontend)
    - `b: ...` for Person B (RAG Core)
    - `c: ...` for Person C (Defense/Security)
    - Example: `git commit -m "b: hybrid rank fusion implement"`
