-- Anonymous install counter table.
-- RLS is enabled with no policies, so the anon key cannot read or write
-- directly. Only the Edge Function (using the service_role key) can insert.

CREATE TABLE installs (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  installed_at   timestamptz NOT NULL DEFAULT now(),
  python_version text NOT NULL,
  platform       text NOT NULL
);

ALTER TABLE installs ENABLE ROW LEVEL SECURITY;
