import httpx
from enum import StrEnum
from typing import Any

class Method(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"

class API:
    """
    Note:
        calling api:
            - memory: access_token
            - agent: no access_token
    """
    _memory_server = "http://memory:8001"
    _agent_server = "http://agent:8002"
    _time_out = httpx.Timeout(20.0, read=60.0) # connect, read
    def __init__(self, access_token:str):
        self.access_token = access_token

    def pack_params(self, url:str, method:Method, content:Any)->dict:
        params = dict(url=url, method=method)
        if method != Method.GET:
            params.update(dict(json=content))
        return params

    async def memory(self, endpoint:str, method:Method, data:Any=None):
        base_url = API._memory_server
        url = f"{base_url}/{endpoint}"
        params = self.pack_params(url, method, data)
        params.update(dict(headers={"Authorization": f"Bearer {self.access_token}"}))
        async with httpx.AsyncClient(timeout=self._time_out) as client:
            response = await client.request(**params)
            return response.json()

    async def agent(self, endpoint, method:Method, data:Any):
        base_url = API._agent_server
        url = f"{base_url}{endpoint}" 
        params = self.pack_params(url, method, data)
        async with httpx.AsyncClient(timeout=self._time_out) as client:
            response = await client.request(**params)
            return response.json()
