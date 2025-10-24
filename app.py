from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
from external import text_model
from dotenv import load_dotenv

app = FastAPI()


# Simple text processing function
def process_text(text: str) -> str:
    mc = text_model.ModelConnector()
    model_responce = mc.get_model_response(text)
    return f"Processed: {model_responce}"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("Client connected")

    try:
        while True:
            # Receive text from client
            data = await websocket.receive_text()
            print(f"Received: {data}")

            # Process the text
            response = process_text(data)

            # Send response back to client
            await websocket.send_text(response)
            print(f"Sent: {response}")

    except WebSocketDisconnect:
        print("Client disconnected")


# HTML client for testing
@app.get("/")
async def get():
    html = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>WebSocket Test Client</title>
        </head>
        <body>
            <h1>WebSocket Text Processor</h1>
            <form id="form">
                <input type="text" id="messageText" autocomplete="off" placeholder="Enter text..."/>
                <button>Send</button>
            </form>
            <ul id="messages"></ul>

            <script>
                const ws = new WebSocket("ws://localhost:8000/ws");

                ws.onmessage = function(event) {
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "Server: " + event.data;
                    message.style.color = 'green';
                    messages.appendChild(message);
                };

                ws.onopen = function(event) {
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "Connected to server";
                    message.style.color = 'blue';
                    messages.appendChild(message);
                };

                ws.onclose = function(event) {
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "Disconnected from server";
                    message.style.color = 'red';
                    messages.appendChild(message);
                };

                document.getElementById('form').onsubmit = function(event) {
                    event.preventDefault();
                    const input = document.getElementById('messageText');
                    const messages = document.getElementById('messages');
                    const message = document.createElement('li');
                    message.textContent = "You: " + input.value;
                    messages.appendChild(message);

                    ws.send(input.value);
                    input.value = '';
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


if __name__ == "__main__":
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)