from datetime import date
from pydantic import BaseModel, Field

class EventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    track_name: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=50)
    event_date: date

class EventOut(BaseModel):
    id: int
    name: str
    track_name: str
    city: str
    state: str
    event_date: date

    class Config:
        from_attributes = True
