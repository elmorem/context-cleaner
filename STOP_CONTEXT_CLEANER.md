# Updated Shutdown Instructions

The legacy `stop-context-cleaner.sh` script performs a direct process kill and
may leave the supervisor/registry in an inconsistent state. The recommended
approach is:

```bash
context-cleaner stop --force --no-discovery
```

This command contacts the supervisor, streams shutdown progress, and only falls
back to discovery/kills when IPC is unavailable.

delete or archive the old shell script to avoid inadvertent use.
