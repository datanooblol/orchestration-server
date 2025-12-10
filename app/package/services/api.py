import httpx
from enum import StrEnum
from typing import Any
from pydantic import BaseModel

class Method(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

class AgentRequest(BaseModel):
    model_id:str
    user_input:str

class API:
    _memory_server = "http://memory:8001"
    _agent_server = "http://agent:8002"

    @staticmethod
    def memory(endpoint:str, method:Method, content:Any):
        base_url = API._memory_server
        url = base_url + endpoint

    @staticmethod
    def agent(agent_name:str, method:Method, json_data:AgentRequest):
        base_url = API._agent_server
        url = f"{base_url}/agent/{agent_name}"
        
        with httpx.Client() as client:
            response = client.request(method, url=url, json=json_data.model_dump())
            return response
