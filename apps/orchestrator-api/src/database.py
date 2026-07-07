import os
import duckdb
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://admin:password@postgres-db:5432/research_db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Configure the async engine with a connection pool
engine = create_async_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Global DuckDB connection instance
_duckdb_conn = None

def init_duckdb() -> duckdb.DuckDBPyConnection:
    global _duckdb_conn
    if _duckdb_conn is None:
        db_dir = os.getenv("DUCKDB_DATA_DIR", "/shared/workspaces")
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "workspace.db")
        # Initialize the global connection in read/write mode
        _duckdb_conn = duckdb.connect(db_path, read_only=False)
    return _duckdb_conn

def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    global _duckdb_conn
    if _duckdb_conn is None:
        return init_duckdb()
    return _duckdb_conn

def close_duckdb():
    global _duckdb_conn
    if _duckdb_conn is not None:
        try:
            _duckdb_conn.close()
        except Exception:
            pass
        _duckdb_conn = None

async def get_pg_session():
    """Dependency generator for Postgres sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
