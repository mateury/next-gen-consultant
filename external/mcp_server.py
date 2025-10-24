import httpx
import os
from mcp.server import FastMCP
from typing import Optional, List
from datetime import datetime

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
def format_date(date_str: str) -> str:
    """Formatuje datę z ISO do czytelnej formy"""
    try:
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%d.%m.%Y')
        return date_str
    except:
        return date_str


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
    
    # Parsuj rzeczywiste pola z odpowiedzi
    order_id = order_data.get('id', 'brak')
    customer_id = order_data.get('customerId', 'brak')
    status = order_data.get('status', 'NEW')
    create_date = order_data.get('createDate', 'brak')
    
    # Status po polsku
    status_pl = {
        'NEW': 'Nowe',
        'PENDING': 'W trakcie',
        'PROCESSING': 'Przetwarzane',
        'COMPLETED': 'Zrealizowane',
        'CANCELLED': 'Anulowane'
    }.get(status, status)
    
    info = f"""
✅ Zamówienie zostało pomyślnie utworzone!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🆔 Numer zamówienia: {order_id}
👤 ID klienta: {customer_id}
📅 Data utworzenia: {format_date(str(create_date))}
📊 Status: {status_pl}

"""
    
    # Pokaż zamówione produkty z orderItems
    order_items = order_data.get('orderItems', [])
    if order_items:
        info += f"📦 Zamówione produkty ({len(order_items)}):\n\n"
        for idx, item in enumerate(order_items, 1):
            component_name = item.get('componentCatalogName', 'Produkt')
            component_id = item.get('componentCatalogId', 'brak')
            item_status = item.get('status', 'NEW')
            item_status_pl = {
                'NEW': 'Nowy',
                'PENDING': 'W trakcie',
                'PROCESSING': 'Przetwarzany',
                'COMPLETED': 'Zrealizowany',
                'CANCELLED': 'Anulowany'
            }.get(item_status, item_status)
            
            info += f"   {idx}. {component_name}\n"
            info += f"      ├─ ID produktu: {component_id}\n"
            info += f"      ├─ Status: {item_status_pl}\n"
            info += f"      └─ ID pozycji: {item.get('id', 'brak')}\n\n"
    else:
        info += "📦 Brak pozycji w zamówieniu (błąd systemu)\n\n"
    
    info += "🎉 Dziękujemy za zamówienie! Wkrótce skontaktujemy się w sprawie realizacji."
    
    return info


def format_invoices(invoices_data: list) -> str:
    """Formatuje listę faktur do czytelnej formy"""
    if isinstance(invoices_data, dict) and "error" in invoices_data:
        return f"❌ Błąd pobierania faktur: {invoices_data['error']}"
    
    if not invoices_data:
        return "📄 Brak faktur do wyświetlenia."
    
    # Statystyki
    total_invoices = len(invoices_data)
    paid_count = sum(1 for inv in invoices_data if inv.get('status') == 'PAID')
    unpaid_count = sum(1 for inv in invoices_data if inv.get('status') == 'UNPAID')
    total_unpaid = sum(float(inv.get('priceGross', 0)) for inv in invoices_data if inv.get('status') == 'UNPAID')
    
    info = f"""
💰 Faktury klienta:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Wszystkich faktur: {total_invoices}
✅ Opłaconych: {paid_count}
⚠️ Nieopłaconych: {unpaid_count}
"""
    
    if unpaid_count > 0:
        info += f"💸 Suma do zapłaty: {total_unpaid:.2f} PLN\n"
    
    info += "\n"
    
    # Sortuj: najpierw nieopłacone, potem opłacone (od najnowszych)
    sorted_invoices = sorted(
        invoices_data, 
        key=lambda x: (x.get('status') != 'UNPAID', x.get('createDate', '')),
        reverse=True
    )
    
    for idx, invoice in enumerate(sorted_invoices, 1):
        inv_id = invoice.get('id', 'brak')
        status = invoice.get('status', 'UNKNOWN')
        price = invoice.get('priceGross', '0.00')
        start_date = format_date(invoice.get('billingPeriodStartDate', ''))
        end_date = format_date(invoice.get('billingPeriodEndDate', ''))
        create_date = format_date(invoice.get('createDate', ''))
        
        # Status i emoji
        if status == 'PAID':
            status_emoji = '✅'
            status_text = 'Opłacona'
        elif status == 'UNPAID':
            status_emoji = '⚠️'
            status_text = 'Nieopłacona'
        elif status == 'OVERDUE':
            status_emoji = '🔴'
            status_text = 'Po terminie'
        elif status == 'CANCELLED':
            status_emoji = '❌'
            status_text = 'Anulowana'
        else:
            status_emoji = '❓'
            status_text = status
        
        info += f"\n{idx}. {status_emoji} Faktura #{inv_id}\n"
        info += f"   ├─ Status: {status_text}\n"
        info += f"   ├─ Kwota: {price} PLN\n"
        info += f"   ├─ Okres rozliczeniowy: {start_date} - {end_date}\n"
        info += f"   └─ Data wystawienia: {create_date}\n"
    
    if unpaid_count > 0:
        info += f"\n⚠️ UWAGA: Masz {unpaid_count} nieopłaconą(ych) faktur(y) na kwotę {total_unpaid:.2f} PLN."
    else:
        info += "\n✅ Wszystkie faktury są opłacone!"
    
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


@mcp.tool()
async def check_invoices(customer_id: int) -> str:
    """
    Sprawdza faktury klienta i status płatności.
    
    Args:
        customer_id: ID klienta (pobierz z check_customer)
    
    Returns:
        Lista faktur ze statusami płatności i kwotami
    
    Example:
        customer_id=123 - sprawdza wszystkie faktury klienta o ID 123
    """
    invoices_data = await call_java_backend("invoices", params={"customerId": customer_id})
    return format_invoices(invoices_data)