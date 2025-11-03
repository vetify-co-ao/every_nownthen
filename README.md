# Every Now & Then - Autonomous Python Script Runner

An autonomous Python script runner designed to execute scheduled Python scripts in isolated virtual environments using Docker, UV, and cron. Each script runs in its own UV-managed virtual environment to prevent dependency conflicts.

## Overview

Every Now & Then provides a containerized environment for running Python scripts on a schedule using UV's powerful project management. Scripts can be:

1. **Local scripts**: Placed in the `scripts/` directory with UV project configuration
2. **UV tools**: Installed from GitHub repositories as UV tools at container build time

Each script runs in isolation with its own dependencies, managed by UV and `pyproject.toml` files.

## Project Structure

```
every_nownthen/
├── scripts/                    # Local scripts directory
│   ├── say_hello/             # Example script
│   │   ├── say_hello.py       # Main script file
│   │   ├── pyproject.toml     # UV project config (optional)
│   │   └── README.md          # Script documentation
│   └── process_data/          # Another example
│       ├── process_data.py
│       ├── pyproject.toml
│       └── README.md
├── install_uv_tools.sh        # Install UV tools from Git
├── uv_tools.txt               # List of Git repos to install as UV tools
├── crontab                     # Cron schedule configuration
├── Dockerfile                  # Container definition
├── docker-compose.yml         # Docker Compose configuration
├── .env.example               # Environment variables template
├── .env.info                  # Environment variables documentation (committed)
├── .env                       # Actual environment values (gitignored, DO NOT COMMIT)
└── README.md                  # This file
```

## Script Directory Structure

Each script must follow this structure:

```
scripts/
└── <script_name>/
    ├── <script_name>.py       # Main Python file (any name works)
    ├── pyproject.toml         # Optional: UV project dependencies
    └── README.md              # Optional: documentation
```

### Example: say_hello

```
scripts/
└── say_hello/
    ├── say_hello.py
    ├── pyproject.toml         # If script has dependencies
    └── README.md
```

### Example pyproject.toml

```toml
[project]
name = "my-script"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31.0",
    "pandas>=2.0.0",
]
```

## UV Tools (Git-Based Scripts)

Scripts can also be installed as UV tools from Git repositories. This is ideal for:

- Reusable scripts across multiple projects
- Scripts maintained in separate repositories
- Third-party automation tools

### Configuration

Add Git repositories to `uv_tools.txt`:

```txt
# UV Tools - Git repositories to install as tools
git+ssh://git@github.com/kindalus/agentic_document_archiver.git
git+https://github.com/your-org/your-tool.git
```

UV tools are installed at container build time using `install_uv_tools.sh`.

### Running UV Tools

UV tools are installed system-wide and can be run directly without the `uv` command:

```bash
# Inside container - run directly
agentic_document_archiver

# In cron - no uv command needed
0 */6 * * * agentic_document_archiver >> /var/log/cron.log 2>&1
```

## Environment Variables

All scripts rely on environment variables configured in the `.env` file.

### Important Security Notes

⚠️ **NEVER commit `.env` files to version control** - they contain sensitive data!

- `.env` is in `.gitignore` and should never be committed
- Use `.env.info` to document what variables are needed (this IS committed)
- Use `.env.example` as a template with example/placeholder values
- Environment variables are loaded by Docker Compose from `.env` file

### Environment Configuration Files

- **`.env.info`** - Documents all required environment variables (committed to git)
  - Describes each variable's purpose
  - Lists which scripts use each variable
  - Specifies required vs optional variables
  - **This is your source of truth for environment documentation**

- **`.env.example`** - Template with example values (committed to git)
  - Safe placeholder values
  - Shows the format of each variable
  - Used as a starting point

- **`.env`** - Actual values (GITIGNORED, never committed)
  - Contains real API keys, passwords, etc.
  - Created locally by each developer/deployment
  - Loaded automatically by Docker Compose

### Setup

1. Review `.env.info` to see what variables are needed:

```bash
cat .env.info
```

2. Copy the example environment file:

```bash
cp .env.example .env
```

3. Edit `.env` with your actual configuration:

```bash
# Edit with real values - this file will NEVER be committed
vim .env
```

4. Variables are automatically loaded by Docker Compose (via `env_file` in docker-compose.yml)

## Running Scripts with UV

### Manual Execution

```bash
# Run a script from its directory
cd scripts/say_hello
uv run say_hello.py

# Or from anywhere
cd scripts/say_hello && uv run say_hello.py
```

### Inside Docker

```bash
# Execute a script manually
docker-compose exec app sh -c "cd /app/scripts/say_hello && uv run say_hello.py"

# Run a UV tool
docker-compose exec app uv tool run agentic_document_archiver
```

## Docker Deployment

### Build and Run

```bash
# Build the container
docker-compose build

# Start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

### Container Features

- Based on Python 3.11 slim image
- UV package manager pre-installed
- Git support for cloning script repositories
- Cron service for scheduled execution
- Environment variables from .env file
- Isolated virtual environments per script

## Scheduling Scripts with Cron

Configure cron jobs in the `crontab` file:

```bash
# Edit crontab file
vim crontab
```

### Example Crontab

```bash
# Run say_hello every day at 9 AM
0 9 * * * cd /app/scripts/say_hello && /root/.cargo/bin/uv run say_hello.py >> /var/log/cron.log 2>&1

# Run process_data every hour
0 * * * * cd /app/scripts/process_data && /root/.cargo/bin/uv run process_data.py >> /var/log/cron.log 2>&1

# Run a UV tool every 6 hours (tools are system-wide, no uv command needed)
0 */6 * * * agentic_document_archiver >> /var/log/cron.log 2>&1
```

**Important**:

- Use full path to UV: `/root/.cargo/bin/uv`
- Change to script directory: `cd /app/scripts/script_name`
- Redirect output: `>> /var/log/cron.log 2>&1`

Cron format: `minute hour day month weekday command`

See: https://crontab.guru/ for help with cron expressions

## Development

### Adding a New Local Script

1. Create the script directory:

```bash
mkdir -p scripts/my_script
```

2. Create the main Python file:

```bash
touch scripts/my_script/my_script.py
```

3. Add dependencies (optional) - create `pyproject.toml`:

```bash
cat > scripts/my_script/pyproject.toml << EOF
[project]
name = "my-script"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31.0",
]
EOF
```

4. Test locally:

```bash
cd scripts/my_script
uv run my_script.py
```

### Adding a UV Tool from Git

1. Edit `uv_tools.txt`:

```txt
git+ssh://git@github.com:your-org/your-tool.git
```

2. For private repositories, configure SSH keys in Dockerfile

3. Rebuild the container:

```bash
docker-compose build
```

### Adding a Cron Schedule

1. Edit the `crontab` file:

```bash
# Add your schedule
0 9 * * * cd /app/scripts/my_script && /root/.cargo/bin/uv run my_script.py >> /var/log/cron.log 2>&1
```

2. Rebuild the container:

```bash
docker-compose build
docker-compose up -d
```

## Virtual Environment Management

Every Now & Then uses UV to manage per-script virtual environments:

- **Location**: `scripts/<script_name>/.venv/`
- **Creation**: Automatic when running `uv run`
- **Dependencies**: Installed from `pyproject.toml` using `uv sync`
- **Isolation**: Each script has its own packages

### Benefits

- No dependency conflicts between scripts
- Fast environment creation with UV
- Easy to update per-script dependencies
- Clean separation of concerns
- UV's lockfile support for reproducible builds

## Requirements

- **Docker** and **Docker Compose**
- **UV** (for local development)
- **Git** (for UV tools from private repos)
- **SSH keys** configured (if using private repositories)

## Troubleshooting

### Dependencies Not Installing

Check that `pyproject.toml` is valid:

```bash
# Test UV sync locally
cd scripts/my_script
uv sync
```

### Environment Variables

Verify `.env` file exists and contains required variables:

```bash
cat .env
```

### Cron Not Running

Check cron logs inside the container:

```bash
docker-compose exec app cat /var/log/cron.log
```

Verify UV path in crontab:

```bash
docker-compose exec app which uv
# Should show: /root/.cargo/bin/uv
```

### UV Tool Installation Failures

Check SSH keys are properly configured for private repositories:

```dockerfile
# In Dockerfile, uncomment and configure:
RUN mkdir -p /root/.ssh
COPY id_rsa /root/.ssh/id_rsa
RUN chmod 600 /root/.ssh/id_rsa && \
    ssh-keyscan github.com >> /root/.ssh/known_hosts
```

## Security Considerations

1. **Environment Variables**:
   - ⚠️ **NEVER commit `.env` files** - they are gitignored for security
   - `.env` contains sensitive data (API keys, passwords, credentials)
   - Use `.env.info` to document variables (safe to commit)
   - Use `.env.example` for templates (safe to commit)
   - Docker Compose loads variables automatically from `.env`

2. **SSH Keys**: Use read-only deploy keys for Git repositories

3. **Container Isolation**: Scripts run in isolated environments

4. **Secrets Management**: Use Docker secrets for sensitive data in production

5. **File Permissions**: Ensure `.env` has restricted permissions (600)

## UV Features Used

- **`uv run`**: Executes scripts in their own virtual environments
- **`uv sync`**: Installs dependencies from pyproject.toml
- **`uv tool install`**: Installs tools from Git repositories
- **`uv tool run`**: Runs globally installed UV tools
- **`pyproject.toml`**: Modern Python project configuration

## Cron File

The `crontab` file in the project root contains all scheduled jobs. This file is:

- Version controlled (safe to commit)
- Loaded into the container at build time
- Easy to review and modify
- Supports comments and documentation

Example structure:

```bash
# Data processing jobs
0 2 * * * cd /app/scripts/process_invoices && /root/.cargo/bin/uv run process_invoices.py >> /var/log/cron.log 2>&1
0 3 * * * cd /app/scripts/generate_reports && /root/.cargo/bin/uv run generate_reports.py >> /var/log/cron.log 2>&1

# Maintenance jobs
0 0 * * 0 cd /app/scripts/cleanup && /root/.cargo/bin/uv run cleanup.py >> /var/log/cron.log 2>&1

# UV tools (run directly, no uv command needed)
0 */6 * * * agentic_document_archiver >> /var/log/cron.log 2>&1
```

## License

[Add your license information here]

## Support

For issues and questions:

- Create an issue in the repository
- Check script-specific README files
- Review cron logs: `docker-compose exec app cat /var/log/cron.log`
