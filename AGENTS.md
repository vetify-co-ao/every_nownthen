# every_nownthen — agent guide

Containerised cron runner for Python scripts. Two execution surfaces:

- **Local scripts** under `scripts/<name>/` — copied into the image at
  `/app/scripts/<name>/` and invoked with `uv run`.
- **UV tools** listed in `uv_tools.txt` — installed at build time via
  `uv tool install` and exposed as binaries in `/root/.local/bin/`.

The entrypoint dumps `printenv` into `/etc/environment` at startup so cron
jobs can `. /etc/environment;` to see `.env` values.

## Adding a local script

1. Create `scripts/<name>/<name>.py`.
2. Declare deps **inline** with PEP 723 (preferred — no extra files):

   ```python
   # /// script
   # requires-python = ">=3.12"
   # dependencies = [
   #     "requests",
   #     "openpyxl",
   # ]
   # ///
   ```

   `uv run` reads the header, builds an isolated venv, and caches it. The
   first run is slow; subsequent runs are fast.

   Use a `pyproject.toml` only if the script grows multiple modules or needs
   a feature PEP 723 doesn't support (e.g. dependency groups, build
   backends). For single-file scripts, stay with PEP 723.

3. Read configuration from `os.environ` only. Document new vars in
   `.env.info` and add placeholders to `.env.example`. Never hardcode
   secrets or test recipients.

4. Bundle static assets (templates, fixtures) next to the script and load
   them via `os.path.dirname(__file__)`. Don't expose those paths as env
   vars — they're versioned with the code.

5. Tests go in `scripts/<name>/tests/` and run with `uv run -m pytest tests`
   from the script directory.

## Adding a UV tool dependency

For reusable tooling that lives in another git repo:

1. Append a line to `uv_tools.txt`:

   ```
   git+https://github.com/owner/repo.git
   ```

   Use `git+ssh://git@github.com/owner/repo.git` for private repos.

2. Rebuild the image. `install_uv_tools.sh` runs `uv tool install` for each
   line; the binary lands in `/root/.local/bin/<tool-name>`.

3. Reference it from `crontab` by absolute path
   (`/root/.local/bin/<tool-name>`) — no `uv` prefix needed.

## Configuring cron

Edit `crontab` at the project root. Format is standard cron, with two
non-negotiable conventions for this image:

- Prefix every command with `. /etc/environment;` so `.env` vars are visible
  to the cron shell.
- Redirect to `/var/log/cron.log` so output shows up in `docker logs`.

**Local script template:**

```
M H * * * . /etc/environment; cd /app/scripts/<name> && /root/.local/bin/uv run <name>.py >> /var/log/cron.log 2>&1
```

**UV tool template:**

```
M H * * * . /etc/environment; /root/.local/bin/<tool-name> [args] >> /var/log/cron.log 2>&1
```

`uv` lives at `/root/.local/bin/uv` (not `/root/.cargo/bin/uv` — the README
example is stale). Set `TZ` in `.env` to align cron firing times with a
timezone (currently `Africa/Luanda`).

After editing `crontab`, rebuild the container — the file is loaded into
the user's crontab in the Dockerfile (`crontab /app/crontab`), not at
runtime.

## Environment variables

- `.env` — real values, gitignored, mounted by docker-compose.
- `.env.info` — documents every var (description, required, default, used
  by). Update whenever a script reads a new var.
- `.env.example` — placeholder values for the same set; safe to commit.

Required vars are read with `os.environ["KEY"]` so the script fails fast at
import. Optional vars use `os.environ.get("KEY", default)`.

Vars that are reasonably shared across scripts (Vendus, Google service
account, company info) keep short generic names. Script-specific vars
should be prefixed with the script name (e.g. `IXLSX_OUTPUT_DIR`,
`IXLSX_TEST_EMAILS`) to avoid collisions.

## Build & run

```
docker compose build
docker compose up -d
docker compose logs -f
```

Manual one-off run inside the container:

```
docker compose exec app sh -c "cd /app/scripts/<name> && uv run <name>.py"
```

## Gotchas

- **Python version**: image is `python:3.12-slim` but the root
  `pyproject.toml` declares `>=3.14`. UV manages its own interpreters per
  script, so PEP 723 headers should pin `>=3.12` to match the runtime.
- **Cron env**: forgetting `. /etc/environment;` makes vars silently empty.
- **Crontab is built-in**: the `crontab` file is `crontab`-installed at
  image build, so changes need a rebuild — not just a container restart.
- **First run latency**: `uv run` materialises the venv on first execution.
  If the cron window is tight, warm the venv during build or in the
  entrypoint.
