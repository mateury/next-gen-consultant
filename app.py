from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from external.text_model import ModelConnector
from dotenv import load_dotenv
import asyncio
from typing import Dict

app = FastAPI()

# Przechowywanie sesji użytkowników
sessions: Dict[str, ModelConnector] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Utwórz unikalną sesję
    session_id = str(id(websocket))
    mc = ModelConnector()
    sessions[session_id] = mc
    
    await websocket.send_json({
        "type": "connected",
        "message": "Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊"
    })
    
    print(f"Client connected: {session_id}")

    try:
        while True:
            # Receive text from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            print(f"Received from {session_id}: {message}")
            
            # Callback dla streamingu
            async def stream_callback(chunk: str):
                await websocket.send_json({
                    "type": "stream",
                    "content": chunk
                })
            
            # Process with streaming
            response = await mc.get_model_response(message, stream_callback)
            
            # Send completion signal
            await websocket.send_json({
                "type": "complete",
                "content": response
            })
            
            print(f"Completed response to {session_id}")

    except WebSocketDisconnect:
        if session_id in sessions:
            del sessions[session_id]
        print(f"Client disconnected: {session_id}")


# Zaktualizowany HTML z lepszym UI
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
                .chat-header p {
                    font-size: 14px;
                    opacity: 0.9;
                }
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
                .system-message {
                    background: #edf2f7;
                    color: #4a5568;
                    text-align: center;
                    font-size: 14px;
                    margin: 10px auto;
                    max-width: 80%;
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
                #messageText:focus {
                    border-color: #6B46C1;
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
                }
                button:hover {
                    background: #553C9A;
                }
                button:disabled {
                    background: #cbd5e0;
                    cursor: not-allowed;
                }
                .typing-indicator {
                    display: none;
                    padding: 10px;
                    color: #718096;
                    font-style: italic;
                }
                .typing-indicator.active {
                    display: block;
                }
            </style>
        </head>
        <body>
            <div class="chat-container">
                <div class="chat-header">
                    <h1>🎯 Play - Wirtualny Konsultant</h1>
                    <p>Pomożemy Ci wybrać najlepszą ofertę!</p>
                </div>
                
                <div id="messages"></div>
                <div class="typing-indicator" id="typing">Konsultant pisze...</div>
                
                <form class="chat-input" id="form">
                    <input 
                        type="text" 
                        id="messageText" 
                        autocomplete="off" 
                        placeholder="Wpisz swoją wiadomość..."
                    />
                    <button type="submit" id="sendBtn">Wyślij</button>
                </form>
            </div>

            <script>
                const ws = new WebSocket("ws://localhost:8000/ws");
                const messagesDiv = document.getElementById('messages');
                const form = document.getElementById('form');
                const input = document.getElementById('messageText');
                const sendBtn = document.getElementById('sendBtn');
                const typingIndicator = document.getElementById('typing');
                
                let currentBotMessage = null;
                let isProcessing = false;

                function addMessage(text, type) {
                    const message = document.createElement('div');
                    message.className = `message ${type}-message`;
                    message.textContent = text;
                    messagesDiv.appendChild(message);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    return message;
                }

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'connected') {
                        addMessage(data.message, 'system');
                    }
                    else if (data.type === 'stream') {
                        if (!currentBotMessage) {
                            currentBotMessage = addMessage('', 'bot');
                        }
                        currentBotMessage.textContent += data.content;
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                    else if (data.type === 'complete') {
                        currentBotMessage = null;
                        typingIndicator.classList.remove('active');
                        isProcessing = false;
                        sendBtn.disabled = false;
                        input.disabled = false;
                    }
                };

                ws.onopen = function(event) {
                    addMessage('Połączono z serwerem', 'system');
                };

                ws.onclose = function(event) {
                    addMessage('Rozłączono z serwerem', 'system');
                    sendBtn.disabled = true;
                    input.disabled = true;
                };

                form.onsubmit = function(event) {
                    event.preventDefault();
                    
                    if (isProcessing || !input.value.trim()) return;
                    
                    const userMessage = input.value.trim();
                    addMessage(userMessage, 'user');
                    
                    ws.send(JSON.stringify({ message: userMessage }));
                    
                    input.value = '';
                    isProcessing = true;
                    sendBtn.disabled = true;
                    typingIndicator.classList.add('active');
                };

                // Auto-focus on input
                input.focus();
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


if __name__ == "__main__":
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)