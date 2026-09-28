import os
import asyncio
import logging

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight


# --------------------------------------------------
# 1. Load environment variables
# --------------------------------------------------

load_dotenv()

HINDSIGHT_API_KEY = os.getenv("HINDSIGHT_API_KEY")
HINDSIGHT_BASE_URL = os.getenv(
    "HINDSIGHT_BASE_URL",
    "https://api.hindsight.vectorize.io"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

BANK_ID = "memora-support"


# --------------------------------------------------
# 2. Initialize Flask
# --------------------------------------------------

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------------------------------------------------
# 3. Initialize Groq
# --------------------------------------------------

groq_client = None

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)


# --------------------------------------------------
# 4. Home page
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# 5. Chat endpoint
# --------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():

    # Read the user's message
    data = request.get_json(silent=True) or {}

    message = data.get("message", "").strip()

    if not message:
        return jsonify({
            "reply": "Please enter a message."
        }), 400

    if groq_client is None:
        return jsonify({
            "reply": "Groq API key is missing. Please check your .env file."
        }), 500

    # Run the asynchronous Hindsight operations
    try:
        answer = asyncio.run(
            process_message(message)
        )

        return jsonify({
            "reply": answer
        })

    except Exception:
        logger.exception("Chat request failed")

        return jsonify({
            "reply": (
                "Sorry, something went wrong. "
                "Please check the Flask terminal."
            )
        }), 500


# --------------------------------------------------
# 6. AI + persistent memory
# --------------------------------------------------

async def process_message(message):

    memory = None
    previous_memories = ""

    try:
        # Create the Hindsight client inside this event loop
        if HINDSIGHT_API_KEY:

            memory = Hindsight(
                base_url=HINDSIGHT_BASE_URL,
                api_key=HINDSIGHT_API_KEY
            )

            # Retrieve relevant past conversations
            try:
                result = await memory.arecall(
                    bank_id=BANK_ID,
                    query=message
                )

                previous_memories = "\n".join(
                    item.text
                    for item in result.results
                )

            except Exception:
                logger.exception(
                    "Hindsight recall failed; continuing without memory"
                )

        # Build the system instructions
        system_prompt = f"""
You are Memora, a friendly AI customer support assistant.

Your responsibilities:
1. Understand the customer's problem.
2. Provide clear, practical solutions.
3. Give troubleshooting steps in a simple order.
4. Ask a follow-up question when necessary.
5. Use previous memories only when they are relevant.
6. Never invent customer history or claim an issue is resolved
   when it has not been confirmed.

Relevant previous memories:
{previous_memories if previous_memories else "No relevant memories found."}

Respond politely and helpfully.
"""

        # Get an answer from Groq
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            temperature=0.5,
            max_tokens=800
        )

        answer = response.choices[0].message.content

        if not answer:
            answer = (
                "I couldn't generate a response. "
                "Please try asking in another way."
            )

        # Save the conversation to Hindsight
        if memory is not None:
            try:
                await memory.aretain(
                    bank_id=BANK_ID,
                    content=(
                        f"Customer message: {message}\n"
                        f"Support response: {answer}"
                    ),
                    context="Memora customer support conversation"
                )

            except Exception:
                logger.exception(
                    "Hindsight retain failed; AI response is still available"
                )

        return answer

    finally:
        # Close the Hindsight client cleanly
        if memory is not None:
            try:
                await memory.aclose()
            except Exception:
                logger.exception(
                    "Could not close Hindsight client"
                )


# --------------------------------------------------
# 7. Run the application
# --------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )