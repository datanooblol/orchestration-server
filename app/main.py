from package.utils import setup_logger
import logging
setup_logger(logging.DEBUG)

from fastapi import FastAPI, Depends, HTTPException, Header
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from package.flows.conversation_flow import ConvoFlow, ChatRequest
from package.services.api import API

app = FastAPI(title="Orchestration Service")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

def verify_and_extract_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    return credentials.credentials

@app.post("/chat")
async def chat(chat_data:ChatRequest, access_token:str = Depends(verify_and_extract_token)):
    """Chat endpoint"""
    api = API(access_token=access_token)
    flow = ConvoFlow(api=api)
    response = await flow.run(chat_data)
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Orchestration API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)