-- The application's own login role. It has no password: in AWS it signs in with
-- IAM authentication (rds_iam), and it can only read, insert and update jobs.
-- No DELETE, no DDL: schema changes happen only in the migration task.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'shipsafe_app') THEN
        CREATE ROLE shipsafe_app LOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO shipsafe_app;
GRANT SELECT, INSERT, UPDATE ON jobs TO shipsafe_app;

-- rds_iam exists only on Amazon RDS; local and CI databases skip this.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rds_iam') THEN
        GRANT rds_iam TO shipsafe_app;
    END IF;
END
$$;
