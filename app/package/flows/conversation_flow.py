from package.services.api import API, Method
from pydantic import BaseModel
from typing import Any, List, Dict, Optional
import logging

class ChatRequest(BaseModel):
    project_id:str
    chat_session_id:str
    model_id:str
    content:str
    talk_to_data:bool = False

class ChatResponse(BaseModel):
    model_id:str
    role:str = "assistant"
    content:str
    references:Optional[List[Dict[str, Any]]] = None

class ConvoFlow:
    def __init__(self, api:API):
        self.api = api
        self.logger = logging.getLogger("Conversation Flow")

    async def start_user_convo(self, chat_session_id, content):
        """
        - save user convo
        """
        params = {
            "endpoint": f"conversation/chat-session/{chat_session_id}",
            "method": Method.POST,
            "data": dict(content=content, role="user"),
        }
        response = await self.api.memory(**params)
        return response

    async def get_chat_history(self, chat_session_id:str):
        response = await self.api.memory(f"conversation/chat-session/{chat_session_id}", method=Method.GET)
        if len(response)>1:
            _ = response.pop()
            chat_history = ["CHAT_HISTORY:\n"] + [f"{r['role'].upper()}:\n{r['content']}\n" for r in response]
            return "".join(chat_history)
        return ""

    async def answer(self, data, talk_to_data):
        endpoint = "/agent/chat-with-data" if talk_to_data else "/agent/chat"
        response = await self.api.agent(endpoint, Method.POST, data=data)
        return response

    async def process_chat_with_data(self):
        ...

    async def end_assistant_convo(self, chat_session_id, content, references):
        params = {
            "endpoint": f"conversation/chat-session/{chat_session_id}",
            "method": Method.POST,
            "data": dict(content=content, role="assistant", references=references),
        }
        convo_id = await self.api.memory(**params)
        convo_id = convo_id['convo_id']
        response = await self.api.memory(f"conversation/{convo_id}", Method.GET)
        return response

    async def run(self, convo:ChatRequest):
        chat_session_id = convo.chat_session_id
        user_convo_id = await self.start_user_convo(chat_session_id=chat_session_id, content=convo.content)
        chat_history = await self.get_chat_history(chat_session_id=chat_session_id)
        self.logger.debug(chat_history)
        if convo.talk_to_data:
            context = await self.process_chat_with_data()
        data = dict(model_id=convo.model_id, content=chat_history+convo.content)
        response = await self.answer(data, convo.talk_to_data)
        ai_convo = await self.end_assistant_convo(chat_session_id, response['content'], None)
        return ai_convo
    