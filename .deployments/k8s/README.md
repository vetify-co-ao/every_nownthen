# Kubernetes deployment

The production workload runs as one long-lived cron container in namespace
`vetify`. Tagged releases build and deploy through `.github/workflows/deploy.yml`.

## Prerequisites

- `kubectl` access to the production cluster.
- Docker Hub and DigitalOcean credentials configured in GitHub Actions.
- A Google service-account JSON key with domain-wide delegation for
  `comercial@vetify.co.ao` and the `gmail.send` scope.
- Read-only production API keys for VCRM, VPIM, VSCO, Dashy, and Vendus.

## Production secrets

Do not store credentials in ConfigMaps. Prepare a mode-`600` env file outside
the repository containing the variables documented in `.env.info`, then apply:

```bash
kubectl -n vetify create secret generic every-nownthen-env-secret \
  --from-env-file=/secure/path/every-nownthen.prod.env \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n vetify create secret generic every-nownthen-service-account-secret \
  --from-file=service_account.json=/secure/path/service-account.json \
  --dry-run=client -o yaml | kubectl apply -f -
```

The env secret must set:

```text
VENDUS_API_KEY
VCRM_API_KEY
VPIM_API_KEY
DASHY_API_KEY
VSCO_API_KEY
SERVICE_ACCOUNT_KEY_PATH=/etc/service_account.json
TZ=Africa/Luanda
```

`DASHY_API_KEY` and `VSCO_API_KEY` are optional at application level, but they
should be configured in production to enable expiry and cargo enrichment.

Verify key names without printing values:

```bash
kubectl -n vetify get secret every-nownthen-env-secret \
  -o jsonpath='{.data}' | jq -r 'keys[]'
```

## Release

The workflow deploys on a pushed tag:

```bash
git tag -a v1.2.0 -m "Release v1.2.0"
git push origin main
git push origin v1.2.0
```

The Deployment uses `Recreate` with one replica so an old and new cron process
cannot overlap during rollout.

## Verification

```bash
kubectl -n vetify rollout status deployment/every-nownthen
kubectl -n vetify get pods -l app=every-nownthen
POD=$(kubectl -n vetify get pod -l app=every-nownthen -o jsonpath='{.items[0].metadata.name}')
kubectl -n vetify logs "$POD" --tail=100
kubectl -n vetify exec "$POD" -- sh -lc \
  '. /etc/environment; cd /app/scripts/ixlsx && uv run ixlsx.py --dry-run'
```

The dry run must report VCRM templates `DJBTl5Ls` and `G64RDgSJ`, create HTML,
XLSX, EML, and JSON files, and must not call Gmail.

To send an end-to-end test only to `IXLSX_TEST_EMAILS`:

```bash
kubectl -n vetify exec "$POD" -- sh -lc \
  '. /etc/environment; cd /app/scripts/ixlsx && uv run ixlsx.py test all_e2e'
```

After the deployed dry run succeeds, CI removes the two legacy credential
ConfigMaps. Credentials remain only in Kubernetes Secrets.

## Monitoring and rollback

```bash
kubectl -n vetify exec "$POD" -- tail -f /var/log/cron.log
kubectl -n vetify rollout history deployment/every-nownthen
kubectl -n vetify set image deployment/every-nownthen \
  every-nownthen=zafircoao/vetify-every-nownthen:<previous-image-tag>
```

Use `set image`, not `rollout undo`: historical revisions before `v1.2.0`
referenced credential ConfigMaps that are deleted after this release.

Deploy away from Monday/Thursday at 08:00 `Africa/Luanda`. Production delivery
is rejected by the application on other weekdays; dry-run and test modes remain
available every day.
