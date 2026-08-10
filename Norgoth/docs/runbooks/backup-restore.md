# Backup & Restore Runbook — NorBot

## Backups

```bash
/opt/norbot/scripts/backup-db.sh production
/opt/norbot/scripts/backup-db.sh test
```

- Format: `pg_dump -Fc`
- Path: `/opt/norbot/backups/postgres/<db>_<timestamp>.dump`
- Local retention: 14 days (script prune)
- Copy off-host (S3/B2/another VPS) outside this script

Production deploys take a pre-deploy backup automatically.

## Restore (emergency)

```bash
CONFIRM_RESTORE=norbot_prod /opt/norbot/scripts/restore-db.sh production /path/to/dump.dump
```

Requires explicit `CONFIRM_RESTORE=<exact-db-name>`.

After restore:

1. `migration-status.sh` / `migrate.sh` if needed
2. Recreate app containers on a known-good SHA
3. Smoke checks

## Notes

- Test DB is **not** a backup.
- Prefer expand/contract schema changes; image rollback ≠ schema rollback.
