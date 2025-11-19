import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Optional database helpers
try:
    from database import create_document, db
except Exception:
    create_document = None
    db = None

# Create downloads directory
DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Media Downloader & AI Content API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded files
app.mount("/files", StaticFiles(directory=str(DOWNLOAD_DIR)), name="files")


@app.get("/")
def read_root():
    return {"name": "Media Downloader & AI Content API", "status": "ok"}


# ------------------------
# Download Endpoint
# ------------------------
class DownloadRequest(BaseModel):
    url: str
    ext: Optional[str] = "mp4"  # preferred extension when possible


class DownloadResponse(BaseModel):
    url: str
    title: Optional[str] = None
    platform: Optional[str] = None
    duration: Optional[float] = None
    ext: Optional[str] = None
    filename: Optional[str] = None
    file_url: Optional[str] = None
    thumbnail: Optional[str] = None


def _build_public_file_url(request: Request, filename: str) -> str:
    """Build an absolute URL to the file using BACKEND_PUBLIC_URL if set,
    otherwise fall back to request.base_url.
    """
    backend_url = os.getenv("BACKEND_PUBLIC_URL") or ""
    if backend_url:
        backend_url = backend_url[:-1] if backend_url.endswith("/") else backend_url
        return f"{backend_url}/files/{filename}"
    # Fallback to request base URL
    base = str(request.base_url).rstrip("/")
    return f"{base}/files/{filename}"


@app.post("/api/download", response_model=DownloadResponse)
def download_media(payload: DownloadRequest, request: Request):
    """Download a media file from YouTube, TikTok, Facebook, etc. using yt-dlp."""
    # Lazy import to speed cold start
    try:
        import yt_dlp as ytdlp
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"yt-dlp non disponible: {e}")

    # Extract info first
    info_dict = None
    ydl_opts_info = {
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with ytdlp.YoutubeDL(ydl_opts_info) as ydl:
        try:
            info_dict = ydl.extract_info(payload.url, download=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Impossible d'analyser l'URL: {e}")

    title = info_dict.get("title")
    duration = info_dict.get("duration")
    thumbnail = info_dict.get("thumbnail")
    extractor = info_dict.get("extractor")
    platform = None
    if extractor:
        if "youtube" in extractor:
            platform = "YouTube"
        elif "tiktok" in extractor:
            platform = "TikTok"
        elif "facebook" in extractor or "instagram" in extractor:
            platform = "Facebook"
        else:
            platform = extractor

    # Prepare download
    safe_title = (title or "video").replace("/", "-").replace("\\", "-")
    out_tmpl = str(DOWNLOAD_DIR / f"{safe_title}.%(ext)s")

    preferred_ext = payload.ext or "mp4"
    ydl_opts_download = {
        "outtmpl": out_tmpl,
        "merge_output_format": preferred_ext,
        "format": "bestvideo+bestaudio/best",
        "quiet": True,
        "no_warnings": True,
    }

    actual_file = None
    with ytdlp.YoutubeDL(ydl_opts_download) as ydl:
        try:
            result = ydl.extract_info(payload.url, download=True)
            if "requested_downloads" in result and result["requested_downloads"]:
                actual_file = result["requested_downloads"][0].get("_filename")
            else:
                actual_file = ydl.prepare_filename(result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Echec du téléchargement: {e}")

    if not actual_file:
        raise HTTPException(status_code=500, detail="Fichier non trouvé après téléchargement")

    file_path = Path(actual_file)
    ext = file_path.suffix.lstrip(".")
    filename = file_path.name

    # Build absolute file URL for the client
    file_url = _build_public_file_url(request, filename)

    # Save metadata to DB if available
    try:
        if create_document is not None and db is not None:
            create_document(
                "download",
                {
                    "url": payload.url,
                    "title": title,
                    "platform": platform,
                    "filename": filename,
                    "filepath": str(file_path.resolve()),
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "ext": ext,
                    "status": "ready",
                },
            )
    except Exception:
        # Database is optional; continue if not configured
        pass

    return DownloadResponse(
        url=payload.url,
        title=title,
        platform=platform,
        duration=duration,
        ext=ext,
        filename=filename,
        file_url=file_url,
        thumbnail=thumbnail,
    )


# ------------------------
# Simple AI Generators (rule-based, no external API)
# ------------------------
class StoryRequest(BaseModel):
    topic: str
    style: Optional[str] = "narratif"
    language: Optional[str] = "fr"
    audience: Optional[str] = "grand public"
    chapters: Optional[int] = 5


class StoryChapter(BaseModel):
    title: str
    summary: str


class StoryResponse(BaseModel):
    topic: str
    style: str
    language: str
    audience: str
    chapters: List[StoryChapter]


@app.post("/api/story", response_model=StoryResponse)
def generate_story(req: StoryRequest):
    # Generate simple chapter titles and summaries
    caps_topic = req.topic.capitalize()
    chapters: List[StoryChapter] = []
    template_titles = [
        "Origines",
        "Le Défi",
        "La Découverte",
        "Le Tournant",
        "Résolution",
        "Leçon Finale",
    ]
    n = max(2, min(12, req.chapters or 5))
    for i in range(n):
        base_title = template_titles[i % len(template_titles)]
        title = f"Chapitre {i+1}: {base_title}"
        summary = (
            f"Dans ce chapitre, {caps_topic} progresse. "
            f"Style {req.style}. Public: {req.audience}. "
            f"Tonalité réfléchie et pédagogique."
        )
        chapters.append(StoryChapter(title=title, summary=summary))

    # Store in DB (optional)
    try:
        if create_document is not None and db is not None:
            create_document(
                "story",
                {
                    "topic": req.topic,
                    "style": req.style,
                    "language": req.language,
                    "audience": req.audience,
                    "chapters": [c.model_dump() for c in chapters],
                },
            )
    except Exception:
        pass

    return StoryResponse(
        topic=req.topic,
        style=req.style or "narratif",
        language=req.language or "fr",
        audience=req.audience or "grand public",
        chapters=chapters,
    )


class CourseRequest(BaseModel):
    topic: str
    level: Optional[str] = "débutant"
    language: Optional[str] = "fr"
    target_audience: Optional[str] = "grand public"
    lessons: Optional[int] = 6


class CourseLesson(BaseModel):
    title: str
    objectives: List[str]
    content: str


class CourseResponse(BaseModel):
    topic: str
    level: str
    language: str
    target_audience: str
    lessons: List[CourseLesson]


@app.post("/api/course", response_model=CourseResponse)
def generate_course(req: CourseRequest):
    n = max(3, min(20, req.lessons or 6))
    lessons: List[CourseLesson] = []
    for i in range(n):
        ltitle = f"Leçon {i+1}: {req.topic} - Concept {i+1}"
        objectives = [
            f"Comprendre le concept {i+1}",
            f"Appliquer {req.topic} dans un cas simple",
            f"Évaluer sa progression au niveau {req.level}",
        ]
        content = (
            f"Cette leçon introduit le concept {i+1} de {req.topic}. "
            f"Adaptée au niveau {req.level}, en {req.language}. "
            f"Public cible: {req.target_audience}."
        )
        lessons.append(CourseLesson(title=ltitle, objectives=objectives, content=content))

    # Save to DB if available
    try:
        if create_document is not None and db is not None:
            create_document(
                "course",
                {
                    "topic": req.topic,
                    "level": req.level,
                    "language": req.language,
                    "target_audience": req.target_audience,
                    "lessons": [l.model_dump() for l in lessons],
                },
            )
    except Exception:
        pass

    return CourseResponse(
        topic=req.topic,
        level=req.level or "débutant",
        language=req.language or "fr",
        target_audience=req.target_audience or "grand public",
        lessons=lessons,
    )


@app.get("/test")
def test_database():
    response: Dict[str, Any] = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        from database import db as _db
        if _db is not None:
            response["database"] = "✅ Available"
            response["database_name"] = getattr(_db, "name", None)
            try:
                response["collections"] = _db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


@app.get("/schema")
def get_schemas():
    """Expose key Pydantic schemas so external tools can introspect collections."""
    from schemas import Download as SDownload, Story as SStory, Course as SCourse, StoryChapter as SStoryChapter, CourseLesson as SCourseLesson

    def model_schema(m):
        try:
            return m.model_json_schema()
        except Exception:
            return {}

    return {
        "download": model_schema(SDownload),
        "story": model_schema(SStory),
        "story_chapter": model_schema(SStoryChapter),
        "course": model_schema(SCourse),
        "course_lesson": model_schema(SCourseLesson),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
