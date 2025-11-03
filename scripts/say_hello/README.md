# Say Hello Script

A simple example script that demonstrates the Every Now & Then autonomous script runner.

## Description

This script prints a greeting message with a timestamp. It demonstrates:

- Reading environment variables
- Using different languages for greetings
- Proper logging with timestamps
- Exit codes for success/failure

## Environment Variables

| Variable            | Description                | Default | Required |
| ------------------- | -------------------------- | ------- | -------- |
| `GREETING_NAME`     | Name to greet              | `World` | No       |
| `GREETING_LANGUAGE` | Language code for greeting | `en`    | No       |

### Supported Languages

- `en` - English (Hello)
- `pt` - Portuguese (Olá)
- `es` - Spanish (Hola)
- `fr` - French (Bonjour)
- `de` - German (Hallo)

## Usage

### Manual Execution

```bash
# Navigate to script directory
cd scripts/say_hello

# Run with UV
uv run say_hello.py

# With environment variables
GREETING_NAME="John" GREETING_LANGUAGE="pt" uv run say_hello.py
```

### Docker Execution

```bash
# Run inside container
docker-compose exec app sh -c "cd /app/scripts/say_hello && uv run say_hello.py"
```

### Scheduled Execution (Cron)

Add to the `crontab` file in the project root:

```bash
# Every day at 9 AM
0 9 * * * cd /app/scripts/say_hello && /root/.cargo/bin/uv run say_hello.py >> /var/log/cron.log 2>&1
```

## Example Output

```
[2025-10-31 10:30:45] Hello, World!
[2025-10-31 10:30:45] Script executed successfully from Every Now & Then
[2025-10-31 10:30:45] Running from: /app/scripts/say_hello
```

With Portuguese greeting:

```
[2025-10-31 10:30:45] Olá, João!
[2025-10-31 10:30:45] Script executed successfully from Every Now & Then
[2025-10-31 10:30:45] Running from: /app/scripts/say_hello
```

## Dependencies

None - uses only Python standard library.

## Exit Codes

- `0` - Success
- Non-zero - Error occurred
