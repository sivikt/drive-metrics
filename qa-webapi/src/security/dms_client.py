from typing import Any, Dict, Optional

import requests


def authorize(base_url: str, jwt_token: str = None) -> Optional[Dict[str, Any]]:
    """Returns:
        `dict` containing User properties if token is valid, `None` otherwise.
    """
    token_validation_path = base_url + f'/auth/token/{jwt_token}'

    r = requests.get(token_validation_path, headers={'Authorization': f'Bearer {jwt_token}'})

    if r.status_code == 400:
        return None
    r.raise_for_status()

    return r.json()
