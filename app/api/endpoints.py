import asyncio

from fastapi import APIRouter, HTTPException
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from starlette.websockets import WebSocket, WebSocketDisconnect

from app.core.config import REDIS_URL
from app.core.model import load_llama3_model
from app.core.redis import get_redis_client
from app.models.chat_requests import ChatRequest

router = APIRouter()

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You're an assistant."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ]
)


runnable = prompt | load_llama3_model() | StrOutputParser()


def get_message_history(session_id: str) -> RedisChatMessageHistory:
    return RedisChatMessageHistory(session_id, url=REDIS_URL)


with_message_history = RunnableWithMessageHistory(
    runnable,
    get_message_history,
    input_messages_key="input",
    history_messages_key="history",
)


async def stream_response(websocket: WebSocket, response: str):
    for char in response:
        await websocket.send_text(char)
        await asyncio.sleep(0.05)

    await websocket.send_text("[DONE]")


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        result = with_message_history.invoke(
            {"input": request.input},
            config={"configurable": {"session_id": request.session_id}},
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            request = ChatRequest.model_validate_json(data)
            result = with_message_history.invoke(
                {"input": request.input},
                config={"configurable": {"session_id": request.session_id}},
            )

            for char in result:
                await websocket.send_text(char)
                await asyncio.sleep(0.05)
            await websocket.close()

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_text("[ERROR]")
        await websocket.close()


@router.delete("/delete_history/{session_id}")
async def delete_history(session_id: str):
    redis_client = get_redis_client()
    _del = redis_client.delete("message_store:" + session_id)
    if _del:
        return {"status": "success", "message": "session delete success"}
    else:
        return {"status": "failure", "message": "session delete failure"}
