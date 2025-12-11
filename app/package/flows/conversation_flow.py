from package.services.api import API, Method
from pydantic import BaseModel
from typing import Any, List, Dict, Optional
import logging
from pathlib import Path

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

    async def get_metadata_context(self, project_id):
        selected_sources = await self.api.memory(f"source/project/{project_id}/selected", Method.GET)
        source_ids = [ss['source_id'] for ss in selected_sources]
        files = [ss['source_path']['stored_path'] for ss in selected_sources]
        metadata_context = []
        for source_id in source_ids:
            metadata = await self.api.memory(f"metadata/source/{source_id}", Method.GET)
            metadata_context.append(extract_metadata(metadata))
        return files, "\n".join(["METADATAS:"]+metadata_context+[""])
        

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
        project_id = convo.project_id
        chat_session_id = convo.chat_session_id
        query_result = ""
        user_convo_id = await self.start_user_convo(chat_session_id=chat_session_id, content=convo.content)
        chat_history = await self.get_chat_history(chat_session_id=chat_session_id)
        self.logger.debug(chat_history)
        if convo.talk_to_data:
            files, metadata_context = await self.get_metadata_context(project_id)
            query = await self.api.agent("/agent/sql-generator", Method.POST, data=dict(model_id="nova-micro", content=metadata_context+convo.content))
            query = query.get("content", None)
            query_result = await self.api.memory("source/query", Method.POST, data=dict(files=files, query=query))
            query_result = f"DATA:\n{query_result}\n"
        data = dict(model_id=convo.model_id, content=chat_history+query_result+convo.content)
        self.logger.debug(data)
        response = await self.answer(data, convo.talk_to_data)
        ai_convo = await self.end_assistant_convo(chat_session_id, response['content'], None)
        return ai_convo
    
def extract_metadata(metadata_dict:dict):
    metadata = metadata_dict.get("metadata", {})
    table_name = metadata.get("table_name", None)
    table_name = Path(table_name).stem
    description = metadata.get("description", None)
    _fields = metadata_dict.get("fields", [])
    fields = []
    for f in _fields:
        input_type = f.get("input_type", None)
        if (input_type is None) or (input_type=='reject'):
            continue
        field_name = f.get("field_name", None)
        data_type = f.get("data_type", None)
        description = f.get("description", None)
        # Build field string only with non-empty values
        field_str = field_name or ""
        if data_type:
            field_str += f" ({data_type})"
        if description:
            field_str += f" : {description}"

        if field_str.strip():  # Only add if not empty
            fields.append(field_str.strip())        
    prompt = [f"TABLE NAME: {table_name}"]
    if description:
        prompt.append(f"DESCRIPTION: {description}")
    prompt.append("FIELDS:")
    prompt.extend([f"- {f}" for f in fields])
    return "\n".join(prompt)