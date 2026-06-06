# RC Reports

Royal Canin period report generator for the
[every_nownthen](../../README.md) runner.

What it does:

1. Reads Royal Canin products from Dashy dimension `product`.
2. Calculates the selected 28-day report period from period number `1..13`.
3. Pulls sales, stock, and USD exchange-rate data from Dashy.
4. Fills `RC_Report_Template_2026.xlsx` with SKU, product name, stock on hand,
   sales USD, and sales KG.
5. Sends the generated workbook by Gmail API to `RC_REPORTS_EMAIL_TO`.

## Dashy API source

The implementation follows the Dashy OpenAPI contract at:

<https://bi.vetify.co.ao/api/openapi.yaml>

Relevant resources:

- `GET /api/dimensions/product` — product dimension (`gold.dim_product`), with
  `sku`, `product_name`, `brand`, and `rc_weight`.
- `GET /api/datasets/client_top_products` — per-SKU `revenue_aoa` and
  `units_sold`, filtered by `date.from`, `date.until`, and `brand`.
- `GET /api/datasets/product_stock_daily` — `stock_qty` snapshot for a SKU.
- `GET /api/datasets/currency_rates_vs_units` — `avg_usd_rate` for the period
  end date.

Dashy API key authentication is bootstrapped via `api_key` on the product
dimension request; Dashy then sets a temporary `dashy_session` cookie used by
subsequent metric/dataset requests.

## Usage

```bash
cd scripts/rc_reports
uv run rc_reports.py <period_number>
uv run rc_reports.py auto
```

`<period_number>` must be from `1` to `13`. Periods are inclusive 28-day
windows. The period start year is always the current runtime year. With
`RC_REPORTS_PERIOD_START_MONTH_DAY=01-01`:

- Period 1: 2026-01-01 → 2026-01-28
- Period 2: 2026-01-29 → 2026-02-25
- Period 13: 2026-12-03 → 2026-12-30

`auto` checks the current date and only sends on scheduled report days:

- P1 runs 30 days after the period start day.
- P2-P12 run every 28 days after P1.
- P13 runs on 30 December every year.
- Non-scheduled days exit successfully without sending.

## Environment variables

All consumed from the project-root `.env`. Documented in
`every_nownthen/.env.info` under the "RC Reports" section. Required:

- `DASHY_API_KEY`
- `RC_REPORTS_EMAIL_TO`
- `SERVICE_ACCOUNT_KEY_PATH`

Optional:

- `RC_REPORTS_PERIOD_START_MONTH_DAY` — defaults to `01-01`
- `RC_REPORTS_OUTPUT_DIR` — defaults to `/tmp`

The Gmail impersonated user and email headers are fixed in `rc_reports.py`:
`comercial@vetify.co.ao`, `Vetify <comercial@vetify.co.ao>`, and
`encomendas@vetify.co.ao`.

## Schedule

Defined in `every_nownthen/crontab`:

```cron
30 9 * * * . /etc/environment; cd /app/scripts/rc_reports && /root/.local/bin/uv run rc_reports.py auto >> /var/log/cron.log 2>&1
```

The cron job runs daily at 09:30 (container `TZ`), but `auto` only sends on the
scheduled period dates.

## Tests

```bash
cd scripts/rc_reports && uv run --with pytest --with requests --with openpyxl -m pytest tests
```
