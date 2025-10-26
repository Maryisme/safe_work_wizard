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

# Models
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL",
                        "text-embedding-3-large")  # must match ingestion
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Chroma paths/collections
CHROMA_PATH = "data/chroma"
LEGIS_COLLECTION = "legislation_policy"
CASES_COLLECTION = "legal_cases"

# Retrieval controls (same as notebook)
TOPK_A, TOPK_B = 8, 3
BUDGET_A, BUDGET_B = 2500, 2000   # total char budgets for prompt sections
CAP_A, CAP_B = 900, 900           # per-chunk char caps

# ------------------------------------------------------
# Init Flask
# ------------------------------------------------------
app = Flask(__name__)
CORS(app, resources={r"/chat": {"origins": "*"}})

# ------------------------------------------------------
# Init OpenAI + Chroma (Chroma >= 0.5: no embedding_function)
# ------------------------------------------------------
oai = OpenAI(api_key=OPENAI_API_KEY)
chroma = chromadb.PersistentClient(path=CHROMA_PATH)
collA = chroma.get_collection(LEGIS_COLLECTION)  # legislation/policy
collB = chroma.get_collection(CASES_COLLECTION)  # cases/tribunals

# ------------------------------------------------------
# Helpers: embed, format sources, retrieve (query_embeddings)
# ------------------------------------------------------


def _embed_one(text: str):
    return oai.embeddings.create(model=EMBED_MODEL, input=[text]).data[0].embedding


def _format_source(meta: dict) -> str:
    url = (meta or {}).get("source_url") or (meta or {}).get("url")
    fname = (meta or {}).get("filename", "")
    return f"Source: {fname} — {url}" if url else f"Source: {fname}"


def _retrieve(collection, query, k, max_chars, per_chunk_cap, prefix):
    """
    Retrieve top chunks with truncation and label them like:
      [A1 filename#chunk_index]
      Source: <fname> — <url>
      <text>
    Returns (block_text, used_count, used_struct_list)
    """
    try:
        qe = _embed_one(query)
        res = collection.query(query_embeddings=[qe], n_results=k)
    except Exception as e:
        label = f"[{prefix}1]"
        msg = f"{label} Retrieval failed: {e}"
        return msg, 0, [{"type": prefix, "label": label, "error": str(e)}]

    if not res.get("ids") or not res["ids"][0]:
        return "", 0, []

    items, total = [], 0
    used = []
    for i in range(len(res["ids"][0])):
        text = (res["documents"][0][i] or "").strip()
        if not text:
            continue
        if len(text) > per_chunk_cap:
            text = text[:per_chunk_cap]
        meta = res["metadatas"][0][i] or {}
        label = f"[{prefix}{len(items)+1} {meta.get('filename','')}#{str(meta.get('chunk_index', i))}]"
        src = _format_source(meta)
        chunk_text = label + "\n" + src + "\n" + text

        items.append(chunk_text)
        used.append({
            "type": prefix,
            "label": label,
            "filename": meta.get("filename"),
            "chunk_index": meta.get("chunk_index", i),
            "source_url": meta.get("source_url") or meta.get("url"),
            "text": text
        })

        total += len(text)
        if total >= max_chars:
            break

    return "\n\n".join(items), len(items), used

# ------------------------------------------------------
# Prompt: EXACTLY the same as the (fixed) notebook flow
# ------------------------------------------------------


def _build_prompt(user_situation: str, A_block: str, B_block: str, has_cases: bool):
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

# ------------------------------------------------------
# LLM call
# ------------------------------------------------------


def _call_llm(prompt):
    try:
        resp = oai.chat.completions.create(
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
        return f"**LLM call failed:** {e}"

# ------------------------------------------------------
# Routes
# ------------------------------------------------------




@app.get("/healthz")
def healthz():
    try:
        return jsonify({
            "ok": True,
            "legislation_chunks": collA.count(),
            "cases_chunks": collB.count()
        })
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

    user_msg = (data["message"] or "").strip()
    if not user_msg:
        return jsonify({"error": "Empty 'message'"}), 400

    # Retrieval uses the user's message directly (no hardcoded seed queries)
    A_block, nA, used_A = _retrieve(
        collA, user_msg, TOPK_A, BUDGET_A, CAP_A, prefix="A")
    B_block, nB, used_B = _retrieve(
        collB, user_msg, TOPK_B, BUDGET_B, CAP_B, prefix="B")

    # Guardrail: do not answer if Section A failed or is empty
    if nA == 0:
        return jsonify({
            "error": "retrieval_failed_for_legislation",
            "resources": {"A_block": A_block, "used_A": used_A}
        }), 503

    prompt = _build_prompt(user_msg, A_block, B_block, has_cases=(nB > 0))
    reply = _call_llm(prompt)

    # Reply mirrors notebook structure; also return the exact source blocks for transparency
    return jsonify({
        "reply": reply,
        "resources": {
            "A_block": A_block,
            "B_block": B_block,
            "used": used_A + used_B
        }
    })


# ------------------------------------------------------
# Entry
# ------------------------------------------------------
if __name__ == "__main__":
    print(">> server.py loaded from:", __file__)
    app.run(host="0.0.0.0", port=5001, debug=True)
