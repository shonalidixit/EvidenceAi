from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_upload_analyze_verify():
    data = b'region,revenue\nNorth,20\nSouth,10\nNorth,30\n'
    upload = client.post('/api/upload', files={'file': ('sample.csv', BytesIO(data), 'text/csv')})
    assert upload.status_code == 200
    dataset_id = upload.json()['dataset_id']
    answer = client.post('/api/analyze', json={'dataset_id': dataset_id, 'question': 'total revenue by region'})
    assert answer.status_code == 200
    result = answer.json()
    assert result['rows'][0]['category'] == 'North'
    assert result['rows'][0]['total'] == 50
    verified = client.post('/api/verify', json={'dataset_id': dataset_id, 'question': result['question'], 'expected_sha256': result['dataset_sha256'], 'expected_sql': result['sql'], 'expected_rows': result['rows']})
    assert verified.json()['verified'] is True
    changed = client.post('/api/verify', json={'dataset_id': dataset_id, 'question': result['question'], 'expected_sha256': 'incorrect', 'expected_sql': result['sql'], 'expected_rows': result['rows']})
    assert changed.json()['verified'] is False

def test_reject_bad_csv_and_missing_question():
    assert client.post('/api/upload', files={'file': ('bad.txt', b'abc')}).status_code == 400
    uploaded = client.post('/api/upload', files={'file': ('data.csv', b'x\n1\n')}).json()
    assert client.post('/api/analyze', json={'dataset_id': uploaded['dataset_id'], 'question': ''}).status_code == 400
