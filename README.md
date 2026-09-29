# maagarim_all

Fork-ready local demo project based on `BodekOktzim/maagarim-eg-el-fa`.

## Included

- The original open-source application code.
- A local unified-search tool under `tools/unified-search/`.
- Search across CSV, TSV, TXT, SQL and XLSX files.
- Matching by normalized email/phone and source provenance.
- Sensitive-field masking for password/CVV/token/card-like fields.

## Run unified search

Put authorized synthetic/demo files in `datasets/` locally, then run:

```bash
./scripts/run-unified-search.sh
```

Open `http://localhost:5000`.

## Data publication policy

Dataset files and generated indexes are excluded from Git. This is deliberate: even synthetic-looking data may contain personal-looking fields or credentials, and public publication is unsafe by default. Use a private repository and explicit authorization before sharing any dataset.
