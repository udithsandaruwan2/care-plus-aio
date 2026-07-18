"""Enforce append-only AuditLog at the database level.

The app DB user owns the table, so REVOKE UPDATE/DELETE has no effect on the
owner. A BEFORE UPDATE OR DELETE trigger raises instead — same outcome for
HIPAA/PDPA immutability.
"""

from django.db import migrations

FORWARD = """
CREATE OR REPLACE FUNCTION accounts_auditlog_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'accounts_auditlog is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS accounts_auditlog_no_mutate ON accounts_auditlog;
CREATE TRIGGER accounts_auditlog_no_mutate
  BEFORE UPDATE OR DELETE ON accounts_auditlog
  FOR EACH ROW EXECUTE FUNCTION accounts_auditlog_immutable();
"""

REVERSE = """
DROP TRIGGER IF EXISTS accounts_auditlog_no_mutate ON accounts_auditlog;
DROP FUNCTION IF EXISTS accounts_auditlog_immutable();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_auditlog"),
    ]

    operations = [
        migrations.RunSQL(FORWARD, REVERSE),
    ]
