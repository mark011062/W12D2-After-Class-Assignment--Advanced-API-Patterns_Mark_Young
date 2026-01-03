from sqlalchemy import String, Integer, Boolean, ForeignKey, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="user")  # user | admin

    tasks: Mapped[list["Task"]] = relationship(back_populates="assignee")

class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)      # "NCM Track Day"
    track_name: Mapped[str] = mapped_column(String(200), index=True) # "NCM Motorsports Park"
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(50))
    event_date: Mapped["Date"] = mapped_column(Date)

    tasks: Mapped[list["Task"]] = relationship(back_populates="event")

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # race-weekend checklist fields
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    category: Mapped[str] = mapped_column(String(50), index=True)  # prep, pit, safety, travel, tech
    priority: Mapped[int] = mapped_column(Integer, default=3)      # 1 (high) - 5 (low)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    due_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    # relations
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"))
    event: Mapped["Event"] = relationship(back_populates="tasks")

    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assignee: Mapped["User"] = relationship(back_populates="tasks")

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
