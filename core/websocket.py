"""
WebSocket connection handler for Play virtual consultant.
"""

from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import traceback

from .logging import log_colored, log_history, log_streaming_progress
from .session import SessionManager


class WebSocketHandler:
    """Handles WebSocket connections and message processing."""
    
    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager
    
    async def handle_connection(self, websocket: WebSocket):
        """
        Handle a WebSocket connection lifecycle.
        
        Args:
            websocket: FastAPI WebSocket instance
        """
        await websocket.accept()
        
        # Create unique session
        session_id = str(id(websocket))
        mc = self.session_manager.create_session(session_id)
        
        log_colored("🟢", "NOWE POŁĄCZENIE", {
            "session_id": session_id,
            "client": str(websocket.client),
            "total_sessions": self.session_manager.get_active_count()
        })
        
        # Send welcome message
        await self._send_welcome(websocket, session_id, mc)
        
        try:
            # Main message loop
            await self._message_loop(websocket, session_id, mc)
            
        except WebSocketDisconnect:
            await self._handle_disconnect(session_id)
            
        except Exception as e:
            await self._handle_error(websocket, session_id, e)
    
    async def _send_welcome(self, websocket: WebSocket, session_id: str, mc):
        """Send welcome message to client."""
        welcome_msg = "Cześć! Jestem wirtualnym konsultantem Play. W czym mogę Ci dziś pomóc? 😊"
        
        await websocket.send_json({
            "type": "message",
            "content": welcome_msg
        })
        
        log_colored("📤", "WYSŁANO POWITANIE", {
            "session_id": session_id,
            "message": welcome_msg
        })
        
        log_history(session_id, mc.get_history(), mc.get_stats())
    
    async def _message_loop(self, websocket: WebSocket, session_id: str, mc):
        """Main message processing loop."""
        while True:
            # Receive message
            message = await websocket.receive_text()
            
            if not message.strip():
                log_colored("⚠️", "OTRZYMANO PUSTĄ WIADOMOŚĆ", {"session_id": session_id})
                continue
            
            log_colored("📨", "OTRZYMANO WIADOMOŚĆ OD UŻYTKOWNIKA", {
                "session_id": session_id,
                "message": message,
                "length": len(message)
            })
            
            # Log history before processing
            print("\n" + "━"*80)
            print("📖 HISTORIA PRZED PRZETWORZENIEM:")
            print("━"*80)
            log_history(session_id, mc.get_history(), mc.get_stats())
            
            try:
                # Process message with streaming
                await self._process_message(websocket, session_id, mc, message)
                
            except Exception as api_error:
                await self._handle_api_error(websocket, session_id, message, api_error)
    
    async def _process_message(self, websocket: WebSocket, session_id: str, mc, message: str):
        """Process user message with AI model."""
        # Start streaming to client
        await websocket.send_json({
            "type": "stream_start",
            "content": ""
        })
        
        # Client streaming callback
        chunk_count = 0
        total_length = 0
        chunks_preview = []
        client_message_started = False
        
        async def stream_to_client(chunk: str):
            """Stream chunks to the client."""
            nonlocal chunk_count, total_length, chunks_preview, client_message_started
            
            # Skip tool command text from being sent to client
            if chunk.startswith("[") and ("CHECK_CUSTOMER" in chunk or "GET_CATALOG" in chunk or "CREATE_ORDER" in chunk):
                return
            
            chunk_count += 1
            total_length += len(chunk)
            
            # Save first 5 chunks for preview
            if chunk_count <= 5:
                chunks_preview.append(chunk)
            
            # Send chunk to client
            await websocket.send_json({
                "type": "stream_chunk",
                "content": chunk
            })
            client_message_started = True
            
            # Log progress every 20 chunks
            log_streaming_progress(chunk_count, total_length)
        
        # Internal logging callback (doesn't go to client)
        internal_logs = []
        
        async def log_internal(message: str):
            """Log internal operations (tool execution, etc)."""
            internal_logs.append(message)
            print(f"  🔧 {message}", end='', flush=True)
        
        log_colored("⚙️", "ROZPOCZYNAM PRZETWARZANIE", {
            "session_id": session_id,
            "model": "gpt-oss-120b (Scaleway)",
            "streaming": True,
            "user_message": message
        })
        
        # Process with model
        start_time = datetime.now()
        response = await mc.get_model_response(
            message, 
            stream_callback=stream_to_client,
            internal_callback=log_internal
        )
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # End streaming to client
        await websocket.send_json({
            "type": "stream_end",
            "content": ""
        })
        
        log_colored("✅", "ZAKOŃCZONO PRZETWARZANIE", {
            "session_id": session_id,
            "chunks_sent_to_client": chunk_count,
            "total_client_length": total_length,
            "duration_seconds": round(duration, 2),
            "chars_per_second": round(total_length / duration, 2) if duration > 0 else 0,
            "internal_operations": len(internal_logs),
            "first_chunks": "".join(chunks_preview[:3])
        })
        
        # Log internal operations
        if internal_logs:
            print("\n" + "─"*80)
            print("🔧 OPERACJE WEWNĘTRZNE (nie widoczne dla klienta):")
            for log in internal_logs:
                print(f"  • {log.strip()}")
            print("─"*80)
        
        # Log history after processing
        print("\n" + "━"*80)
        print("📖 HISTORIA PO PRZETWORZENIU:")
        print("━"*80)
        log_history(session_id, mc.get_history(), mc.get_stats())
        
        # Log full AI response
        log_colored("🤖", "ODPOWIEDŹ AI (pełna - klient widzi tylko końcówkę)", {
            "session_id": session_id,
            "response_preview": response[:300] + "..." if len(response) > 300 else response,
            "full_length": len(response),
            "client_visible_length": total_length,
            "has_tool_commands": any(cmd in response for cmd in ["[CHECK_CUSTOMER:", "[GET_CATALOG:", "[CREATE_ORDER:"])
        })
    
    async def _handle_api_error(self, websocket: WebSocket, session_id: str, message: str, error: Exception):
        """Handle API errors during message processing."""
        log_colored("❌", "BŁĄD API", {
            "session_id": session_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "user_message": message
        })
        
        error_message = f"⚠️ Przepraszam, wystąpił problem z połączeniem. Spróbuj ponownie za chwilę.\n\nBłąd: {type(error).__name__}"
        
        await websocket.send_json({
            "type": "error",
            "content": error_message
        })
        
        print("📍 Stack trace:")
        traceback.print_exc()
    
    async def _handle_disconnect(self, session_id: str):
        """Handle client disconnect."""
        final_history, final_stats = self.session_manager.delete_session(session_id)
        
        if final_history:
            log_colored("🔴", "ROZŁĄCZONO KLIENTA", {
                "session_id": session_id,
                "final_stats": final_stats,
                "remaining_sessions": self.session_manager.get_active_count()
            })
            
            print("\n" + "━"*80)
            print("📖 OSTATECZNA HISTORIA PRZED ROZŁĄCZENIEM:")
            print("━"*80)
            log_history(session_id, final_history, final_stats)
    
    async def _handle_error(self, websocket: WebSocket, session_id: str, error: Exception):
        """Handle unexpected errors."""
        log_colored("💥", "NIEOCZEKIWANY BŁĄD", {
            "session_id": session_id,
            "error_type": type(error).__name__,
            "error_message": str(error)
        })
        
        self.session_manager.delete_session(session_id)
        
        print("📍 Stack trace:")
        traceback.print_exc()