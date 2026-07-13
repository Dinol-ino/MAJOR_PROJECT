# Security Checklist

Verify these checklist items before merging any pull request to `dev` or `main`:

- `[ ]` **No dynamic SQL**: Under no circumstances should SQL queries be built using python `f-string`, `.format()`, or string concatenation. Use parameterized queries only.
- `[ ]` **No eval/exec**: Ensure that no user-supplied input or retrieved document text passes through standard python `eval()` or `exec()` interpreters.
- `[ ]` **PDF Extraction Sandboxing**: Ensure files are only read as plain text via `pdfplumber`. Enforce size limits (e.g. maximum 10MB) and page limits (e.g. up to 100 pages) before parsing.
- `[ ]` **Data Boundary Isolation**: Verify that all RAG retrieval outputs are strictly wrapped in `<data> ... </data>` XML-style boundary blocks when constructing the final system prompt.
- `[ ]` **Fail-Closed Pipelines**: Verify that any validation failure in Layer 1, Layer 2, or Layer 3 throws a strict error, quarantining the request (fails-closed with explicit error reporting in the audit logs) instead of passing unfiltered text to the user.
