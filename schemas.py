"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Core domain schemas for this app

class Download(BaseModel):
    """
    Stores metadata for a downloaded video
    Collection name: "download"
    """
    url: str = Field(..., description="Source URL of the video")
    title: Optional[str] = Field(None, description="Detected title")
    platform: Optional[str] = Field(None, description="Platform (YouTube, TikTok, Facebook, etc.)")
    filename: Optional[str] = Field(None, description="Stored file name on server")
    filepath: Optional[str] = Field(None, description="Absolute path to the stored file")
    thumbnail: Optional[str] = Field(None, description="Thumbnail URL if available")
    duration: Optional[float] = Field(None, description="Duration in seconds")
    ext: Optional[str] = Field(None, description="File extension")
    status: str = Field("ready", description="Status of the download record")

class StoryChapter(BaseModel):
    title: str
    summary: str

class Story(BaseModel):
    """
    AI-generated story structure
    Collection name: "story"
    """
    topic: str = Field(..., description="Story topic or prompt")
    style: Optional[str] = Field("narrative", description="Writing style")
    language: Optional[str] = Field("fr", description="Language of generated content")
    audience: Optional[str] = Field("general", description="Target audience")
    chapters: List[StoryChapter] = Field(default_factory=list)

class CourseLesson(BaseModel):
    title: str
    objectives: List[str] = Field(default_factory=list)
    content: str

class Course(BaseModel):
    """
    AI-generated course outline
    Collection name: "course"
    """
    topic: str
    level: Optional[str] = Field("beginner", description="Difficulty level")
    language: Optional[str] = Field("fr", description="Language")
    target_audience: Optional[str] = Field("general", description="Target audience")
    lessons: List[CourseLesson] = Field(default_factory=list)

# Example schemas kept for reference (not used by app but safe to keep)
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True

# The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
