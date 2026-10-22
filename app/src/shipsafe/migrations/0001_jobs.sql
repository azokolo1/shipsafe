CREATE TABLE jobs (
    id          uuid        PRIMARY KEY,
    status      text        NOT NULL CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    payload     jsonb       NOT NULL,
    result      jsonb,
    error       text,
    attempts    integer     NOT NULL DEFAULT 0,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
