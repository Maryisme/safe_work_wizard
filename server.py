# server.py
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# ---------- Env / Config ----------
load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
LEGIS_COLLECTION = os.getenv("LEGIS_COLLECTION", "legislation_policy")
CASES_COLLECTION = os.getenv("CASES_COLLECTION", "legal_cases")
TOPK_A, TOPK_B = 8, 3
BUDGET_A, BUDGET_B = 2500, 2000
CAP_A, CAP_B = 900, 900
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("Set OPENAI_API_KEY before running the server.")

# ---------- Flask ----------
app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"},
     r"/healthz": {"origins": "*"}})

# ---------- Chroma ----------
ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=OPENAI_API_KEY,
    model_name="text-embedding-3-large"  # must match ingestion dimension
)
client = chromadb.PersistentClient(path=CHROMA_PATH)
collA = client.get_collection(name=LEGIS_COLLECTION, embedding_function=ef)
collB = client.get_collection(name=CASES_COLLECTION, embedding_function=ef)

# ---------- Helpers ----------


def _merge_experience(payload: dict) -> str:
    """Flatten a dict of question→answer into a readable user situation."""
    if not isinstance(payload, dict):
        return ""
    parts = []
    for k, v in payload.items():
        q = str(k).strip()
        a = str(v).strip()
        if not a:
            continue
        if q:
            parts.append(f"{q}: {a}")
        else:
            parts.append(a)
    return "\n".join(parts).strip()


def _format_source(meta):
    url = meta.get("source_url") or meta.get("url")
    fname = meta.get("filename", "")
    return ("Source: " + fname + " — " + url) if url else ("Source: " + fname)


def _retrieve(collection, query, k, max_chars, per_chunk_cap, prefix):
    """Retrieve top chunks with truncation and label them."""
    try:
        res = collection.query(query_texts=[query], n_results=k)
    except Exception as e:
        return f"[{prefix}1] Retrieval failed: {e}", 0
    if not res.get("ids") or not res["ids"][0]:
        return "", 0

    items, total = [], 0
    for i in range(len(res["ids"][0])):
        text = (res["documents"][0][i] or "").strip()
        if not text:
            continue
        if len(text) > per_chunk_cap:
            text = text[:per_chunk_cap]
        meta = res["metadatas"][0][i] or {}
        label = "[" + prefix + str(len(items)+1) + " " + meta.get(
            "filename", "") + "#" + str(meta.get("chunk_index", i)) + "]"
        src = _format_source(meta)
        chunk_text = label + "\n" + src + "\n" + text
        items.append(chunk_text)
        total += len(text)
        if total >= max_chars:
            break
    return "\n\n".join(items), len(items)


def _build_prompt(user_situation, A_block, B_block, has_cases):
    """Constructs system and user messages cleanly."""
    system = (
        "You are a BC workplace triage explainer. "
        "Use legislation/policy excerpts to assess whether the described conduct likely qualifies as bullying or harassment. "
        "Base your analysis ONLY on the Legislation Excerpts (Section A). "
        "List exact sources you rely on by name/URL as shown in the excerpts. "
        "If NO case excerpts are provided, OMIT the 'Similar Tribunal Decisions' section entirely. "
        "If case excerpts are provided, you may include a brief 'Similar Tribunal Decisions' section using ONLY those case excerpts; "
        "do not invent or imply the existence of other cases. "
        "Never invent sources or citations."
    )

    section_b = ""
    if has_cases and B_block.strip():
        section_b = (
            "\n\nSection B — Case Excerpts (context only; do not change your decision based on these):\n---\n"
            + B_block
        )

    user = (
        "User Situation:\n---\n" + user_situation.strip() + "\n\n"
        "Section A — Legislation Excerpts (authoritative; use these to assess and justify):\n---\n"
        + (A_block.strip() if A_block.strip() else "(none retrieved)")
        + section_b
        + "\n\nYour tasks:\n"
        "1) Assessment under the Law & Policy (use ONLY Section A):\n"
        "   - Return one of: 'very likely', 'likely', 'borderline', or 'unlikely'.\n"
        "   - Provide 3–5 bullets mapping the user's facts to legal elements. Quote sparingly and refer to the provided sources by name/URL.\n"
        "2) Confidence: repeat the likelihood from #1.\n"
    )

    if has_cases:
        user += (
            "3) Similar Tribunal Decisions (context only): list 1–3 items drawn ONLY from the case excerpts above; "
            "1–2 lines each; include outcome; cite by the provided source names/URLs.\n"
        )
    else:
        user += "3) Do not include a 'Similar Tribunal Decisions' section (no case excerpts were provided).\n"

    user += (
        "4) Next Steps: 3–5 actionable steps consistent with your assessment.\n"
        "5) Sources: list the specific Section A sources (by name/URL) you relied on.\n"
        "6) Disclaimer: one line that this is general information, not legal advice."
    )

    return {"system": system, "user": user}


def _call_llm(prompt):
    """Calls OpenAI chat completion."""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": prompt["system"]},
                {"role": "user", "content": prompt["user"]},
            ],
            temperature=0.1,
            max_tokens=900,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return "**LLM call failed:** " + str(e)


def triage(user_text):
    """Main pipeline: retrieve → build prompt → call LLM. (unchanged functionality)"""
    if not user_text or not user_text.strip():
        return "Please paste the user's situation."

    # EXACTLY the same retrieval queries you provided
    query_A = "bullying harassment definition repeated one serious incident reasonable management action WorkSafeBC"
    query_B = "supervisor yelling insults repeated humiliation intimidation decision outcome"

    A_block, _ = _retrieve(collA, query_A, TOPK_A, BUDGET_A, CAP_A, prefix="A")
    B_block, nB = _retrieve(collB, query_B, TOPK_B,
                            BUDGET_B, CAP_B, prefix="B")

    prompt = _build_prompt(user_text, A_block, B_block, has_cases=(nB > 0))
    return _call_llm(prompt)

# ---------- Routes ----------


@app.get("/healthz")
def healthz():
    try:
        return jsonify({
            "ok": True,
            "model": MODEL,
            "collections": {
                "legislation_policy": collA.count(),
                "legal_cases": collB.count(),
            }
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    # Expecting structured Q/A data instead of "message"
    user_text = _merge_experience(data)
    if not user_text:
        return jsonify({"error": "Missing user experience data"}), 400

    reply_md = triage(user_text)
    return jsonify({"reply_markdown": reply_md}), 200


# ---------- Entry ----------
if __name__ == "__main__":
    print(">> server.py loaded from:", __file__)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5001")), debug=True)
