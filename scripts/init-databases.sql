-- Initialize multiple databases for AI Projects Workspace
-- This script is automatically run by PostgreSQL on first startup

-- Create biolinker database
CREATE DATABASE biolinker;
GRANT ALL PRIVILEGES ON DATABASE biolinker TO postgres;

-- Create agriguard database
CREATE DATABASE agriguard;
GRANT ALL PRIVILEGES ON DATABASE agriguard TO postgres;

-- Create database for future services
-- CREATE DATABASE dailynews;
-- GRANT ALL PRIVILEGES ON DATABASE dailynews TO postgres;

\c biolinker;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search optimization

\c agriguard;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Return to default database
\c postgres;
