def health() -> dict[str, str]:
    """Fusion add-in readiness probe."""
    return {
        "status": "ok",
        "service": "mcp-addin",
    }
