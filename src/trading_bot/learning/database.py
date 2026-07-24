"""Banco SQLite isolado para os exemplos de operações perdedoras."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from trading_bot.learning.models import LearningBase


class LearningDatabase:
    """Conexão separada que cria apenas as tabelas de aprendizado."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine = create_engine(url, echo=echo)
        self._session_factory = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        echo: bool = False,
    ) -> "LearningDatabase":
        """Cria o arquivo SQLite e seus diretórios quando necessário."""

        resolved = Path(path).expanduser().resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return cls(f"sqlite:///{resolved.as_posix()}", echo=echo)

    def create_schema(self) -> None:
        """Cria somente as tabelas pertencentes ao aprendizado."""

        LearningBase.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Confirma a transação ou desfaz todas as mudanças em caso de erro."""

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
        """Libera as conexões mantidas pelo engine."""

        self.engine.dispose()
