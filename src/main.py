from fastapi import FastAPI
from src.router.user import user_router

app = FastAPI(title = "Academic Paper Assistant API", version = "1.0")

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

app.include_router(user_router)