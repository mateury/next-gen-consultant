from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from external.text_model import ModelConnector
from dotenv import load_dotenv
import json


app = FastAPI()
# Mount MCP server routes to the main app
app.mount("/mcp", mcp_server.mcp.sse_app())

# Single ModelConnector instance
mc = None


async def process_text_streaming(text: str, websocket: WebSocket):
    """Process text and stream responses to websocket"""
    if mc is None:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Conversation not started"
        }))
        return

    # Stream the response
    full_response = ""
    async for chunk in mc.get_model_response_streaming(text):
        full_response += chunk
        # Send each chunk as it arrives
        await websocket.send_text(json.dumps({
            "type": "message_chunk",
            "text": chunk
        }))

    # Send completion signal
    await websocket.send_text(json.dumps({
        "type": "message_complete",
        "text": full_response
    }))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global mc

    await websocket.accept()
    
    # Utwórz unikalną sesję
    session_id = str(id(websocket))
    mc = ModelConnector()
    sessions[session_id] = mc
    
    # Wyślij wiadomość powitalną jako zwykły tekst
    await websocket.send_text("Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊")
    
    print(f"Client connected: {session_id}")

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            print(f"Received: {data}")

            try:
                message = json.loads(data)
                action = message.get("action")

                if action == "start":
                    # Start a new conversation
                    mc = text_model.ModelConnector()

                    response = {
                        "type": "conversation_started",
                        "message": "Conversation started successfully"
                    }
                    await websocket.send_text(json.dumps(response))
                    print("Started new conversation")

                elif action == "message":
                    # Send a message in the conversation
                    user_message = message.get("text")

                    if mc is None:
                        response = {
                            "type": "error",
                            "message": "Conversation not started. Please start a conversation first."
                        }
                        await websocket.send_text(json.dumps(response))
                        continue

                    # Process the message with streaming
                    await process_text_streaming(user_message, websocket)
                    print("Processed message with streaming")

                elif action == "end":
                    # End the conversation and reset context
                    if mc is not None:
                        mc.clear_history()
                        mc = None
                        response = {
                            "type": "conversation_ended",
                            "message": "Conversation ended successfully"
                        }
                        print("Ended conversation and cleared context")
                    else:
                        response = {
                            "type": "error",
                            "message": "No active conversation to end"
                        }

                    await websocket.send_text(json.dumps(response))

                else:
                    response = {
                        "type": "error",
                        "message": f"Unknown action: {action}"
                    }
                    await websocket.send_text(json.dumps(response))

            except json.JSONDecodeError:
                response = {
                    "type": "error",
                    "message": "Invalid message format. Expected JSON with 'action' field"
                }
                await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        print("Client disconnected")
        # Reset conversation on disconnect
        if mc is not None:
            mc.clear_history()
            mc = None
            print("Cleared conversation context")


# HTML client for testing
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
                    white-space: pre-wrap;
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
            </style>
        </head>
        <body>
            <div class="chat-container">
                <div class="chat-header">
                    <h1>🎯 Play - Wirtualny Konsultant</h1>
                    <p>Pomożemy Ci wybrać najlepszą ofertę!</p>
                </div>
                
                <div id="messages"></div>
                
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
                    // Streaming - dodawaj do bieżącej wiadomości bota
                    if (!currentBotMessage) {
                        currentBotMessage = addMessage('', 'bot');
                    }
                    currentBotMessage.textContent += event.data;
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                };

                ws.onopen = function(event) {
                    console.log('Connected to server');
                    sendBtn.disabled = false;
                };

                ws.onclose = function(event) {
                    console.log('Disconnected from server');
                    sendBtn.disabled = true;
                };

                document.getElementById('form').onsubmit = function(event) {
                    event.preventDefault();
                    
                    if (!input.value.trim()) return;
                    
                    const userMessage = input.value.trim();
                    addMessage(userMessage, 'user');
                    
                    // Wyślij jako zwykły tekst
                    ws.send(userMessage);
                    
                    input.value = '';
                    
                    // Przygotuj nową wiadomość bota
                    currentBotMessage = null;
                };

                input.focus();
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Play Virtual Consultant"}


if __name__ == "__main__":
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)