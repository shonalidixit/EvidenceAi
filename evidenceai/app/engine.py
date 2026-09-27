"""Deterministic, read-only analysis plans for uploaded tabular data."""
import hashlib
import re
from dataclasses import dataclass

import duckdb
import pandas as pd

MAX_ROWS = 250_000


@dataclass
class Dataset:
    frame: pd.DataFrame
    digest: str
    filename: str


def load_csv(data: bytes, filename: str) -> Dataset:
    if not data or len(data) > 20 * 1024 * 1024:
        raise ValueError("Upload a nonempty CSV smaller than 20 MB.")
    try:
        from io import BytesIO
        frame = pd.read_csv(BytesIO(data), nrows=MAX_ROWS + 1, low_memory=False)
    except Exception as exc:
        raise ValueError("Could not read this CSV. Check its encoding and header row.") from exc
    if frame.empty or len(frame) > MAX_ROWS or not len(frame.columns):
        raise ValueError("CSV must contain 1 to 250,000 data rows.")
    frame.columns = [str(c).strip() for c in frame.columns]
    if not all(frame.columns) or frame.columns.duplicated().any():
        raise ValueError("Column names must be nonempty and unique.")
    return Dataset(frame, hashlib.sha256(data).hexdigest(), filename)


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def choose(question: str, columns: list[str], numeric: list[str]):
    q = question.lower()
    def score(col):
        tokens = re.findall(r'[a-z0-9]+', col.lower())
        return max([len(t) for t in tokens if len(t) > 2 and re.search(r'\b' + re.escape(t) + r'\b', q)] or [0])
    n = sorted(numeric, key=lambda c: score(c), reverse=True)
    measure = n[0] if n and score(n[0]) else (n[0] if n else None)
    categories = [c for c in columns if c not in numeric and not re.search(r'(^id$|_id$|uuid|email)', c, re.I)]
    categories.sort(key=lambda c: score(c), reverse=True)
    group = categories[0] if categories and score(categories[0]) else (categories[0] if categories else None)
    operation = 'avg' if re.search(r'\b(avg|average|mean)\b', q) else 'sum' if re.search(r'\b(sum|total|revenue|sales)\b', q) else 'count'
    if operation in ('avg', 'sum') and not measure:
        operation = 'count'
    return operation, measure, group


def analyze(dataset: Dataset, question: str) -> dict:
    question = question.strip()
    if not question or len(question) > 500:
        raise ValueError("Enter a question of up to 500 characters.")
    frame = dataset.frame
    numeric = [c for c in frame if pd.api.types.is_numeric_dtype(frame[c]) and not pd.api.types.is_bool_dtype(frame[c])]
    operation, measure, group = choose(question, list(frame.columns), numeric)
    expression = 'COUNT(*)' if operation == 'count' else f'{operation.upper()}({quote(measure)})'
    alias = {'count': 'row_count', 'sum': 'total', 'avg': 'average'}[operation]
    if group:
        sql = (f'SELECT {quote(group)} AS category, {expression} AS {alias}, COUNT(*) AS rows_used '
               f'FROM uploaded_data WHERE {quote(group)} IS NOT NULL '
               f'GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 12')
    else:
        sql = f'SELECT {expression} AS {alias}, COUNT(*) AS rows_used FROM uploaded_data'
    con = duckdb.connect(':memory:')
    try:
        con.register('uploaded_data', frame)
        result = con.execute(sql).df()
    finally:
        con.close()
    result = result.astype(object).where(pd.notna(result), None)
    records = result.to_dict(orient='records')
    if group and records:
        top = records[0]
        statement = f'{top["category"]} has the highest {alias.replace("_", " ")} among the displayed {group} groups: {format_value(top[alias])}.'
    elif records:
        statement = f'The {alias.replace("_", " ")} is {format_value(records[0][alias])} across {len(frame):,} rows.'
    else:
        statement = f'No nonmissing {group} values were available to compare.'
    caveats = []
    if group and frame[group].isna().any():
        caveats.append(f'{int(frame[group].isna().sum()):,} rows with missing {group} were excluded.')
    if group and frame[group].nunique(dropna=True) > 12:
        caveats.append('Only the top 12 groups are displayed.')
    if measure and frame[measure].isna().any() and operation != 'count':
        caveats.append(f'{int(frame[measure].isna().sum()):,} missing {measure} values were ignored by {operation.upper()}.')
    caveats.append('This is a descriptive comparison; it does not establish a cause or a statistically significant difference.')
    return {
        'question': question, 'statement': statement, 'sql': sql, 'rows': records,
        'metric': alias, 'group': group, 'measure': measure if operation != 'count' else None,
        'caveats': caveats, 'dataset_sha256': dataset.digest, 'row_count': len(frame),
        'method': 'Deterministic DuckDB aggregation; no model-generated SQL or code is executed.'
    }


def format_value(value):
    if value is None:
        return 'no value'
    return f'{float(value):,.2f}' if isinstance(value, float) else f'{value:,}' if isinstance(value, int) else str(value)
