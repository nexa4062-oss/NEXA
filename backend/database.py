import os
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from config import get_settings
import structlog

settings = get_settings()
logger = structlog.get_logger()

_db_url = settings.DATABASE_URL
_is_sqlite = False

if settings.USE_SQLITE:
    os.makedirs("./data", exist_ok=True)
    _db_url = "sqlite+aiosqlite:///./data/sovereign_ai.db"
    _is_sqlite = True
    logger.info("Using SQLite database", path="./data/sovereign_ai.db")

engine = create_async_engine(
    _db_url,
    echo=settings.DATABASE_ECHO,
    **({} if "sqlite" in _db_url else {"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True}),
)

# SQLite only ever allows one writer at a time. WAL mode + a generous
# busy_timeout mean ordinary requests just wait briefly instead of
# failing outright if a background task's write is in flight. The
# asyncio.Lock below additionally serializes the document-indexing
# background task against itself (get_db_context, further down) so two
# indexing jobs started close together can't race each other's commits -
# it does NOT wrap normal request handling (get_db), since that could
# stall the whole app behind one slow request. This is a no-op for
# Postgres deployments.
_sqlite_write_lock = asyncio.Lock() if _is_sqlite else None

if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    # NOTE: deliberately does NOT take _sqlite_write_lock. This runs for
    # every request (including simple reads like login), so holding a
    # process-wide lock for its whole duration would let a single slow
    # request (e.g. one that kicks off heavy processing) stall every other
    # endpoint in the app - that's worse than the "database is locked"
    # error it would be trying to prevent. WAL + busy_timeout (set on
    # connect, above) is what actually protects ordinary requests from
    # colliding with background-task writes.
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context():
    """For code that isn't a FastAPI route and can't use Depends()
    (currently just the document-indexing BackgroundTask). Serializes
    against other callers of get_db_context() specifically, so two
    background jobs can't race each other's writes. Ordinary requests
    via get_db() are intentionally NOT blocked by this lock - see the
    note on get_db() above."""
    if _sqlite_write_lock is not None:
        async with _sqlite_write_lock:
            async with AsyncSessionLocal() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
                finally:
                    await session.close()
    else:
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    await engine.dispose()
