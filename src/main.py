from fastapi import FastAPI

app = FastAPI(title = "Academic Paper Assistant API", version = "1.0")

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}