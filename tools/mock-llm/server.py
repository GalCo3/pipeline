import json
import re

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI(title="Mock LLM Server")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def mock_all(request: Request):
    selected_label = "תפעולי"
    try:
        body = await request.json()
        messages = body.get("messages", [])
        for msg in messages:
            content = msg.get("content", "")
            if "Candidate Labels:" in content:
                match = re.search(r"Candidate Labels:\s*(\[.*?\])", content, re.DOTALL)
                if match:
                    labels = json.loads(match.group(1))
                    if labels and isinstance(labels, list) and len(labels) > 0:
                        selected_label = labels[0]
    except Exception:
        pass

    mock_response_content = json.dumps(
        {"reasoning": "Mock classification", "recommended_label": selected_label},
        ensure_ascii=False,
    )

    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": mock_response_content,
                },
                "finish_reason": "stop",
            }
        ],
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
