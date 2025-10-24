import requests
from mcp.server import FastMCP

JAVA_BACKEND_URL = "http://localhost:8080/"

# Create MCP server instance
mcp = FastMCP("next-gen-sales-service")


# --- Utility: request helper ---
def call_java_backend(endpoint: str, method="GET", params=None, data=None):
    url = f"{JAVA_BACKEND_URL}/{endpoint}"
    try:
        if method == "GET":
            res = requests.get(url, params=params)
        elif method == "POST":
            res = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        res.raise_for_status()
        return res.json()
    except Exception as e:
        return {"error": str(e)}


# --- MCP Tools (exposed functions) ---

@mcp.tool()
async def get_customer_by_pesel(pesel: int) -> dict:
    return call_java_backend("customer", params={"pesel": pesel})
