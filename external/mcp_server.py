import httpx
import os
from mcp.server import FastMCP
from typing import Optional, List

# Create MCP server instance
mcp = FastMCP("next-gen-sales-service")

# Backend configuration
JAVA_BACKEND_URL = os.environ.get("SALES_API_URL", "http://localhost:8080")


# --- Utility: async request helper ---
async def call_java_backend(endpoint: str, method="GET", params=None, data=None):
    """Asynchroniczne wywołanie backend API"""
    url = f"{JAVA_BACKEND_URL}/{endpoint}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                res = await client.get(url, params=params)
            elif method == "POST":
                res = await client.post(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")

            res.raise_for_status()
            return res.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": "Not found", "status_code": 404}
        return {"error": f"HTTP {e.response.status_code}: {str(e)}", "status_code": e.response.status_code}
    except Exception as e:
        return {"error": str(e)}


# --- Formatting helpers ---
def format_customer_info(customer_data: dict) -> str:
    """Formatuje dane klienta do czytelnej formy"""
    if "error" in customer_data:
        return f"❌ {customer_data['error']}"
    
    info = f"""
📋 Informacje o kliencie:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 Imię i nazwisko: {customer_data.get('firstName', '')} {customer_data.get('lastName', '')}
📧 Email: {customer_data.get('email', 'brak')}
🆔 PESEL: {customer_data.get('pesel', 'brak')}
🔑 ID klienta: {customer_data.get('id', 'brak')}
📊 Status: {customer_data.get('status', 'nieznany')}
👥 Typ: {customer_data.get('type', 'nieznany')}

"""
    
    services = customer_data.get('services', [])
    if services:
        info += f"📦 Aktywne usługi ({len(services)}):\n"
        for idx, service in enumerate(services, 1):
            info += f"\n{idx}. {service.get('serviceName', 'Usługa')}\n"
            info += f"   ├─ Typ: {service.get('type', 'brak')}\n"
            info += f"   ├─ Status: {service.get('status', 'brak')}\n"
            
            if service.get('sim'):
                info += f"   ├─ SIM: {service.get('simNumber', 'brak')} ({service.get('simType', 'brak')})\n"
            
            components = service.get('components', [])
            if components:
                info += f"   └─ Komponenty ({len(components)}):\n"
                for comp in components:
                    info += f"      • {comp.get('name', 'brak')} - {comp.get('parameterValue', '')} {comp.get('parameterName', '')}\n"
    else:
        info += "📦 Brak aktywnych usług\n"
    
    return info


def format_catalog(catalog_data: list) -> str:
    """Formatuje katalog produktów do czytelnej formy"""
    if not catalog_data or isinstance(catalog_data, dict) and "error" in catalog_data:
        return "❌ Brak dostępnych produktów w katalogu"
    
    info = f"""
🛍️ Katalog dostępnych produktów ({len(catalog_data)}):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Grupuj po typach
    by_type = {}
    for item in catalog_data:
        item_type = item.get('type', 'Inne')
        if item_type not in by_type:
            by_type[item_type] = []
        by_type[item_type].append(item)
    
    for product_type, items in by_type.items():
        info += f"\n📱 {product_type.upper()}\n"
        info += "─" * 40 + "\n"
        
        for item in items:
            param_name = item.get('parameterName', '')
            param_value = item.get('parameterValue', '')
            price_min = item.get('priceMin', '0')
            price_max = item.get('priceMax', '0')
            
            info += f"\n• {param_value} {param_name}\n"
            
            if price_min == price_max:
                info += f"  💰 Cena: {price_min} PLN/mies\n"
            else:
                info += f"  💰 Cena: od {price_min} do {price_max} PLN/mies\n"
            
            info += f"  📊 Status: {item.get('status', 'nieznany')}\n"
            info += f"  🆔 ID: {item.get('id', 'brak')}\n"
    
    return info


def format_order_response(order_data: dict) -> str:
    """Formatuje odpowiedź po utworzeniu zamówienia"""
    if "error" in order_data:
        return f"❌ Błąd podczas tworzenia zamówienia: {order_data['error']}"
    
    info = f"""
✅ Zamówienie zostało pomyślnie utworzone!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆔 Numer zamówienia: {order_data.get('orderId', order_data.get('id', 'brak'))}
👤 ID klienta: {order_data.get('customerId', 'brak')}
📅 Data utworzenia: {order_data.get('createdAt', order_data.get('orderDate', 'brak'))}
📊 Status: {order_data.get('status', 'W trakcie realizacji')}

"""
    
    # Pokaż zamówione komponenty
    components = order_data.get('components', order_data.get('componentCatalogIds', []))
    if components:
        info += f"📦 Zamówione produkty:\n"
        if isinstance(components, list):
            if isinstance(components[0], dict):
                # Jeśli są to pełne obiekty
                for idx, comp in enumerate(components, 1):
                    info += f"   {idx}. {comp.get('name', 'Produkt')} (ID: {comp.get('id', 'brak')})\n"
            else:
                # Jeśli są to tylko ID
                for idx, comp_id in enumerate(components, 1):
                    info += f"   {idx}. Produkt ID: {comp_id}\n"
    
    info += "\n🎉 Dziękujemy za zamówienie! Wkrótce skontaktujemy się w sprawie realizacji."
    
    return info


# --- MCP Tools (exposed functions) ---

@mcp.tool()
async def check_customer(pesel: str) -> str:
    """
    Sprawdza dane klienta i jego aktywne usługi po numerze PESEL.
    
    Args:
        pesel: Numer PESEL klienta (11 cyfr)
    
    Returns:
        Sformatowane informacje o kliencie i jego usługach (zawiera ID klienta potrzebne do zamówienia)
    """
    customer_data = await call_java_backend("customer", params={"pesel": pesel})
    return format_customer_info(customer_data)


@mcp.tool()
async def get_product_catalog(product_type: Optional[str] = None) -> str:
    """
    Pobiera katalog dostępnych produktów Play.
    
    Args:
        product_type: Typ produktu do filtrowania (MOBILE, INTERNET, TV) - opcjonalnie
    
    Returns:
        Sformatowany katalog produktów z cenami i szczegółami (zawiera ID produktów)
    """
    params = {}
    if product_type:
        params["type"] = product_type.upper()
    
    catalog_data = await call_java_backend("component-catalog", params=params)
    
    if isinstance(catalog_data, dict) and "error" in catalog_data:
        return f"❌ Błąd pobierania katalogu: {catalog_data['error']}"
    
    return format_catalog(catalog_data)


@mcp.tool()
async def create_order(customer_id: int, component_catalog_ids: List[int]) -> str:
    """
    Tworzy nowe zamówienie dla klienta.
    
    Args:
        customer_id: ID klienta (pobierz z check_customer)
        component_catalog_ids: Lista ID produktów z katalogu (pobierz z get_product_catalog)
    
    Returns:
        Potwierdzenie utworzenia zamówienia z numerem
    
    Example:
        customer_id=123, component_catalog_ids=[5, 12] 
        tworzy zamówienie na produkty o ID 5 i 12 dla klienta 123
    """
    order_data = {
        "customerId": customer_id,
        "componentCatalogIds": component_catalog_ids
    }
    
    result = await call_java_backend("order", method="POST", data=order_data)
    return format_order_response(result)