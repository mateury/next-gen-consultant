"""
Logging utilities for the Play virtual consultant API.
"""

import json
from datetime import datetime


def log_colored(emoji: str, message: str, data=None):
    """
    Kolorowe logowanie z timestampem.
    
    Args:
        emoji: Emoji do wyświetlenia
        message: Wiadomość do zalogowania
        data: Opcjonalne dane do wyświetlenia (dict, list, lub string)
    """
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
    """
    Wyświetl szczegółową historię konwersacji.
    
    Args:
        session_id: ID sesji
        history: Lista wiadomości z historii
        stats: Opcjonalne statystyki (dict)
    """
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


def log_streaming_progress(chunk_count: int, total_length: int):
    """
    Loguj progress streamingu.
    
    Args:
        chunk_count: Liczba wysłanych chunków
        total_length: Całkowita długość tekstu
    """
    if chunk_count % 20 == 0:
        print(f"  📊 Streaming: {chunk_count} chunks | {total_length} chars")