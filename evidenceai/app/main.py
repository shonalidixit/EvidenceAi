import secrets
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .engine import Dataset, analyze, load_csv

app = FastAPI(title='EvidenceAI', version='1.0.0')
DATASETS: dict[str, Dataset] = {}
LOCK = Lock()
MAX_DATASETS = 20
STATIC = Path(__file__).parent / 'static'

class Question(BaseModel):
    dataset_id: str
    question: str

class Verify(Question):
    expected_sha256: str
    expected_sql: str
    expected_rows: list[dict]

@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')

@app.get('/static/{filename}')
def static(filename: str):
    if filename not in ('app.js', 'style.css'):
        raise HTTPException(404)
    return FileResponse(STATIC / filename)

@app.post('/api/upload')
async def upload(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(400, 'Please upload a CSV file.')
    data = await file.read(20 * 1024 * 1024 + 1)
    try:
        ds = load_csv(data, file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    token = secrets.token_urlsafe(24)
    with LOCK:
        if len(DATASETS) >= MAX_DATASETS:
            DATASETS.pop(next(iter(DATASETS)))
        DATASETS[token] = ds
    return {'dataset_id': token, 'filename': ds.filename, 'rows': len(ds.frame),
            'columns': [{'name': c, 'dtype': str(ds.frame[c].dtype), 'missing': int(ds.frame[c].isna().sum())} for c in ds.frame],
            'sha256': ds.digest, 'preview': ds.frame.head(5).fillna('').astype(str).to_dict(orient='records')}

def get_dataset(dataset_id: str):
    with LOCK:
        ds = DATASETS.get(dataset_id)
    if ds is None:
        raise HTTPException(404, 'Dataset expired. Upload it again.')
    return ds

@app.post('/api/analyze')
def run(request: Question):
    try:
        return analyze(get_dataset(request.dataset_id), request.question)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@app.post('/api/verify')
def verify(request: Verify):
    result = run(request)
    matches = (result['dataset_sha256'] == request.expected_sha256 and
               result['sql'] == request.expected_sql and result['rows'] == request.expected_rows)
    return {'verified': matches, 'result': result}
