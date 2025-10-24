"""
Play Virtual Consultant API - Main application.
"""

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from dotenv import load_dotenv
from pathlib import Path

from core import SessionManager, WebSocketHandler

# Initialize FastAPI app
app = FastAPI(
    title="Play Virtual Consultant API",
    description="AI-powered virtual consultant for Play telecom services",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Initialize session manager and WebSocket handler
session_manager = SessionManager()
ws_handler = WebSocketHandler(session_manager)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for chat communication.
    
    Message format:
        - {"type": "message", "content": "text"}
        - {"type": "stream_start", "content": ""}
        - {"type": "stream_chunk", "content": "partial text"}
        - {"type": "stream_end", "content": ""}
        - {"type": "error", "content": "error message"}
    """
    await ws_handler.handle_connection(websocket)


@app.get("/", response_class=HTMLResponse)
async def get_chat_client():
    """Serve the HTML test client."""
    html_file = Path(__file__).parent / "static" / "chat.html"
    
    if html_file.exists():
        return FileResponse(html_file)
    
    # Fallback if static file doesn't exist
    return HTMLResponse("""
        <html>
            <body>
                <h1>Play Virtual Consultant</h1>
                <p>WebSocket endpoint: ws://localhost:8000/ws</p>
                <p>API Docs: <a href="/docs">/docs</a></p>
            </body>
        </html>
    """)


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Status information and active session count
    """
    return {
        "status": "healthy",
        "service": "Play Virtual Consultant",
        "active_sessions": session_manager.get_active_count(),
        "session_stats": session_manager.get_all_stats()
    }


@app.get("/api/info")
async def api_info():
    """
    API information endpoint.
    
    Returns:
        API version and capabilities
    """
    return {
        "name": "Play Virtual Consultant API",
        "version": "1.0.0",
        "features": [
            "AI-powered chat",
            "Customer verification (PESEL)",
            "Product catalog access",
            "Streaming responses",
            "Session management"
        ],
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
            "docs": "/docs"
        }
    }


def main():
    """Main entry point."""
    load_dotenv()
    
    print("=" * 80)
    print("🚀 Play Virtual Consultant API - JSON Streaming Mode")
    print("=" * 80)
    print("📍 WebSocket: ws://localhost:8000/ws")
    print("🌐 HTML Test Client: http://localhost:8000")
    print("💚 Health Check: http://localhost:8000/health")
    print("📚 API Docs: http://localhost:8000/docs")
    print("=" * 80)
    print("\n📦 Message Format:")
    print('  {"type": "stream_start", "content": ""}')
    print('  {"type": "stream_chunk", "content": "Hello"}')
    print('  {"type": "stream_end", "content": ""}')
    print("=" * 80)
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info",
        reload=True  # Auto-reload on code changes
    )


if __name__ == "__main__":
    main()