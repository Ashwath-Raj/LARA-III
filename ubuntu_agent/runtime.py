"""Persistent global pause and emergency-stop controls."""

from .database import Database
from .models import Actor, utc_now
from .services import PolicyDeniedError
from .bootstrap import PRINCIPAL_ID


class RuntimeControlService:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _check(actor: Actor) -> None:
        if not isinstance(actor, Actor) or actor.principal_id != PRINCIPAL_ID:
            raise PolicyDeniedError("Local user identity is required.")

    def state(self) -> dict:
        with self.database.connect() as connection:
            return dict(connection.execute("SELECT * FROM runtime_controls WHERE singleton=1").fetchone())

    def pause(self, actor: Actor) -> dict:
        return self._set(actor, paused=1)

    def resume(self, actor: Actor) -> dict:
        self._check(actor)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT killed FROM runtime_controls WHERE singleton=1").fetchone()
            if row["killed"]:
                raise PolicyDeniedError("Emergency stop requires the local recovery command.")
            connection.execute("UPDATE runtime_controls SET paused=0,updated_at=?,updated_by=? WHERE singleton=1",
                               (utc_now(), actor.principal_id))
            return dict(connection.execute("SELECT * FROM runtime_controls WHERE singleton=1").fetchone())

    def kill(self, actor: Actor) -> dict:
        return self._set(actor, paused=1, killed=1)

    def recover(self, actor: Actor) -> dict:
        self._check(actor)
        return self._set(actor, paused=0, killed=0)

    def _set(self, actor: Actor, *, paused: int, killed: int | None = None) -> dict:
        self._check(actor)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if killed is None:
                connection.execute("UPDATE runtime_controls SET paused=?,updated_at=?,updated_by=? WHERE singleton=1",
                                   (paused, utc_now(), actor.principal_id))
            else:
                connection.execute("UPDATE runtime_controls SET paused=?,killed=?,updated_at=?,updated_by=? WHERE singleton=1",
                                   (paused, killed, utc_now(), actor.principal_id))
            return dict(connection.execute("SELECT * FROM runtime_controls WHERE singleton=1").fetchone())

