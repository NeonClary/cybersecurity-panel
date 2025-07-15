from dotenv import load_dotenv
import os

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


app = FastAPI(
    title="Multi-LLM Chatbot Backend",
    version="1.0.0"  # Updated version
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def root():
    return {
        "message": "Multi-LLM PhD Advisor Backend is up and running",
        "version": "1.0.0",
        "features": [
            "Improved Session Management", 
            "Unified Context Handling",
            "Ollama Support", 
            "Gemini API Support", 
            "Provider Switching"
        ]
    }