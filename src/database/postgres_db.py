from contextlib import contextmanager
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from .Base import Base
from typing import Optional, Generator
from src.schemas.database.config import PostgreSQLSettings

logger = logging.getLogger(__name__)

class PostgreSQLDatabase:

    def __init__(self, config:PostgreSQLSettings):
        self.config = config

        self.engine: Optional[Engine] = None
        self.session_factory: Optional[sessionmaker] = None

    def startup(self) -> None:
        """Initialize database connection"""
        try:
            self.engine = create_engine(
                self.config.database_url,
                echo=self.config.echo_sql,
                pool_size=self.config.pool_size,
                max_overflow= self.config.max_overflow,
                pool_pre_ping=True,
            )

            self.session_factory = sessionmaker(
                bind=self.engine,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
            )
            
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
                
            inspector = inspect(self.engine)
            existing_tables = inspector.get_table_names()

            Base.metadata.create_all(bind=self.engine)

            new_inspector = inspect(self.engine)
            current_tables = new_inspector.get_table_names()

            new_tables = set(current_tables) - set(existing_tables)

            if new_tables:
                logger.info(f"New tables created: {', '.join(new_tables)}")
            else:
                logger.info("No new tables created")
            
            logger.info(f"Connected database: {self.engine.url.database}")
            logger.info(f"Total tables: {', '.join(current_tables) if current_tables else 'None'}")
            logger.info("Database connected succesfully")
            
        except Exception as e:
            logger.exception("Failed to connect to PostgreSQL database")
            raise

    def dispose(self) -> None:
        """
        Dispose created database connection
        """
        if self.engine:
            self.engine.dispose()
            logger.info("PostgreSQL database connection closed")

    @contextmanager
    def get_session(self)-> Generator[Session, None, None]:
        """Get database session"""
        
        if self.session_factory is None:
            raise RuntimeError("Database not initialized")

        session: Session = self.session_factory()

        try:
            yield session

        except Exception as e:
            session.rollback()
            logger.exception("Error occurred while getting session")
            raise

        finally:
            logger.info("Closing session")
            session.close()