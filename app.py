from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from external import text_model, mcp_server
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
    print("Client connected")

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
            <title>WebSocket Conversation Client</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
                #messages { list-style: none; padding: 0; max-height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; }
                #messages li { margin: 10px 0; padding: 5px; }
                .user { color: #0066cc; }
                .assistant { color: #00aa00; }
                .system { color: #888; font-style: italic; }
                .error { color: #cc0000; }
                button { margin: 5px; padding: 10px 20px; }
                input[type="text"] { width: 70%; padding: 10px; }
                #controlButtons { margin: 20px 0; }
            </style>
        </head>
        <body>
            <h1>WebSocket Conversation Client (Streaming)</h1>

            <div id="controlButtons">
                <button id="startBtn" onclick="startConversation()">Start Conversation</button>
                <button id="endBtn" onclick="endConversation()" disabled>End Conversation</button>
            </div>

            <form id="form">
                <input type="text" id="messageText" autocomplete="off" placeholder="Start a conversation first..." disabled/>
                <button type="submit" disabled id="sendBtn">Send</button>
            </form>

            <ul id="messages"></ul>

            <script>
                const ws = new WebSocket("ws://localhost:8000/ws");
                let conversationActive = false;
                let currentAssistantMessage = null;

                ws.onmessage = function(event) {
                    const data = JSON.parse(event.data);
                    const messages = document.getElementById('messages');

                    if (data.type === "conversation_started") {
                        conversationActive = true;
                        const message = document.createElement('li');
                        message.textContent = "System: " + data.message;
                        message.className = 'system';
                        messages.appendChild(message);

                        // Enable message input
                        document.getElementById('messageText').disabled = false;
                        document.getElementById('messageText').placeholder = "Enter your message...";
                        document.getElementById('sendBtn').disabled = false;
                        document.getElementById('startBtn').disabled = true;
                        document.getElementById('endBtn').disabled = false;
                    } 
                    else if (data.type === "message_chunk") {
                        // Create new message element if this is the first chunk
                        if (!currentAssistantMessage) {
                            currentAssistantMessage = document.createElement('li');
                            currentAssistantMessage.textContent = "Assistant: ";
                            currentAssistantMessage.className = 'assistant';
                            messages.appendChild(currentAssistantMessage);
                        }
                        // Append the chunk to the current message
                        currentAssistantMessage.textContent += data.text;
                        messages.scrollTop = messages.scrollHeight;
                    }
                    else if (data.type === "message_complete") {
                        // Reset for next message
                        currentAssistantMessage = null;
                        messages.scrollTop = messages.scrollHeight;
                    }
                    else if (data.type === "conversation_ended") {
                        conversationActive = false;
                        const message = document.createElement('li');
                        message.textContent = "System: " + data.message;
                        message.className = 'system';
                        messages.appendChild(message);

                        // Disable message input
                        document.getElementById('messageText').disabled = true;
                        document.getElementById('messageText').placeholder = "Start a conversation first...";
                        document.getElementById('sendBtn').disabled = true;
                        document.getElementById('startBtn').disabled = false;
                        document.getElementById('endBtn').disabled = true;
                    }
                    else if (data.type === "error") {
                        const message = document.createElement('li');
                        message.textContent = "Error: " + data.message;
                        message.className = 'error';
                        messages.appendChild(message);
                    }

                    messages.scrollTop = messages.scrollHeight;
                };

                ws.onopen = function(event) {
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "System: Connected to server";
                    message.className = 'system';
                    messages.appendChild(message);
                };

                ws.onclose = function(event) {
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "System: Disconnected from server";
                    message.className = 'system';
                    messages.appendChild(message);
                };

                function startConversation() {
                    const command = {
                        action: "start"
                    };
                    ws.send(JSON.stringify(command));
                }

                function endConversation() {
                    if (conversationActive) {
                        const command = {
                            action: "end"
                        };
                        ws.send(JSON.stringify(command));
                    }
                }

                document.getElementById('form').onsubmit = function(event) {
                    event.preventDefault();
                    const input = document.getElementById('messageText');

                    if (!conversationActive) {
                        alert("Please start a conversation first");
                        return;
                    }

                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "You: " + input.value;
                    message.className = 'user';
                    messages.appendChild(message);

                    const command = {
                        action: "message",
                        text: input.value
                    };
                    ws.send(JSON.stringify(command));
                    input.value = '';
                    messages.scrollTop = messages.scrollHeight;
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


if __name__ == "__main__":
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)