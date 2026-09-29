# Local demo data

Place authorized synthetic/demo files here locally. Dataset files are intentionally excluded from Git by `.gitignore`.

Build the local unified index:

```bash
python3 tools/unified-search/indexer.py datasets --db tools/unified-search/unified.sqlite
python3 tools/unified-search/app.py tools/unified-search/unified.sqlite
```

This keeps large datasets out of the repository and avoids publishing personal-looking records by accident.
