# pyrefly: ignore [missing-import]
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import chat, upload, recommend, audit

app = FastAPI(title="DFrag API", description="Security-Hardened, Privacy-Preserving Legal AI Workspace API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat.router)
app.include_router(upload.router)
app.include_router(recommend.router)
app.include_router(audit.router)

@app.get("/")
def read_root():
    return {"message": "DFrag API is running"}
