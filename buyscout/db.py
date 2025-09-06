from peewee import PostgresqlDatabase
import os
from urllib.parse import urlparse

# Example: postgresql://user:password@localhost:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise Exception("DATABASE_URL is not set in environment variables")

parsed = urlparse(DATABASE_URL)

db = PostgresqlDatabase(
    parsed.path[1:],  # skip the leading '/'
    user=parsed.username,
    password=parsed.password,
    host=parsed.hostname,
    port=parsed.port
)
