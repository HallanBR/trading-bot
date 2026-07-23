"""Criação do banco e gerenciamento transacional de sessões."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from trading_bot.persistence.models import Base


class Database:
    """Conexão SQLAlchemy explícita, sem estado global."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = create_engine(url, echo=echo)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @classmethod
    def from_path(cls, path: str | Path, *, echo: bool = False) -> "Database":
        """Cria um banco SQLite no caminho informado."""

        resolved = Path(path).expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return cls(f"sqlite:///{resolved.as_posix()}", echo=echo)

    def create_schema(self) -> None:
        """Cria tabelas ausentes sem apagar dados existentes."""

        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Confirma a transação ou executa rollback em qualquer erro."""

        database_session = self._session_factory()
        try:
            yield database_session
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise
        finally:
            database_session.close()

    def dispose(self) -> None:
        """Libera conexões mantidas pelo engine."""

        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(
        dbapi_connection: object,
        connection_record: object,
    ) -> None:
        del connection_record
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
