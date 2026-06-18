from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from .Base import Base

class PostgreSQLDatabase:

    def __init__(
        self,
        database_url: str,
    ):
        self.database_url = database_url

        self.engine = None
        self.session_factory = None

    def startup(self) -> None:

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        
        Base.metadata.create_all(
            bind=self.engine
        )

    def teardown(self) -> None:

        if self.engine:
            self.engine.dispose()

    @contextmanager
    def get_session(self):

        if self.session_factory is None:
            raise RuntimeError(
                "Database not initialized"
            )

        session: Session = self.session_factory()

        try:
            yield session

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()