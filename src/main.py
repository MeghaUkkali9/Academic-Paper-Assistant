from fastapi import FastAPI
from src.router.user import user_router
from src.router.ask import stream_router

app = FastAPI(title = "Academic Paper Assistant API", version = "1.0")

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

app.include_router(user_router)
app.include_router(stream_router, prefix="/api/v1") 