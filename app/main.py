from package.utils import setup_logger
import logging
setup_logger(logging.DEBUG)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Orchestration Service")

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# for r in [
#     llm_router,
#     agent_router,
#     intent_router,
# ]:
#     app.include_router(r)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Orchestration API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)