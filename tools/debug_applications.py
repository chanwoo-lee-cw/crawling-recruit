import json
from services.wanted.wanted_client import WantedClient


def debug_applications() -> str:
    client = WantedClient()
    try:
        result = client.debug_applications_response()
    except (PermissionError, ValueError) as e:
        return str(e)
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)
