# iXLSX

Scheduled offer mailer that runs as a script inside the
[every_nownthen](../../README.md) runner.

What it does:

1. Pulls product inventory and active client emails from the Vendus API.
2. Fills a bundled XLSX template (`vetify-template.xlsx`) with stock status,
   net price, and the current offer date.
3. Renders an HTML body from the bundled `email-template.html`.
4. Sends the result via the Gmail API (service account with domain-wide
   delegation), BCC'ing all clients.

## Schedule

Defined in `every_nownthen/crontab`:

```
0 8 * * mon,thu . /etc/environment; cd /app/scripts/ixlsx && /root/.local/bin/uv run ixlsx.py >> /var/log/cron.log 2>&1
```

Mondays and Thursdays at 08:00 (container `TZ`).

## Dependencies

Declared inline at the top of `ixlsx.py` using PEP 723 script metadata. UV
materialises them on first `uv run` and caches the venv. No `pyproject.toml`
or `requirements.txt`.

## Environment variables

Consumed from the project-root `.env` and documented in
`every_nownthen/.env.info` under the "iXLSX" section. Required:
`VENDUS_API_KEY`, `SERVICE_ACCOUNT_KEY_PATH`.

The Gmail impersonated user and email headers are fixed in `ixlsx.py`:
`comercial@vetify.co.ao`, `Vetify <comercial@vetify.co.ao>`,
`encomendas@vetify.co.ao`, and `Oferta Vetify %s`.

## Bundled assets

- `vetify-template.xlsx` — Excel template. Sheet `Sheet1`, references in
  column A from row 5, date cell `D2`. Stock status → C, net price → D,
  due date cleared in I when out of stock.
- `email-template.html` — HTML email body.

Edit either file in-repo and redeploy. There is no env override.

## E2E test

```
docker compose exec app sh -c \
  "cd /app/scripts/ixlsx && uv run ixlsx.py test all_e2e"
```

Sends to the addresses in `IXLSX_TEST_EMAILS` only. Requires that var to be
set; otherwise the test aborts.

## Tests

```
cd scripts/ixlsx && uv run -m pytest tests
```
