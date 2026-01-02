## FastAPI app

### Install

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

### Run

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Endpoints

- `GET /` -> `{ "message": "ok" }`
- `GET /health` -> `{ "status": "healthy" }`


