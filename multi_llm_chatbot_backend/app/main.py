# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Multi-LLM Chatbot Backend",
    version="0.2"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route definitions
app.include_router(router)

@app.get("/")
def root():
    return {
        "message": "Multi-LLM PhD Advisor Backend is up and running",
        "version": "0.2",
        "features": ["Ollama Support", "Gemini API Support", "Provider Switching"]
    }