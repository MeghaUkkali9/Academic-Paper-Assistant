from pydantic_settings import BaseSettings
from pydantic import Field

class PostgreSQLSettings(BaseSettings):
    database_url: str = Field(default = "postgresql+psycopg2://neondb_owner:npg_Ori1UY3LaFmE@ep-sweet-cloud-aiuz4z54-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require")
    echo_sql: bool = Field(default = False)
    pool_size:int = Field(default = 5)
    max_overflow:int = Field(default = 0)
    
    