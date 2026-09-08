# Boletim Bissemanal Vetify

Scheduled operational bulletin and reseller order workbook. It runs on Monday
and Thursday at 08:00 in `Africa/Luanda`.

## Sources

| Source | Purpose | Failure policy |
|---|---|---|
| VCRM | Recipient emails, announcements, HTML/XLSX templates | Abort |
| VPIM | Active catalog, taxonomy, price, VAT, highlights | Abort |
| Vendus | Live stock | Abort |
| Dashy | Nearest future lot expiry with remaining quantity | Leave expiries blank |
| VSCO | Cargo in transit and cleared in the last seven days | Omit cargo sections |

All source access is read-only. Templates are always downloaded from VCRM:

- XLSX node `DJBTl5Ls`
- HTML node `G64RDgSJ`

There is no bundled template or local fallback.

## Business rules

- Recipients are deduplicated primary emails from VCRM resellers in `Activo` or
  `Incumprimento`; establishment emails are not used.
- Every active VPIM product appears in the XLSX, including products not found in
  Vendus.
- Availability is `SOB CONSULTA` without a Vendus match, `ESGOTADO` at stock
  `<= 0`, `ULTIMAS UNIDADES` at stock `<= commercial-performance:minimum-stock`,
  and `EM STOCK` above it. Missing minimum stock uses 10 and records an anomaly.
- Price and VAT come from VPIM. Multiple categories/subcategories are joined by
  ` · `.
- Expiry is filled only for positive Vendus stock and uses the nearest future
  Dashy lot with positive remaining quantity.
- Every active VCRM announcement is shown to every recipient; target metadata is
  intentionally ignored. Start/end dates determine whether it is active.
- Every active featured VPIM product is rendered. Missing image or description
  removes only that element from its card.
- Cargo cards show the nature of the goods, never individual SKUs.
- Issue numbers are `(ISO week × 2) − 1` for the Monday edition and
  `ISO week × 2` for the Thursday edition.

## Commands

Generate HTML, XLSX, EML, and JSON report without calling Gmail:

```bash
cd scripts/ixlsx
uv run ixlsx.py --dry-run
```

Send an end-to-end test only to `IXLSX_TEST_EMAILS`:

```bash
uv run ixlsx.py test all_e2e
```

Normal production delivery (used by cron):

```bash
uv run ixlsx.py
```

Production delivery fails outside Monday/Thursday. All mandatory-source,
template, attachment, and Gmail errors produce a non-zero process exit.

## Environment

Required:

- `VENDUS_API_KEY`
- `VCRM_API_KEY`
- `VPIM_API_KEY`

Required for Gmail delivery:

- `SERVICE_ACCOUNT_KEY_PATH` points to the mounted Google JSON key.

Optional enrichments and settings:

- `DASHY_API_KEY`
- `VSCO_API_KEY`
- `IXLSX_OUTPUT_DIR` controls artifact output (default `/tmp`).
- `IXLSX_TEST_EMAILS` controls test recipients.

See [`.env.info`](../../.env.info) for the complete contract.

## XLSX

The renderer corrects the VCRM workbook at runtime:

- products begin at row 6;
- `F = D × (1 + E)`;
- `H = IF(G="", "", G × F)`;
- `H3 = SUM(H6:Húltima_linha)`;
- table, validation, and conditional-format ranges end on the final product row;
- freeze pane is `A6`;
- hidden brand and availability lists are refreshed.

## Tests

```bash
cd scripts/ixlsx
uv run --with pytest --with requests --with openpyxl \
  --with google-api-python-client --with google-auth \
  --with google-auth-httplib2 -m pytest
```
