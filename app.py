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
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"\n{'='*80}")
    print(f"{emoji} [{timestamp}] {message}")
    if data:
        print(f"{'─'*80}")
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(str(data))
    print(f"{'='*80}\n")


def log_history(session_id: str, history: list, stats: dict = None):
    """Wyświetl szczegółową historię konwersacji"""
    print(f"\n{'┌'+'─'*78+'┐'}")
    print(f"│ 📚 HISTORIA KONWERSACJI - Session: {session_id[:16]}...{' '*34}│")
    
    if stats:
        print(f"│ Total: {stats['total_messages']:3} | User: {stats['user_messages']:3} | AI: {stats['ai_messages']:3} | System: {stats['system_messages']:3} {' '*17}│")
    else:
        print(f"│ Liczba wiadomości: {len(history):<56} │")
    
    print(f"├{'─'*78}┤")
    
    for idx, msg in enumerate(history, 1):
        msg_type = msg.__class__.__name__
        
        if msg_type == "SystemMessage":
            icon = "⚙️"
            label = "SYSTEM"
            preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
        elif msg_type == "HumanMessage":
            icon = "👤"
            label = "USER  "
            preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
        elif msg_type == "AIMessage":
            icon = "🤖"
            label = "AI    "
            preview = msg.content[:60] + "..." if len(msg.content) > 60 else msg.content
        else:
            icon = "❓"
            label = "OTHER "
            preview = str(msg)[:60]
        
        preview = preview.replace('\n', ' ').replace('\r', '')
        print(f"│ {idx:2}. {icon} [{label}] {preview:<58}│")
    
    print(f"└{'─'*78}┘\n")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Utwórz unikalną sesję
    session_id = str(id(websocket))
    mc = ModelConnector()
    sessions[session_id] = mc
    
    log_colored("🟢", "NOWE POŁĄCZENIE", {
        "session_id": session_id,
        "client": str(websocket.client),
        "total_sessions": len(sessions)
    })
    
    # Wyślij wiadomość powitalną ze strukturą JSON
    welcome_msg = "Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊"
    await websocket.send_json({
        "type": "message",
        "content": welcome_msg
    })
    
    log_colored("📤", "WYSŁANO POWITANIE", {
        "session_id": session_id,
        "message": welcome_msg
    })
    
    # Pokaż początkową historię
    log_history(session_id, mc.get_history(), mc.get_stats())

    try:
        while True:
            # Odbierz wiadomość jako tekst
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
            print("\n" + "━"*80)
            print("📖 HISTORIA PRZED PRZETWORZENIEM:")
            print("━"*80)
            log_history(session_id, mc.get_history(), mc.get_stats())
            
            try:
                # Wyślij sygnał rozpoczęcia streamingu
                await websocket.send_json({
                    "type": "stream_start",
                    "content": ""
                })
                
                # Callback dla streamingu - wysyłaj chunki
                chunk_count = 0
                total_length = 0
                chunks_preview = []
                
                async def stream_callback(chunk: str):
                    nonlocal chunk_count, total_length, chunks_preview
                    chunk_count += 1
                    total_length += len(chunk)
                    
                    # Zapisz pierwsze 5 chunków do podglądu
                    if chunk_count <= 5:
                        chunks_preview.append(chunk)
                    
                    # Wyślij chunk jako JSON
                    await websocket.send_json({
                        "type": "stream_chunk",
                        "content": chunk
                    })
                    
                    # Loguj co 20 chunków
                    if chunk_count % 20 == 0:
                        print(f"  📊 Streaming: {chunk_count} chunks | {total_length} chars")
                
                log_colored("⚙️", "ROZPOCZYNAM PRZETWARZANIE", {
                    "session_id": session_id,
                    "model": "gpt-oss-120b (Scaleway)",
                    "streaming": True,
                    "user_message": message
                })
                
                # Przetwórz wiadomość ze streamingiem
                start_time = datetime.now()
                response = await mc.get_model_response(message, stream_callback)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Wyślij sygnał zakończenia streamingu
                await websocket.send_json({
                    "type": "stream_end",
                    "content": ""
                })
                
                log_colored("✅", "ZAKOŃCZONO PRZETWARZANIE", {
                    "session_id": session_id,
                    "chunks_sent": chunk_count,
                    "total_length": total_length,
                    "duration_seconds": round(duration, 2),
                    "chars_per_second": round(total_length / duration, 2) if duration > 0 else 0,
                    "first_chunks": "".join(chunks_preview[:3])
                })
                
                # Pokaż historię PO przetworzeniu
                print("\n" + "━"*80)
                print("📖 HISTORIA PO PRZETWORZENIU:")
                print("━"*80)
                log_history(session_id, mc.get_history(), mc.get_stats())
                
                # Pokaż pełną odpowiedź AI
                log_colored("🤖", "ODPOWIEDŹ AI (pełna)", {
                    "session_id": session_id,
                    "response_preview": response[:300] + "..." if len(response) > 300 else response,
                    "full_length": len(response),
                    "has_tool_commands": any(cmd in response for cmd in ["[CHECK_CUSTOMER:", "[GET_CATALOG"])
                })
                
            except Exception as api_error:
                log_colored("❌", "BŁĄD API", {
                    "session_id": session_id,
                    "error_type": type(api_error).__name__,
                    "error_message": str(api_error),
                    "user_message": message
                })
                
                error_message = f"⚠️ Przepraszam, wystąpił problem z połączeniem. Spróbuj ponownie za chwilę.\n\nBłąd: {type(api_error).__name__}"
                
                # Wyślij błąd jako JSON
                await websocket.send_json({
                    "type": "error",
                    "content": error_message
                })
                
                import traceback
                print("📍 Stack trace:")
                traceback.print_exc()

    except WebSocketDisconnect:
        if session_id in sessions:
            final_history = sessions[session_id].get_history()
            final_stats = sessions[session_id].get_stats()
            del sessions[session_id]
            
            log_colored("🔴", "ROZŁĄCZONO KLIENTA", {
                "session_id": session_id,
                "final_stats": final_stats,
                "remaining_sessions": len(sessions)
            })
            
            print("\n" + "━"*80)
            print("📖 OSTATECZNA HISTORIA PRZED ROZŁĄCZENIEM:")
            print("━"*80)
            log_history(session_id, final_history, final_stats)
        
    except Exception as e:
        log_colored("💥", "NIEOCZEKIWANY BŁĄD", {
            "session_id": session_id,
            "error_type": type(e).__name__,
            "error_message": str(e)
        })
        
        if session_id in sessions:
            del sessions[session_id]
        
        import traceback
        print("📍 Stack trace:")
        traceback.print_exc()


# HTML client z obsługą JSON streaming
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
                .chat-header h1 { font-size: 24px; margin-bottom: 5px; }
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
                .error-message {
                    background: #fed7d7;
                    border: 1px solid #fc8181;
                    color: #c53030;
                    max-width: 70%;
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
                }
                #messageText:focus { border-color: #6B46C1; }
                button {
                    margin-left: 10px;
                    padding: 12px 30px;
                    background: #6B46C1;
                    color: white;
                    border: none;
                    border-radius: 25px;
                    font-size: 16px;
                    cursor: pointer;
                    font-weight: 500;
                }
                button:hover:not(:disabled) { background: #553C9A; }
                button:disabled { background: #cbd5e0; cursor: not-allowed; }
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
                    <input type="text" id="messageText" autocomplete="off" placeholder="Wpisz swoją wiadomość..." disabled />
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
                let isStreaming = false;

                function addMessage(text, type) {
                    const message = document.createElement('div');
                    message.className = `message ${type}-message`;
                    message.textContent = text;
                    messagesDiv.appendChild(message);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    return message;
                }

                ws.onmessage = function(event) {
                    try {
                        // Parsuj JSON
                        const data = JSON.parse(event.data);
                        console.log('Received:', data);

                        switch(data.type) {
                            case 'message':
                                // Zwykła wiadomość (np. powitanie)
                                addMessage(data.content, 'bot');
                                break;

                            case 'stream_start':
                                // Rozpocznij nową wiadomość od bota
                                isStreaming = true;
                                currentBotMessage = addMessage('', 'bot');
                                break;

                            case 'stream_chunk':
                                // Dodaj chunk do bieżącej wiadomości
                                if (currentBotMessage && isStreaming) {
                                    currentBotMessage.textContent += data.content;
                                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                                }
                                break;

                            case 'stream_end':
                                // Zakończ streaming
                                isStreaming = false;
                                currentBotMessage = null;
                                break;

                            case 'error':
                                // Wyświetl błąd
                                addMessage(data.content, 'error');
                                isStreaming = false;
                                currentBotMessage = null;
                                break;

                            default:
                                console.warn('Unknown message type:', data.type);
                        }
                    } catch (e) {
                        console.error('Error parsing message:', e);
                        // Fallback - traktuj jako zwykły tekst
                        if (!currentBotMessage) {
                            currentBotMessage = addMessage('', 'bot');
                        }
                        currentBotMessage.textContent += event.data;
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                };

                ws.onopen = function() {
                    console.log('✅ Connected');
                    statusEl.textContent = '✅ Połączono';
                    statusEl.className = 'status connected';
                    sendBtn.disabled = false;
                    input.disabled = false;
                    input.focus();
                };

                ws.onclose = function() {
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
                    
                    // Wyślij jako zwykły tekst (nie JSON)
                    ws.send(userMessage);
                    
                    input.value = '';
                    currentBotMessage = null;
                    isStreaming = false;
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "Play Virtual Consultant",
        "active_sessions": len(sessions),
        "session_stats": {sid: sessions[sid].get_stats() for sid in sessions}
    }


if __name__ == "__main__":
    load_dotenv()
    print("=" * 80)
    print("🚀 Play Virtual Consultant API - JSON Streaming Mode")
    print("=" * 80)
    print("📍 WebSocket: ws://localhost:8000/ws")
    print("🌐 HTML Test Client: http://localhost:8000")
    print("💚 Health Check: http://localhost:8000/health")
    print("=" * 80)
    print("\n📦 Message Format:")
    print('  {"type": "stream_start", "content": ""}')
    print('  {"type": "stream_chunk", "content": "Hello"}')
    print('  {"type": "stream_end", "content": ""}')
    print("=" * 80)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")