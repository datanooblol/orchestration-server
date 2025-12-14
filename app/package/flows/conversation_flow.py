from package.services.api import API, Method
from pydantic import BaseModel
from typing import Any, List, Dict, Optional
import logging
from pathlib import Path
import json

class ChatRequest(BaseModel):
    project_id:str
    chat_session_id:str
    model_id:str = "nova-micro"
    content:str = ""
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

    async def get_last_convo(self, chat_session_id):
        response = await self.api.memory(f"conversation/chat-session/{chat_session_id}/latest", Method.GET)
        return response[0]

    async def get_reference_by_id(self, reference_id):
        response = await self.api.memory(f"reference/{reference_id}", Method.GET)
        return response

    async def delete_convo(self, convo_id):
        response = await self.api.memory(f"conversation/{convo_id}", Method.DELETE)
        return response

    async def get_convo(self, convo_id):
        response = await self.api.memory(f"conversation/{convo_id}", Method.GET)
        return response

    async def create_user_convo(self, chat_session_id, content):
        """
        - save user convo
        """
        params = {
            "endpoint": f"conversation/chat-session/{chat_session_id}",
            "method": Method.POST,
            "data": dict(content=content, role="user"),
        }
        response = await self.api.memory(**params)
        convo_id = response.get("convo_id", None)
        convo = await self.get_convo(convo_id)
        return convo

    async def patch_user_convo_content(self, convo_id, content):
        params = {
            "endpoint": f"conversation/{convo_id}",
            "method": Method.PUT,
            "data": dict(content=content, role="user"),
        }
        response = await self.api.memory(**params)
        convo = await self.get_convo(convo_id)
        return convo

    async def get_chat_history(self, chat_session_id:str):
        response = await self.api.memory(f"conversation/chat-session/{chat_session_id}", method=Method.GET)
        # chat
        if len(response)>1:
            _ = response.pop()
            chat_history = ["CHAT_HISTORY:\n"] + [f"{r['role'].upper()}:\n{r['content']}\n" for r in response]
            return "".join(chat_history)
        return ""

    async def answer(self, data, talk_to_data):
        endpoint = "agent/chat-with-data" if talk_to_data else "agent/chat"
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
        
    async def process_talk_to_data(self, project_id, content):
        files, metadata_context = await self.get_metadata_context(project_id)
        query = await self.api.agent("agent/sql-generator", Method.POST, data=dict(model_id="nova-micro", content=metadata_context+content))
        query = query.get("content", None)
        query_data = await self.api.memory("source/query", Method.POST, data=dict(files=files, query=query))
        data_markdown = query_data.get("markdown", None)
        data_str = query_data.get("data", None)
        self.logger.debug(f"QUERY DATA: \n{query_data}")
        return query, data_str, data_markdown

    async def visualize(self, convo_id, content, data, references):
        content = f"DATA:\n\n{data}\n\nCONTENT:\n\n{content}"
        data = dict(model_id="nova-micro", content=content)
        response = await self.api.agent("agent/plotly-data-generator", Method.POST, data=data)
        plotly_data = response.get("content", None)
        plotly_data_reference = await self.api.memory(f"reference/conversation/{convo_id}", Method.POST, data=dict(type="plotly_data", content=json.dumps(plotly_data)))
        reference_id = plotly_data_reference.get("reference_id", None)
        references = [r for r in references if r.get("type")!='plotly_data']
        references.append(plotly_data_reference)
        await self.api.memory(f"conversation/{convo_id}/references", Method.PATCH, data=dict(references=references))
        reference = await self.api.memory(f"reference/{reference_id}", Method.GET)
        return reference

    async def end_assistant_convo(self, chat_session_id, content, references:Optional[dict]=None):
        params = {
            "endpoint": f"conversation/chat-session/{chat_session_id}",
            "method": Method.POST,
            "data": dict(content=content, role="assistant", references=None),
        }
        convo_id = await self.api.memory(**params)
        convo_id = convo_id['convo_id']
        if references:
            sql_code_reference = await self.api.memory(f"reference/conversation/{convo_id}", Method.POST, data=dict(type="sql_code", content=references['sql_code']))
            self.logger.debug(f"SQL CODE: {sql_code_reference}")
            sql_data_reference = await self.api.memory(f"reference/conversation/{convo_id}", Method.POST, data=dict(type="sql_data", content=references['sql_data']))
            self.logger.debug(f"SQL DATA: {sql_data_reference}")
            reference_data = [
                sql_code_reference, 
                sql_data_reference
            ]
            await self.api.memory(f"conversation/{convo_id}/references", Method.PATCH, data=dict(references=reference_data))
        response = await self.api.memory(f"conversation/{convo_id}", Method.GET)
        return response

    async def run(self, project_id, model_id, content, chat_history, talk_to_data:bool):
        query_result = ""
        references = None
        self.logger.debug(chat_history)
        if talk_to_data:
            query, data_str, data_markdown = await self.process_talk_to_data(project_id=project_id, content=content)
            references = dict(sql_code=query, sql_data=data_str)
            self.logger.debug(f"References: {references}")
            query_result = f"DATA:\n{data_markdown}\n"
        data = dict(model_id=model_id, content=chat_history+query_result+content)
        self.logger.debug(data)
        response = await self.answer(data, talk_to_data)
        return response, references

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