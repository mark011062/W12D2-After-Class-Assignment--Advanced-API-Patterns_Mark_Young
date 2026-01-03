from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

TaskCategory = Literal["prep", "pit", "safety", "travel", "tech"]

class TaskCreate(BaseModel):
    event_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    category: TaskCategory
    priority: int = Field(default=3, ge=1, le=5)
    due_at: datetime | None = None
    assignee_id: int | None = None

class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    category: TaskCategory | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    due_at: datetime | None = None
    completed: bool | None = None
    assignee_id: int | None = None

class TaskOut(BaseModel):
    id: int
    event_id: int
    assignee_id: int | None
    title: str
    description: str
    category: str
    priority: int
    completed: bool
    due_at: datetime | None

    class Config:
        from_attributes = True
