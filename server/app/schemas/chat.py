from pydantic import BaseModel


# --- Chat ---

class FileRef(BaseModel):
    id: str
    filename: str


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    model: str = "openrouter"
    messages: list[dict]
    files: list[FileRef] | None = None


# --- Conversation ---

class ConversationCreate(BaseModel):
    title: str = "新对话"
    model: str = "openrouter"


class ConversationOut(BaseModel):
    id: str
    title: str
    model: str
    created_at: int
    updated_at: int
    message_count: int = 0


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    thinking_content: str | None = None
    files_json: str | None = None
    citations_json: str | None = None
    timestamp: int


# --- Knowledge ---

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    created_at: int
