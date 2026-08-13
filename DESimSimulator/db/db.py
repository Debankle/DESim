from typing import Any

import psycopg


class DBService:
    def __init__(self, host, dbname, port, user, password):
        self.host = host
        self.dbname = dbname
        self.port = port
        self.user = user
        self.password = password

        self.uri = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

        self._setup_table()

    def _setup_table(self):
        # Can't init RDB in AWS CDK/CloudFormation so just going to use this as default setup each time even if its redundant
        with psycopg.connect(self.uri) as conn, conn.cursor() as cur:
            cur.execute(
                """
                do $$
                begin
                    if not exists ( select 1 from pg_type where typname = 'simulation_status') then
                        create type simulation_status as enum ('queued', 'running', 'complete', 'failed');
                    end if;
                end$$;
                """
            )

            cur.execute(
                """
                create table if not exists simulations (
                    simulation_id uuid primary key default gen_random_uuid(),
                    username varchar not null,
                    equation varchar(50) not null,
                    theta real not null,
                    params jsonb not null,
                    status simulation_status not null,
                    submit_time timestamp not null,
                    complete_time timestamp,
                    private boolean not null,
                    message text,
                    email_sent boolean default false
                )
                """
            )

            conn.commit()

    def execute(self, query, params: tuple = ()) -> None:
        with psycopg.connect(self.uri) as conn:
            conn.execute(query, params)
            conn.commit()

    def fetchone(self, query, params: tuple = ()) -> dict[str, Any] | None:
        with psycopg.connect(self.uri) as conn:
            cur = conn.execute(query, params)
            if not cur.description:
                return None
            columns = [d.name for d in cur.description]
            row = cur.fetchone()
            conn.commit()
            return dict(zip(columns, row)) if row else None

    def fetchall(self, query, params: tuple = ()) -> list[dict[str, Any]]:
        with psycopg.connect(self.uri) as conn:
            cur = conn.execute(query, params)
            if not cur.description:
                return []
            columns = [d.name for d in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            conn.commit()
            return rows
