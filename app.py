from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from external.text_model import ModelConnector
from dotenv import load_dotenv
from typing import Dict

app = FastAPI()

# CORS dla frontendu Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Przechowywanie sesji użytkowników
sessions: Dict[str, ModelConnector] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Utwórz unikalną sesję
    session_id = str(id(websocket))
    mc = ModelConnector()
    sessions[session_id] = mc
    
    # Wyślij wiadomość powitalną jako zwykły tekst
    await websocket.send_text("Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊")
    
    print(f"✅ Client connected: {session_id}")

    try:
        while True:
            # Odbierz wiadomość jako zwykły tekst
            message = await websocket.receive_text()
            
            if not message.strip():
                continue
            
            print(f"📨 Received from {session_id}: {message}")
            
            try:
                # Callback dla streamingu - wysyłaj fragmenty tekstu
                async def stream_callback(chunk: str):
                    await websocket.send_text(chunk)
                
                # Przetwórz wiadomość ze streamingiem
                await mc.get_model_response(message, stream_callback)
                
                print(f"✅ Completed response to {session_id}")
                
            except Exception as api_error:
                # Obsłuż błędy API (np. 502 Bad Gateway)
                error_message = f"\n\n⚠️ Przepraszam, wystąpił problem z połączeniem. Spróbuj ponownie za chwilę."
                await websocket.send_text(error_message)
                print(f"⚠️ API Error for {session_id}: {api_error}")

    except WebSocketDisconnect:
        if session_id in sessions:
            del sessions[session_id]
        print(f"❌ Client disconnected: {session_id}")
    except Exception as e:
        print(f"⚠️ Error in websocket: {e}")
        if session_id in sessions:
            del sessions[session_id]


# HTML client dla testów
@app.get("/")
async def get():
    html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>Play - Wirtualny Konsultant</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    height: 100vh;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                }
                .chat-container {
                    width: 90%;
                    max-width: 800px;
                    height: 90vh;
                    background: white;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }
                .chat-header {
                    background: #6B46C1;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }
                .chat-header h1 {
                    font-size: 24px;
                    margin-bottom: 5px;
                }
                .status {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-size: 12px;
                    margin-top: 8px;
                }
                .status.connected { background: rgba(72, 187, 120, 0.3); }
                .status.disconnected { background: rgba(245, 101, 101, 0.3); }
                #messages {
                    flex: 1;
                    overflow-y: auto;
                    padding: 20px;
                    background: #f7fafc;
                }
                .message {
                    margin-bottom: 15px;
                    padding: 12px 16px;
                    border-radius: 12px;
                    max-width: 70%;
                    animation: fadeIn 0.3s;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                }
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateY(10px); }
                    to { opacity: 1; transform: translateY(0); }
                }
                .user-message {
                    background: #6B46C1;
                    color: white;
                    margin-left: auto;
                    text-align: right;
                }
                .bot-message {
                    background: white;
                    border: 1px solid #e2e8f0;
                    color: #2d3748;
                }
                .chat-input {
                    display: flex;
                    padding: 20px;
                    background: white;
                    border-top: 1px solid #e2e8f0;
                }
                #messageText {
                    flex: 1;
                    padding: 12px 16px;
                    border: 2px solid #e2e8f0;
                    border-radius: 25px;
                    font-size: 16px;
                    outline: none;
                    transition: border-color 0.3s;
                }
                #messageText:focus { border-color: #6B46C1; }
                #messageText:disabled {
                    background: #f7fafc;
                    cursor: not-allowed;
                }
                button {
                    margin-left: 10px;
                    padding: 12px 30px;
                    background: #6B46C1;
                    color: white;
                    border: none;
                    border-radius: 25px;
                    font-size: 16px;
                    cursor: pointer;
                    transition: background 0.3s;
                    font-weight: 500;
                }
                button:hover:not(:disabled) { background: #553C9A; }
                button:disabled {
                    background: #cbd5e0;
                    cursor: not-allowed;
                }
            </style>
        </head>
        <body>
            <div class="chat-container">
                <div class="chat-header">
                    <h1>🎯 Play - Wirtualny Konsultant</h1>
                    <span id="status" class="status disconnected">❌ Rozłączono</span>
                </div>
                
                <div id="messages"></div>
                
                <form class="chat-input" id="form">
                    <input 
                        type="text" 
                        id="messageText" 
                        autocomplete="off" 
                        placeholder="Wpisz swoją wiadomość..."
                        disabled
                    />
                    <button type="submit" id="sendBtn" disabled>Wyślij</button>
                </form>
            </div>

            <script>
                const ws = new WebSocket("ws://localhost:8000/ws");
                const messagesDiv = document.getElementById('messages');
                const form = document.getElementById('form');
                const input = document.getElementById('messageText');
                const sendBtn = document.getElementById('sendBtn');
                const statusEl = document.getElementById('status');
                
                let currentBotMessage = null;

                function addMessage(text, type) {
                    const message = document.createElement('div');
                    message.className = `message ${type}-message`;
                    message.textContent = text;
                    messagesDiv.appendChild(message);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    return message;
                }

                ws.onmessage = function(event) {
                    if (!currentBotMessage) {
                        currentBotMessage = addMessage('', 'bot');
                    }
                    currentBotMessage.textContent += event.data;
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                };

                ws.onopen = function(event) {
                    console.log('✅ Connected');
                    statusEl.textContent = '✅ Połączono';
                    statusEl.className = 'status connected';
                    sendBtn.disabled = false;
                    input.disabled = false;
                    input.focus();
                };

                ws.onclose = function(event) {
                    console.log('❌ Disconnected');
                    statusEl.textContent = '❌ Rozłączono';
                    statusEl.className = 'status disconnected';
                    sendBtn.disabled = true;
                    input.disabled = true;
                };

                ws.onerror = function(error) {
                    console.error('⚠️ WebSocket error:', error);
                };

                form.onsubmit = function(event) {
                    event.preventDefault();
                    
                    if (!input.value.trim()) return;
                    
                    const userMessage = input.value.trim();
                    addMessage(userMessage, 'user');
                    ws.send(userMessage);
                    input.value = '';
                    currentBotMessage = null;
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Play Virtual Consultant",
        "active_sessions": len(sessions)
    }


if __name__ == "__main__":
    load_dotenv()
    print("=" * 60)
    print("🚀 Play Virtual Consultant API")
    print("=" * 60)
    print("📍 WebSocket: ws://localhost:8000/ws")
    print("🌐 HTML Test Client: http://localhost:8000")
    print("💚 Health Check: http://localhost:8000/health")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000)