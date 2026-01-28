import pandas as pd
from sqlalchemy import inspect, text


def truncate_dataframe(df: pd.DataFrame, token_limit: int = 5000) -> pd.DataFrame:
    """
    Truncates a pandas DataFrame to fit within a rough token limit.
    This is an approximation where 1 character ~= 0.25 tokens (or 4 chars per token).
    """
    if df is None or df.empty:
        return df

    # Deep copy to avoid modifying original
    df_copy = df.copy()

    # Estimate tokens: 1 token ~= 4 characters
    char_limit = token_limit * 4

    # Convert to string to estimate size
    current_chars = len(df_copy.to_string())

    if current_chars <= char_limit:
        return df_copy

    # If too large, reduce rows until it fits
    while current_chars > char_limit and not df_copy.empty:
        # Reduce by 10% or at least 1 row
        rows_to_drop = max(1, int(len(df_copy) * 0.1))
        df_copy = df_copy.iloc[:-rows_to_drop]
        current_chars = len(df_copy.to_string())

    return df_copy


def get_db_schema_summary(engine, target_tables=None):
    """
    Generates a concise summary of the database schema.
    If target_tables is provided, only includes those tables.
    """
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    if target_tables:
        # Filter tables that exist in the DB
        tables_to_inspect = [t for t in target_tables if t in all_tables]
    else:
        tables_to_inspect = all_tables

    schema_summary = []

    for table_name in tables_to_inspect:
        columns = inspector.get_columns(table_name)
        col_strings = [f"{col['name']} ({str(col['type'])})" for col in columns]

        # Get PKs
        pks = inspector.get_pk_constraint(table_name).get("constrained_columns", [])

        # Format table info
        table_str = f"Table: {table_name}\nColumns: {', '.join(col_strings)}"
        if pks:
            table_str += f"\nPrimary Keys: {', '.join(pks)}"

        schema_summary.append(table_str)

    return "\n\n".join(schema_summary)


def get_sample_data(engine, limit=3):
    """
    Fetches a small sample of data from all tables to help the LLM understand content.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    sample_data = []

    with engine.connect() as conn:
        for table in tables:
            try:
                # Use text() for safe execution
                # Note: table names from inspector are generally safe, but quoting is good practice if complex
                query = text(f'SELECT * FROM "{table}" LIMIT {limit}')
                df = pd.read_sql(query, conn)

                if not df.empty:
                    # Format as markdown table for readability
                    table_md = f"Table: {table}\n{df.to_markdown(index=False)}"
                    sample_data.append(table_md)
            except Exception as e:
                # Ignore errors for specific tables (e.g. permission issues or no select access)
                continue

    return "\n\n".join(sample_data)
