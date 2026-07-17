# ew-notify

Shared **ntfy + macOS** alerts for the **paper trading** stack (`ew-paper-trading`).

| Topic (default) | Purpose |
|-----------------|---------|
| `ew-paper-sk-alerts` | Mac → iPhone (status, trades, coach) |
| `ew-sk-paper-cmd` | iPhone → Mac (`status` / `start` / `stop`) |

## Install

```bash
~/Projects/ew-paper-trading/.venv/bin/pip install -e ~/Projects/ew-notify
```

## iPhone

Subscribe in the ntfy app to:

- `ew-paper-sk-alerts`
- `ew-sk-paper-cmd`

## API

```python
from ew_notify import configure
from ew_notify.push import notify_alert, notify_info, notify_both
from ew_notify.alerts import build_trade_entry_alert
from ew_notify.status import build_status_message

configure(project_root, profile="paper")
```

The paper repo keeps thin `scripts/notify.py` / `scripts/system_status.py` shims that call `configure(...)`.
