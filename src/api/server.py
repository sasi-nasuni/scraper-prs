"""
Entry point for the FastAPI server.

Usage:
    uvicorn src.api.server:app --reload --port 8000

Or via the CLI:
    python -m src.api.server
"""
import uvicorn

from src.api.routes import app  # noqa: F401 – re-export for uvicorn


def main() -> None:
    """Run the API server."""
    uvicorn.run(
        "src.api.routes:app",
        host="127.0.0.1",
        port=8001,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
