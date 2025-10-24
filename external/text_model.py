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

DOSTĘPNE NARZĘDZIA MCP:
Możesz używać następujących narzędzi poprzez specjalną składnię:

1. [CHECK_CUSTOMER: pesel]
   Przykład: [CHECK_CUSTOMER: 85010112345]
   Sprawdza dane klienta i jego usługi po PESEL

2. [GET_CATALOG: typ]
   Przykład: [GET_CATALOG: MOBILE] lub [GET_CATALOG: ALL]
   Pobiera katalog produktów (MOBILE, INTERNET, TV lub ALL dla wszystkich)

Zasady:
- Bądź uprzejmy i profesjonalny
- Zadawaj pytania, aby zrozumieć potrzeby klienta
- Jeśli klient podaje PESEL, ZAWSZE najpierw sprawdź jego usługi używając [CHECK_CUSTOMER: pesel]
- Pokazuj katalog produktów używając [GET_CATALOG: typ]
- Kalkuluj cenę przed utworzeniem zamówienia używając [CALCULATE_PRICE: ids]
- Zawsze potwierdzaj wszystkie dane przed utworzeniem zamówienia
- Używaj emoji dla lepszej komunikacji 😊

Workflow:
1. Zapytaj o potrzeby klienta (internet, TV, telefon?)
2. Jeśli klient podaje PESEL - użyj [CHECK_CUSTOMER: pesel]
3. Użyj [GET_CATALOG: typ] aby pokazać oferty
4. Pomóż wybrać odpowiednie pakiety

WAŻNE: 
- Formatuj odpowiedzi czytelnie
- Używaj narzędzi gdy to konieczne (zapisuj je DOKŁADNIE jak w przykładach)
- Nigdy nie wymyślaj danych - zawsze pytaj klienta
- Po wykonaniu narzędzia, przeanalizuj wynik i odpowiedz klientowi
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
            
            # [GET_CATALOG: type]
            elif command.startswith("[GET_CATALOG:"):
                catalog_type = command[13:-1].strip()
                if catalog_type.upper() == "ALL":
                    catalog_type = None
                return await get_product_catalog(catalog_type)
            
            else:
                return f"❌ Nieznana komenda: {command}"
                
        except json.JSONDecodeError as e:
            return f"❌ Błąd parsowania JSON: {str(e)}"
        except Exception as e:
            return f"❌ Błąd wykonania narzędzia: {str(e)}"
    
    async def _process_response_with_tools(self, text: str, stream_callback=None) -> str:
        """Przetwarza odpowiedź i wykonuje narzędzia MCP jeśli są w tekście"""
        
        # Szukaj komend narzędzi w odpowiedzi
        tool_pattern = r'\[(CHECK_CUSTOMER|GET_CATALOG):[^\]]+\]'
        tools_found = re.findall(tool_pattern, text, re.IGNORECASE)
        
        if not tools_found:
            return text
        
        # Znajdź pełne komendy
        full_commands = re.findall(r'\[(?:CHECK_CUSTOMER|GET_CATALOG):[^\]]+\]', text, re.IGNORECASE)
        
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
            HumanMessage(content=f"TOOL_RESULTS:\n{tool_results_text}\n\nNa podstawie powyższych wyników, sformułuj pomocną odpowiedź dla klienta. NIE używaj już więcej narzędzi, tylko przeanalizuj wyniki.")
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
        
        # Check if response contains tool commands
        tool_pattern = r'\[(?:CHECK_CUSTOMER|GET_CATALOG):[^\]]+\]'
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