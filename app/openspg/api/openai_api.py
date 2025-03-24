import json
import logging
import time
import uuid
from typing import Optional, List, Literal, Union, Generator

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.authz.authorize import authenticate
from app.openspg.service.kag_service import get_kag_service


class ModelCard(BaseModel):
    id: str
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "owner"
    root: Optional[str] = None
    parent: Optional[str] = None
    permission: Optional[list] = None


class ModelList(BaseModel):
    object: str = "list"
    data: List[ModelCard] = None


class ChatMessage(BaseModel):
    role: Literal['user', 'assistant', 'system', 'function']
    content: str = None
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.8
    top_p: Optional[float] = 0.8
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    tools: Optional[Union[dict, List[dict]]] = None
    repetition_penalty: Optional[float] = 1.1


class DeltaMessage(BaseModel):
    role: Optional[Literal["user", "assistant", "system"]] = None
    content: Optional[str] = None


class ChatCompletionResponseStreamChoice(BaseModel):
    delta: DeltaMessage
    finish_reason: Optional[Literal["stop", "length", "function_call"]]
    index: int


class ChatCompletionResponse(BaseModel):
    model: str
    id: str
    object: Literal["chat.completion", "chat.completion.chunk"]
    choices: List[Union[ChatCompletionResponseStreamChoice]]
    created: Optional[int] = Field(default_factory=lambda: int(time.time()))


def mount_routes(app: FastAPI, args):
    api_prefix = f'{args.servlet}/openai'
    api_tag = 'OpenAI'
    model_category = 'openspg'

    service = get_kag_service(args.openspg_service, args.openspg_modules)

    @app.get(f'{api_prefix}/v1/models', response_model=ModelList, tags=[api_tag], summary='Model List')
    async def list_models():
        projects = service.get_projects()
        return ModelList(
            data=[ModelCard(id=f'{model_category}/{x}') for x in projects.keys()]
        )

    @app.post(f'{api_prefix}/v1/chat/completions', response_model=ChatCompletionResponse, tags=[api_tag],
              summary='Chat Completions')
    async def create_chat_completion(request: ChatCompletionRequest,
                                     api_key: str = Depends(authenticate)) -> EventSourceResponse:
        logging.info(f'request by: {api_key}')
        if len(request.messages) < 1 or request.messages[-1].role != "user":
            raise HTTPException(status_code=400, detail=f'Invalid messages: {request.messages}')

        model_id = request.model

        if not model_id.startswith(f'{model_category}/'):
            raise ValueError(f'Invalid model id: {model_id}')

        project_name = model_id[(len(model_category) + 1):]
        project_id = service.get_project_id_by_name(project_name)
        if not project_id:
            raise ValueError(f'Project {project_name} not found')

        query = request.messages[-1].content

        def build_chat_completion_response(content: any, message_id='', finish_reason=None):
            choice = ChatCompletionResponseStreamChoice(
                index=0,
                delta=DeltaMessage(
                    role="assistant",
                    content=content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
                ),
                finish_reason=finish_reason
            )
            chunk = ChatCompletionResponse(
                model=model_id,
                id=message_id,
                choices=[choice],
                object='chat.completion.chunk'
            )
            return '{}'.format(chunk.model_dump_json(exclude_unset=True, exclude_none=True))

        def stream_generate():
            message_id = f'chat-{str(uuid.uuid4()).replace("-", "")}'
            event_queue = service.query(query, project_id)
            for event in event_queue:
                if isinstance(event, Generator):
                    for x in event:
                        yield build_chat_completion_response(x, message_id=message_id)
                elif event:
                    yield build_chat_completion_response(content=event, message_id=message_id)

            yield build_chat_completion_response(content='', message_id=message_id, finish_reason='stop')
            yield '[DONE]'

        return EventSourceResponse(stream_generate(), media_type="text/event-stream")

    pass
