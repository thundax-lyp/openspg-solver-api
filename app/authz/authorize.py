import json
import logging
import os
from typing import List, Set

from fastapi import Header, HTTPException

AUTHORIZATION_FILENAME = os.path.join(os.path.dirname(__file__), "api_keys.json")


def load_api_keys() -> List[str]:
    try:
        with open(AUTHORIZATION_FILENAME, "r") as f:
            data = json.load(f)
        return [str(x) for x in data.values()]
    except Exception as e:
        logging.info(f"Failed to load API keys: {e}")
        return []


API_KEYS: Set[str] = set(load_api_keys())


async def authenticate(api_key: str = Header(..., alias="Authorization")):
    if len(API_KEYS) == 0:
        return 'none'

    if api_key and api_key.startswith('Bearer\x20'):
        api_key = ''.join(api_key.split('\x20')[1:])

    if api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Unauthorized access")

    return api_key
