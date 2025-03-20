import json
from typing import Any, Mapping, Optional

from fastapi.responses import Response
from starlette.background import BackgroundTask

from app.utils import remove_empty_fields


class JSONEncode(json.JSONEncoder):

    def default(self, o):
        return super().default(o)


class JSONResponse(Response):
    media_type = "application/json"

    def __init__(
            self,
            content: Any,
            status_code: int = 200,
            headers: Optional[Mapping[str, str]] = None,
            media_type: Optional[str] = None,
            background: Optional[BackgroundTask] = None,
    ) -> None:
        super().__init__(content, status_code, headers, media_type, background)

    def render(self, content: Any) -> bytes:
        return json.dumps(
            remove_empty_fields(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=JSONEncode
        ).encode("utf-8")
