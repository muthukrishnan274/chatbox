import os
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import (
    CHATBOT_TITLE,
    SYSTEM_PROMPT,
    GEMINI_MODEL,
)

app = Flask(__name__)

MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_MESSAGES = 30
MAX_HISTORY_CONTENT_LENGTH = 4000


def _validate_text(value, field_name, max_length):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    value = value.strip()
    if not value:
        raise ValueError(f"{field_name} cannot be empty.")
    if len(value) > max_length:
        raise ValueError(f"{field_name} is too long.")
    return value


def validate_history(history):
    if history is None:
        return []
    if not isinstance(history, list):
        raise ValueError("history must be a list.")
    if len(history) > MAX_HISTORY_MESSAGES:
        raise ValueError("history contains too many messages.")

    validated = []
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("Each history item must be an object.")

        role = item.get("role")
        content = item.get("content")

        if role not in {"user", "assistant"}:
            raise ValueError("History contains an invalid role.")

        content = _validate_text(
            content,
            "history content",
            MAX_HISTORY_CONTENT_LENGTH,
        )
        validated.append({"role": role, "content": content})

    return validated


def build_contents(history, message):
    contents = []
    for item in history:
        contents.append(
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["content"])],
            )
        )

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=message)],
        )
    )
    return contents


@app.get("/")
def index():
    return render_template("index.html", chatbot_title=CHATBOT_TITLE)


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "Request body must be valid JSON."}), 400

        message = _validate_text(
            data.get("message"),
            "message",
            MAX_MESSAGE_LENGTH,
        )
        history = validate_history(data.get("history", []))

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return jsonify({"error": "The chatbot service is not configured."}), 503

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=build_contents(history, message),
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )

        reply = getattr(response, "text", None)
        if not isinstance(reply, str) or not reply.strip():
            return jsonify({"error": "The chatbot could not generate a response."}), 502

        return jsonify({"reply": reply.strip()})

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        app.logger.exception("Chat request failed")
        return jsonify({"error": "Something went wrong while processing your request."}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
