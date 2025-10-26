#!/opt/anaconda3/envs/llms/bin/python
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import chromadb
from openai import OpenAI

# ------------------------------------------------------
# Load env vars
# ------------------------------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY in your .env file.")

MODEL = "gpt-4o-mini"
CHROMA_PATH = "data/chroma"
LEGIS_COLLECTION = "legislation_policy"
CASES_COLLECTION = "legal_cases"

# ------------------------------------------------------
# Init Flask
# ------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}})

# ------------------------------------------------------
# Init Chroma
# ------------------------------------------------------
client = chromadb.PersistentClient(path=CHROMA_PATH)
collA = client.get_collection(LEGIS_COLLECTION)
collB = client.get_collection(CASES_COLLECTION)

# ------------------------------------------------------
# Helper: retrieve relevant chunks
# ------------------------------------------------------


def retrieve(collection, query, k, prefix):
    try:
        res = collection.query(query_texts=[query], n_results=k)
        results = []
        for i, doc in enumerate(res["documents"][0]):
            filename = res["metadatas"][0][i].get("filename", "unknown")
            results.append(f"[{prefix}{i+1}] ({filename})\n{doc.strip()}")
        return "\n\n".join(results)
    except Exception as e:
        return f"(error retrieving {prefix}): {e}"

# ------------------------------------------------------
# Helper: build the prompt
# ------------------------------------------------------


def build_prompt(user_input, legis_text, case_text):
    system = (
        "You are a BC workplace harassment triage assistant. "
        "Base your judgment on legislation excerpts (Section A) only. "
        "Use cases (Section B) only for supporting context — omit them if none are relevant. "
        "Do NOT invent cases or legal definitions."
    )

    user = f"""
User situation:
---
{user_input.strip()}

Section A — Legislation Excerpts:
---
{legis_text}

Section B — Case Excerpts (optional):
---
{case_text}

Instructions:
1. Determine if the user's experience qualifies as workplace bullying or harassment under BC law.
2. Return one of: 'very likely', 'likely', 'borderline', 'unlikely'.
3. Explain reasoning with 3–5 concise bullets citing the legislation sources (e.g. [A1]).
4. If any cases in Section B are relevant, summarize up to 2 briefly; otherwise omit that section entirely.
5. Provide 3–5 next steps.
6. End with one-line disclaimer that this is not legal advice.
"""
    return {"system": system, "user": user}

# ------------------------------------------------------
# Helper: call OpenAI
# ------------------------------------------------------


def call_llm(prompt):
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            temperature=0.2,
            max_tokens=900,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"LLM error: {e}"

# ------------------------------------------------------
# Routes
# ------------------------------------------------------




@app.get("/healthz")
def healthz():
    try:
        countA = collA.count()
        countB = collB.count()
        return jsonify({"ok": True, "legislation_chunks": countA, "cases_chunks": countB})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/echo")
def echo():
    data = request.get_json(silent=True) or {}
    return jsonify({"you_sent": data}), 200


@app.post("/chat")
def chat():
    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message'"}), 400

    user_msg = data["message"]
    query_A = "bullying harassment WorkSafeBC definition repeated serious incident"
    query_B = "supervisor yelling insults tribunal decision outcome"

    legis_text = retrieve(collA, query_A, k=6, prefix="A")
    case_text = retrieve(collB, query_B, k=3, prefix="B")

    prompt = build_prompt(user_msg, legis_text, case_text)
    reply = call_llm(prompt)
    return jsonify({"reply": reply})


# ------------------------------------------------------
# Entry
# ------------------------------------------------------
if __name__ == "__main__":
    print(">> server.py loaded from:", __file__)
    app.run(host="0.0.0.0", port=5001, debug=True)
