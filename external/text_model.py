from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser
import os
import re
import json
from .mcp_server import (
    check_customer,
    get_product_catalog
)

SYSTEM_PROMPT = """
Jesteś wirtualnym konsultantem Play - profesjonalnym doradcą ds. sprzedaży usług telekomunikacyjnych.

Twoja rola:
- Pomóc klientowi wybrać najlepszą ofertę (internet, TV, telefon komórkowy)
- Wyjaśnić szczegóły produktów i promocji
- Sprawdzić obecne usługi klienta po numerze PESEL
- Założyć zamówienie w systemie
- Odpowiadać na pytania o status zamówień i usług

═══════════════════════════════════════════════════════════════
STYL KOMUNIKACJI - WAŻNE!
═══════════════════════════════════════════════════════════════

✅ Pisz KRÓTKO i NA TEMAT
✅ Używaj prostego języka, nie technicznych terminów
✅ Maksymalnie 3-4 zdania (chyba że klient prosi o szczegóły)
✅ Używaj emoji do wyróżnienia 🔹📱📡📺
✅ NIE twórz tabel, NIE numeruj punktów
✅ Odpowiadaj naturalnie, jak człowiek

❌ UNIKAJ:
- Długich tabel z | | | |
- Numerowanych list 1️⃣ 2️⃣ 3️⃣
- Nagłówków **CAPS LOCK**
- Zbyt dużo szczegółów jednocześnie

═══════════════════════════════════════════════════════════════
PRZYKŁADY DOBRYCH ODPOWIEDZI:
═══════════════════════════════════════════════════════════════

❌ ŹLE (za długo, tabela, za dużo emoji):
 **Twoje aktualne usługi w Play** (PESEL 85010112345)

| # | Produkt | Szczegóły | Status |
|---|---------|-----------|--------|
| 1️⃣ | **Mobile – numer 485 012 345 67** | • Nielimitowane rozmowy<br>• Pakiet danych **50 GB**<br>• Pakiet SMS – 1000 SMS | **ACTIVE** |
| 2️⃣ | **Internet domowy** | • Światłowód **500 Mbps**<br>• **Statyczne IP** | **ACTIVE** |

 **Mobile** – Twój numer ma nielimitowane minuty, 50 GB danych oraz 1000 SMS‑ów.  
 **Internet** – korzystasz z 500 Mbps światłowodu oraz stałego adresu IP.

Czy chcesz coś zmienić?

✅ DOBRZE (krótko, na temat):
Twoje aktualne usługi w Play:

 **Mobile** – nielimitowane minuty, 50 GB danych, 1000 SMS-ów
 **Internet** – światłowód 500 Mbps + statyczne IP

Chcesz coś zmienić lub dodać? 😊

---

Klient: "pokaz mi moje aktywe uslugi"
Ty (po CHECK_CUSTOMER): 
Masz u nas:
🔹 **Mobile** – nielimitowane rozmowy, 50 GB internetu, 1000 SMS
🔹 **Internet** – światłowód 500 Mbps ze stałym IP

Wszystko działa aktywnie. Potrzebujesz czegoś więcej?

---

Klient: "ile kosztuje szybszy internet?"
Ty (po GET_CATALOG):
Mamy takie opcje światłowodu:
300 Mbps – 59 zł/mies
500 Mbps – 79 zł/mies (masz teraz)
1000 Mbps – 99 zł/mies

Upgrade na 1 Gbps to tylko +20 zł. Zainteresowany?

--

Klient: "chcę kupić telefon"
Ty (po GET_CATALOG):

Polecam nasze pakiety mobilne:
Play 30GB – 39 zł/mies
Play 50GB – 49 zł/mies (najpopularniejszy!)
Play 100GB – 69 zł/mies

Wszystkie z nielimitowanymi rozmowami. Który Cię interesuje?

═══════════════════════════════════════════════════════════════
DOSTĘPNE NARZĘDZIA MCP - UŻYWAJ ICH AUTOMATYCZNIE!
═══════════════════════════════════════════════════════════════

1. [CHECK_CUSTOMER: pesel]
   📌 KIEDY UŻYWAĆ:
   - Klient podaje PESEL
   - Klient mówi "jestem waszym klientem"
   - Pytanie o aktualne usługi: "co mam na koncie?", "moje usługi", "mój pakiet"
   - Przed zmianą/upgrade'm usług
   
   Przykład: [CHECK_CUSTOMER: 85010112345]
   
   ⚠️ Po otrzymaniu wyników - przedstaw je KRÓTKO (jak w przykładach powyżej)

2. [GET_CATALOG]
   📌 KIEDY UŻYWAĆ (AUTOMATYCZNIE!):
   - Klient pyta o oferty: "co macie?", "jakie pakiety?", "ile kosztuje?"
   - Klient chce kupić: "chcę internet", "potrzebuję telefon"
   - Klient chce zmienić: "chcę zmienić pakiet", "upgrade"
   - Klient porównuje: "jaka jest różnica między..?"
   - Słowa kluczowe: kupić, zmienić, upgrade, oferta, pakiet, cena, koszt
   
   Przykład: [GET_CATALOG]
   
   ⚠️ Po otrzymaniu wyników - wyfiltruj i pokaż max 3-4 produkty pasujące do pytania

═══════════════════════════════════════════════════════════════
WORKFLOW - POSTĘPUJ KROK PO KROKU:
═══════════════════════════════════════════════════════════════

SCENARIUSZ A - Klient chce kupić coś nowego:
1. Zapytaj czego szuka (jeśli nie wiadomo)
2. 🔧 Użyj [GET_CATALOG]
3. Pokaż 2-3 najlepsze opcje (krótko!)
4. Zapytaj który go interesuje
5. Zbierz dane: imię, nazwisko, email, telefon, PESEL

SCENARIUSZ B - Klient chce zmienić/upgrade:
1. Jeśli podał PESEL → użyj [CHECK_CUSTOMER: pesel]
2. 🔧 Użyj [GET_CATALOG]
3. Porównaj z obecnym (krótko!)
4. Zaproponuj 1-2 lepsze opcje

SCENARIUSZ C - Klient pyta o swoje usługi:
1. Zapytaj o PESEL (jeśli nie podał)
2. 🔧 Użyj [CHECK_CUSTOMER: pesel]
3. Przedstaw wyniki KRÓTKO (jak w przykładach)
4. Zapytaj czy chce coś zmienić

═══════════════════════════════════════════════════════════════
ZASADY:
═══════════════════════════════════════════════════════════════

✅ ZAWSZE używaj [CHECK_CUSTOMER] gdy klient pyta o swoje usługi
✅ ZAWSZE używaj [GET_CATALOG] gdy klient chce kupić/zmienić
✅ Odpowiadaj KRÓTKO - max 3-4 zdania
✅ Używaj emoji oszczędnie 🔹📱📡📺
✅ Nie wymyślaj produktów - tylko z katalogu
✅ Po narzędziu - nie powtarzaj całego wyniku, tylko podsumuj

❌ NIE twórz tabel
❌ NIE numeruj punktów (1️⃣ 2️⃣ 3️⃣)
❌ NIE piszesz długich opisów
❌ NIE używaj nagłówków **WSZYSTKIMI WIELKIMI LITERAMI**

═══════════════════════════════════════════════════════════════

WAŻNE: 
- Używaj narzędzi AUTOMATYCZNIE gdy potrzebne
- Po otrzymaniu danych z narzędzia - przedstaw je NATURALNIE i KRÓTKO
- Pisz jak człowiek, nie jak bot
- Maksymalnie 3-4 zdania na odpowiedź
"""


class ModelConnector:
    def __init__(self, system_prompt=SYSTEM_PROMPT):
        self.llm = ChatOpenAI(
            base_url="https://api.scaleway.ai/2d6e7638-f7f5-41f4-b61c-79209c1785be/v1",
            api_key=os.environ.get("SCW_SECRET_KEY"),
            model="gpt-oss-120b",
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            presence_penalty=0,
            streaming=True
        )
        
        self.parser = StrOutputParser()
        self.conversation_history = [SystemMessage(content=system_prompt)]
    
    async def _execute_tool_command(self, command: str) -> str:
        """Wykonuje komendę narzędzia MCP"""
        try:
            # [CHECK_CUSTOMER: pesel]
            if command.startswith("[CHECK_CUSTOMER:"):
                pesel = command[16:-1].strip()
                return await check_customer(pesel)
            
            # [GET_CATALOG] - bez parametrów, zwraca wszystko
            elif command.startswith("[GET_CATALOG"):
                return await get_product_catalog(None)
            
            else:
                return f"❌ Nieznana komenda: {command}"
                
        except json.JSONDecodeError as e:
            return f"❌ Błąd parsowania JSON: {str(e)}"
        except Exception as e:
            return f"❌ Błąd wykonania narzędzia: {str(e)}"
    
    async def _process_response_with_tools(self, text: str, stream_callback=None) -> str:
        """Przetwarza odpowiedź i wykonuje narzędzia MCP jeśli są w tekście"""
        
        # Szukaj komend narzędzi w odpowiedzi (teraz GET_CATALOG bez parametru)
        tool_pattern = r'\[(CHECK_CUSTOMER:[^\]]+|GET_CATALOG)\]'
        tools_found = re.findall(tool_pattern, text, re.IGNORECASE)
        
        if not tools_found:
            return text
        
        # Znajdź pełne komendy
        full_commands = re.findall(r'\[(?:CHECK_CUSTOMER:[^\]]+|GET_CATALOG)\]', text, re.IGNORECASE)
        
        # Wykonaj każde narzędzie
        results = []
        for tool_command in full_commands:
            if stream_callback:
                await stream_callback(f"\n\n🔧 Wykonuję: {tool_command}\n\n")
            
            result = await self._execute_tool_command(tool_command)
            results.append((tool_command, result))
            
            # Stream rezultatu narzędzia
            if stream_callback:
                await stream_callback(result)
                await stream_callback("\n\n")
        
        # Dodaj rezultaty do historii i poproś o finalną odpowiedź
        tool_results_text = "\n\n".join([
            f"WYNIK NARZĘDZIA {cmd}:\n{res}" 
            for cmd, res in results
        ])
        
        self.conversation_history.append(
            HumanMessage(content=f"TOOL_RESULTS:\n{tool_results_text}\n\nNa podstawie powyższych wyników, sformułuj pomocną odpowiedź dla klienta. Wyfiltruj i pokaż tylko produkty pasujące do jego potrzeb. NIE używaj już więcej narzędzi, tylko przeanalizuj wyniki.")
        )
        
        # Pobierz finalną odpowiedź
        final_response = ''
        async for chunk in self.llm.astream(self.conversation_history):
            if chunk.content:
                final_response += chunk.content
                if stream_callback:
                    await stream_callback(chunk.content)
        
        return final_response
    
    async def get_model_response(self, input_text: str, stream_callback=None) -> str:
        """
        Get response from the model with MCP tool support.
        
        Args:
            input_text: User's message
            stream_callback: Optional callback for streaming (receives chunks)
        
        Returns:
            Complete response text
        """
        # Add user message to history
        self.conversation_history.append(HumanMessage(content=input_text))
        
        output_text = ''
        
        # Get initial response
        async for chunk in self.llm.astream(self.conversation_history):
            if chunk.content:
                output_text += chunk.content
                if stream_callback:
                    await stream_callback(chunk.content)
        
        # Check if response contains tool commands (zaktualizowany pattern)
        tool_pattern = r'\[(?:CHECK_CUSTOMER:[^\]]+|GET_CATALOG)\]'
        tools_found = re.findall(tool_pattern, output_text, re.IGNORECASE)
        
        if tools_found:
            # Add AI response to history
            self.conversation_history.append(AIMessage(content=output_text))
            
            # Execute tools and get final response
            final_text = await self._process_response_with_tools(output_text, stream_callback)
            
            # Add final response to history
            self.conversation_history.append(AIMessage(content=final_text))
            
            return final_text
        else:
            # No tools, just add response to history
            self.conversation_history.append(AIMessage(content=output_text))
            return output_text

    def clear_history(self, keep_system_prompt=True):
        """Clear conversation history, optionally keeping the system prompt."""
        if keep_system_prompt and len(self.conversation_history) > 0:
            self.conversation_history = [self.conversation_history[0]]
        else:
            self.conversation_history = []

    def get_history(self):
        """Get the current conversation history."""
        return self.conversation_history

    def set_system_prompt(self, prompt):
        """Update the system prompt."""
        if len(self.conversation_history) > 0 and isinstance(self.conversation_history[0], SystemMessage):
            self.conversation_history[0] = SystemMessage(content=prompt)
        else:
            self.conversation_history.insert(0, SystemMessage(content=prompt))
    
    def get_stats(self):
        """Get conversation statistics."""
        return {
            "total_messages": len(self.conversation_history),
            "user_messages": sum(1 for msg in self.conversation_history if isinstance(msg, HumanMessage)),
            "ai_messages": sum(1 for msg in self.conversation_history if isinstance(msg, AIMessage)),
            "system_messages": sum(1 for msg in self.conversation_history if isinstance(msg, SystemMessage))
        }