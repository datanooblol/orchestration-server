from package.utils import setup_logger
import logging
setup_logger(logging.DEBUG)

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from package.flows.conversation_flow import ConvoFlow, ChatRequest
from package.services.api import API
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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


class Reference(BaseModel):
    reference_id: str
    type: str

class ConversationResponse(BaseModel):
    created_at: datetime
    updated_at: datetime
    convo_id: str
    chat_session_id: str
    role: str
    content: str
    references: Optional[List[Reference]] = None

@app.post("/chat", response_model=ConversationResponse)
async def chat(
    chat_data:ChatRequest, 
    access_token:str = Depends(verify_and_extract_token)
):
    api = API(access_token=access_token)
    flow = ConvoFlow(api=api)
    convo = await flow.create_user_convo(chat_data.chat_session_id, chat_data.content)
    content = convo.get("content", None)
    chat_history = await flow.get_chat_history(chat_data.chat_session_id)
    response, references = await flow.run(chat_data.project_id, chat_data.model_id, content, chat_history, chat_data.talk_to_data)
    ai_convo = await flow.end_assistant_convo(chat_data.chat_session_id, response['content'], references)
    return ai_convo

@app.patch("/chat/{convo_id}", response_model=ConversationResponse)
async def edit_user_last_message_and_regenerate_response(
    convo_id:str,
    chat_data:ChatRequest, 
    access_token:str = Depends(verify_and_extract_token)
):
    api = API(access_token=access_token)
    flow = ConvoFlow(api=api)
    convo = await flow.patch_user_convo_content(convo_id, chat_data.content)
    last_convo = await flow.get_last_convo(chat_data.chat_session_id)
    if last_convo is not None and last_convo.get("role")=='assistant':
        await flow.delete_convo(last_convo['convo_id'])
    content = convo.get("content", None)
    chat_history = await flow.get_chat_history(chat_data.chat_session_id)
    response, references = await flow.run(chat_data.project_id, chat_data.model_id, content, chat_history, chat_data.talk_to_data)
    ai_convo = await flow.end_assistant_convo(chat_data.chat_session_id, response['content'], references)
    return ai_convo

@app.post("/regenerate", response_model=ConversationResponse)
async def regenerate_response(
    chat_data:ChatRequest,
    access_token:str = Depends(verify_and_extract_token)
):
    """
    - delete last ai message
    - get last user content
    - get history
    """
    api = API(access_token=access_token)
    flow = ConvoFlow(api=api)
    last_convo = await flow.get_last_convo(chat_data.chat_session_id)
    if last_convo is not None and last_convo.get("role")=='assistant':
        await flow.delete_convo(last_convo['convo_id'])
    user_convo = await flow.get_last_convo(chat_data.chat_session_id)
    content = user_convo.get("content", None)
    chat_history = await flow.get_chat_history(chat_data.chat_session_id)
    response, references = await flow.run(chat_data.project_id, chat_data.model_id, content, chat_history, chat_data.talk_to_data)
    ai_convo = await flow.end_assistant_convo(chat_data.chat_session_id, response['content'], references)
    return ai_convo

@app.post("/visualize/{convo_id}")
async def visualize(
    access_token:str = Depends(verify_and_extract_token)
):
    pass

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Orchestration API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)