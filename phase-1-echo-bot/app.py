#!/usr/bin/env python3
"""EurecomGPT echo bot — a ~50-line Flask service."""

from __future__ import annotations

from flask import Flask, jsonify, request

app = Flask(__name__)


def build_echo(message: str) -> dict:
    return {"echo": message, "length": len(message)}


def extract_message(args, json_body) -> str | None:
    msg = args.get("msg")
    if msg is not None:
        return msg
    if json_body is not None:
        return json_body.get("message")
    return None


@app.get("/")
def index():
    return jsonify(
        {
            "service": "eurecomgpt-echo",
            "usage": "GET /echo?msg=hello  or  POST /echo {\"message\": \"hello\"}",
        }
    )


@app.get("/health")
def health():
    return "ok", 200


@app.route("/echo", methods=["GET", "POST"])
def echo():
    message = extract_message(request.args, request.get_json(silent=True))
    if message is None:
        return jsonify({"error": "provide ?msg=... or JSON {\"message\": ...}"}), 400
    return jsonify(build_echo(message))


if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
