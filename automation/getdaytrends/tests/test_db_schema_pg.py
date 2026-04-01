import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from getdaytrends.db_schema import get_connection, _PgAdapter, close_pg_pool

@pytest.mark.asyncio
async def test_get_connection_postgres_routing() -> None:
    """Test that get_connection correctly routes to PostgreSQL when DATABASE_URL is set."""
    # Ensure _PG_POOL is reset in case other tests ran
    import getdaytrends.db_schema as dbs
    dbs._PG_POOL = None

    with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost:5432/db"}),\
         patch("getdaytrends.db_schema._PG_AVAILABLE", True),\
         patch("getdaytrends.db_schema.asyncpg") as mock_asyncpg:
         
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=MagicMock())
        mock_pool._closed = False
        mock_asyncpg.create_pool = AsyncMock(return_value=mock_pool)
        
        # Act
        conn = await get_connection()
        
        # Assert
        mock_asyncpg.create_pool.assert_called_once_with(
            "postgresql://user:pass@localhost:5432/db", 
            min_size=2, 
            max_size=10
        )
        assert isinstance(conn, _PgAdapter)
        mock_pool.acquire.assert_called_once()
        
        # Cleanup
        await close_pg_pool()
