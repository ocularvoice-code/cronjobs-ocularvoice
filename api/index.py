from main import app as fastapi_app

# Expose FastAPI app for Vercel's Python runtime entrypoint
app = fastapi_app

__all__ = ["app"]
