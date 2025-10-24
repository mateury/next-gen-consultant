from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from external.text_model import ModelConnector
from dotenv import load_dotenv
from typing import Dict
import json
from datetime import datetime

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


def log_colored(emoji: str, message: str, data=None):
    """Kolorowe logowanie z timestampem"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*80}")
    print(f"{emoji} [{timestamp}] {message}")
    if data:
        print(f"{'─'*80}")
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(str(data))
    print(f"{'='*80}\n")


def log_history(session_id: str, history: list):
    """Wyświetl szczegółową historię konwersacji"""
    print(f"\n{'┌'+'─'*78+'┐'}")
    print(f"│ 📚 HISTORIA KONWERSACJI - Session: {session_id[:16]}... {'│':>34}")
    print(f"│ Liczba wiadomości: {len(history):<56} │")
    print(f"├{'─'*78}┤")
    
    for idx, msg in enumerate(history, 1):
        msg_type = msg.__class__.__name__
        
        if msg_type == "SystemMessage":
            icon = "🤖"
            label = "SYSTEM"
            preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        elif msg_type == "HumanMessage":
            icon = "👤"
            label = "USER  "
            preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        elif msg_type == "AIMessage":
            icon = "🤖"
            label = "AI    "
            preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        else:
            icon = "❓"
            label = "OTHER "
            preview = str(msg)[:100]
        
        print(f"│ {idx:2}. {icon} [{label}] {preview:<55} │")
    
    print(f"└{'─'*78}┘\n")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Utwórz unikalną sesję
    session_id = str(id(websocket))
    mc = ModelConnector()
    sessions[session_id] = mc
    
    log_colored("🟢", f"NOWE POŁĄCZENIE", {
        "session_id": session_id,
        "client": str(websocket.client),
        "total_sessions": len(sessions)
    })
    
    # Wyślij wiadomość powitalną
    welcome_msg = "Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊"
    await websocket.send_text(welcome_msg)
    
    log_colored("📤", "WYSŁANO POWITANIE", {
        "session_id": session_id,
        "message": welcome_msg
    })

    try:
        while True:
            # Odbierz wiadomość jako zwykły tekst
            message = await websocket.receive_text()
            
            if not message.strip():
                log_colored("⚠️", "OTRZYMANO PUSTĄ WIADOMOŚĆ", {"session_id": session_id})
                continue
            
            log_colored("📨", "OTRZYMANO WIADOMOŚĆ OD UŻYTKOWNIKA", {
                "session_id": session_id,
                "message": message,
                "length": len(message)
            })
            
            # Pokaż historię PRZED przetworzeniem
            log_history(session_id, mc.get_history())
            
            try:
                # Callback dla streamingu
                chunk_count = 0
                total_length = 0
                
                async def stream_callback(chunk: str):
                    nonlocal chunk_count, total_length
                    chunk_count += 1
                    total_length += len(chunk)
                    await websocket.send_text(chunk)
                    
                    # Loguj co 10 chunków
                    if chunk_count % 10 == 0:
                        print(f"  📊 Streaming progress: {chunk_count} chunks, {total_length} chars")
                
                log_colored("⚙️", "ROZPOCZYNAM PRZETWARZANIE", {
                    "session_id": session_id,
                    "model": "gpt-oss-120b (Scaleway)",
                    "streaming": True
                })
                
                # Przetwórz wiadomość ze streamingiem
                start_time = datetime.now()
                response = await mc.get_model_response(message, stream_callback)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                log_colored("✅", "ZAKOŃCZONO PRZETWARZANIE", {
                    "session_id": session_id,
                    "chunks_sent": chunk_count,
                    "total_length": total_length,
                    "duration_seconds": round(duration, 2),
                    "chars_per_second": round(total_length / duration, 2) if duration > 0 else 0
                })
                
                # Pokaż historię PO przetworzeniu
                log_history(session_id, mc.get_history())
                
                # Pokaż odpowiedź AI
                log_colored("🤖", "ODPOWIEDŹ AI (pełna)", {
                    "session_id": session_id,
                    "response_preview": response[:500] + "..." if len(response) > 500 else response,
                    "full_length": len(response)
                })
                
            except Exception as api_error:
                log_colored("❌", "BŁĄD API", {
                    "session_id": session_id,
                    "error_type": type(api_error).__name__,
                    "error_message": str(api_error),
                    "user_message": message
                })
                
                error_message = f"\n\n⚠️ Przepraszam, wystąpił problem z połączeniem. Spróbuj ponownie za chwilę."
                await websocket.send_text(error_message)

    except WebSocketDisconnect:
        if session_id in sessions:
            # Zapisz ostatnią historię przed usunięciem
            final_history = sessions[session_id].get_history()
            del sessions[session_id]
            
            log_colored("🔴", "ROZŁĄCZONO KLIENTA", {
                "session_id": session_id,
                "final_history_length": len(final_history),
                "remaining_sessions": len(sessions)
            })
            
            # Pokaż ostateczną historię
            log_history(session_id, final_history)
        
    except Exception as e:
        log_colored("💥", "NIEOCZEKIWANY BŁĄD", {
            "session_id": session_id,
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": True
        })
        
        if session_id in sessions:
            del sessions[session_id]
        
        import traceback
        traceback.print_exc()


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