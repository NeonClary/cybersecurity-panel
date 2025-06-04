from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Multi-LLM Chatbot Backend",
    version="0.1"
)

# Include route definitions
app.include_router(router)

@app.get("/")
def root():
    return {"message": "Backend is up and running"}