from src.config import get_settings
from src.database.postgres_db import PostgreSQLDatabase
from src.schemas.database.config import PostgreSQLSettings

def create_database() -> PostgreSQLDatabase:
    """Factory function to create a database instance."""
    
    settings = get_settings()

    config = PostgreSQLSettings(
        database_url=settings.postgres_database_url,
        echo_sql=settings.postgres_echo_sql,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
    )

    database = PostgreSQLDatabase(config=config)
    database.startup()
    return database
