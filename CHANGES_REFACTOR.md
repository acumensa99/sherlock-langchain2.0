# Refactoring & Improvements Changelog

This document summarizes the changes made to the Sherlock LangChain backend (`sherlock-langchain`) to improve performance, modularity, and stability.

## 1. Architectural Improvements

### Asynchronous Execution
- **Change**: Converted all synchronous LLM calls (`invoke`) to asynchronous calls (`await ainvoke`).
- **Impact**: The FastAPI server is now non-blocking, allowing it to handle concurrent requests without freezing the event loop.

### Modularization
- **Change**: Split the monolithic `main.py` (1100+ lines) into focused modules:
    - `main.py`: Core FastAPI routing and business logic.
    - `models_config.py`: LLM initialization, environment variable loading, and fallback logic.
    - `prompts.py`: Centralized storage for large prompt templates and SQL generation rules.
    - `utils.py`: Helper functions for database schema extraction and dataframe truncation.
- **Impact**: Improved code readability and maintainability.

## 2. LLM & Model Handling

### Robust Fallback System
- **Change**: Implemented a fallback mechanism for the Groq model.
- **Details**: If `GROQ_API_KEY` is missing or invalid, the system automatically falls back to the AWS Bedrock `llama3-8b-instruct` model.
- **Specifics**: `generate_title` and `autocomplete` features explicitly prefer the lightweight Llama 3 8B model for speed and cost efficiency.

### Intent Classification
- **Change**: Removed the redundant LLM-based intent classification step.
- **Details**: The backend now trusts the `miniAppType` provided by the frontend (e.g., "BBCHAMPS", "SEPHORA").
- **Impact**: Reduced latency and eliminated hallucinations (e.g., falsely classifying queries as "Instagram Analyzer").

## 3. Database & SQL Generation Improvements

### Row Level Security (RLS)
- **Fix**: Restored missing RLS context handling.
- **Details**: The backend now correctly sets the following Postgres session variables before executing queries:
    - `app.allowed_categories` (serialized as JSON)
    - `app.max_days`
    - `app.access_start_date`
    - `app.access_end_date`
- **Impact**: Fixed issue where users with specific permissions saw 0 results.

### SQL Robustness (BBCHAMPS)
- **Null Handling**: Added prompt rules to filter out rows with `NULL` prices or winning sellers by default, ensuring cleaner data tables.
- **Limit & Deduplication**: Enforced `LIMIT 50` and `DISTINCT`/`GROUP BY` usage to prevent excessively large or duplicate responses.
- **Postgres Compatibility**: Added specific instructions to avoid `SELECT DISTINCT` errors when `ORDER BY` columns are missing from the select list.

## 4. Bug Fixes & Code Quality

### Input Sanitization
- **Fix**: Added checks in `main.py` to catch and sanitize `[object Object]` strings in `seller_name` or `question`.

### Pandas Deprecations
- **Fix**: Updated code to resolve Pandas 2.0+ warnings:
    - Replaced `df.applymap` with `df.map`.
    - Fixed `FutureWarning` for `fillna` by casting to object type first (`df.astype(object).fillna("null")`).
    - Added `pd.set_option("future.no_silent_downcasting", True)` to suppress downcasting warnings.

### Minor UI/UX Fixes
- **Fix**: The `generate_title` endpoint now strips extraneous quotes (`""`) from the generated title string.