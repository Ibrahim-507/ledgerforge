# LedgerForge delivery audit (2026-11-20)

## Changes made in this delivery

- Kept the existing application structure, database mappings, routes, and seed data intact.
- Corrected `.env.example`: all configured values are now clearly marked as placeholders. The sample demo password is no longer a real-looking default, and local data-path overrides were removed so the documented Docker seed path remains authoritative.
- Corrected `trial_balance_csv()` so the official checker receives cumulative journal debit/credit activity per account in its `debit` and `credit` columns. The human-facing `closing_debit` and `closing_credit` fields remain present. Previously the export supplied net closing balances, which caused 13 false mismatches against the official activity-based checker.

## Verification run

Commands run from the repository root:

```bash
python -m pytest -q tests/test_release_files.py tests/test_release_extras.py tests/test_versioning.py tests/test_security.py tests/test_financials.py --disable-warnings
python verify_ledgerforge.py checks --data csv
python verify_ledgerforge.py payroll payroll_results.csv --data csv
python -m scripts.task15_run csv
python verify_ledgerforge.py trial-balance my_trial_balance.csv --data csv
python verify_ledgerforge.py summary --data csv
```

Results:

- Selected release, versioning, security, and financial-report tests: **40 passed**.
- Official integrity checks: **5/5 passed**.
- Payroll comparison: **7,340 / 7,340 rows match (100%)**.
- Trial balance comparison: **40 accounts, 0 mismatches**.
- Official headline totals: revenue **1,260,930,052.00**; expenses **1,036,246,464.42**; profit **224,683,587.58**; 18 payroll runs; employer cost **861,586,392.42**.
- Task 15 report: assets **463,762,958.65** equal liabilities + equity + current profit **463,762,958.65** at 2026-09-30.

The full pytest suite was attempted, but the execution environment interrupted the run at its 60-second limit before completion. No full-suite pass is claimed here.

## Deployment boundary / actions still requiring your accounts

The repository contains Docker, Compose, hosted-PostgreSQL configuration, seed data, health checks, CI, smoke-test script, backup/restore scripts, and API documentation. A real public deployment has **not** been performed from this delivery: it requires your cloud-hosting account, hosted PostgreSQL credentials, secret values, and permission to publish the service. Do not put those secrets in Git or send them in chat.

Before calling this production-live, complete these steps in your hosting provider:

1. Create a managed PostgreSQL database and (if using background jobs) a managed Redis instance.
2. Configure `LEDGERFORGE_SECRET_KEY` (at least 32 random characters), `POSTGRES_PASSWORD`, and `DEMO_PASSWORD` as host-side secrets.
3. Build and deploy the Docker image; confirm the API can reach PostgreSQL and Redis.
4. Run migrations and seed the official Zenith Nova data once; persist `/var/lib/ledgerforge` because the current books/ledger store remains SQLite on a persistent volume.
5. Open `/health` and `/docs`, then run `python smoke_test.py https://YOUR-LIVE-URL` with `SMOKE_USER` and `SMOKE_PASSWORD` set to valid credentials.
6. Run the integrity checks against an export from the deployed instance, record the actual URL, and only then mark LF-17 as complete.

**Architecture note:** PostgreSQL backs the employee/application database in the current Compose configuration. The accounting books store is still SQLite on a persistent volume, as also disclosed in `docs/RELEASE_NOTES.md`. This delivery intentionally does not rewrite the mapped books database layer.

## Submission checklist

- [ ] Push the code and create the requested Git tag(s) in your own GitHub repository.
- [ ] Deploy using your own cloud credentials and record the live API URL.
- [ ] Verify the public `/docs` URL and `/health` response.
- [ ] Run the live smoke test and export-based integrity checks.
- [ ] Record a five-minute demo and attach the final release notes / test report.
