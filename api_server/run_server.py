"""VocalPro API Server – convenience launcher.

Starts the FastAPI backend on localhost:8000.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        log_level="info",
        reload=False,
    )
