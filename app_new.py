# llama_main.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import faiss
import subprocess
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import docx
import pandas as pd
import re
from uuid import uuid4
import time
import threading
from ask_menu import ask_menu
from ask_image import ask_image

from helper_func import (
    save_document_to_db,
    load_document_from_db,
    save_image_text,
    load_image_text,
    load_document_from_db_outletwise,
    match_command,
    get_command_slots,
)

app = Flask(__name__)
CORS(app)

embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Store documents per doc_id
DOCUMENTS = {}  # {doc_id: {"index": ..., "chunks": ..., "created_at": ...}}

# Auto-expiry config
EXPIRY_SECONDS = 1800  # 30 minutes

OLLAMA_PATH = "/usr/local/bin/ollama"


from file_utils import UPLOAD_FOLDER

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ------------------------------
# Text extraction
# ------------------------------
def extract_text(file):
    """Extract text from PDF, DOCX, TXT, or Excel files."""
    if file.filename.endswith(".pdf"):
        reader = PdfReader(file)
        return " ".join([page.extract_text() or "" for page in reader.pages])
    elif file.filename.endswith(".docx"):
        doc = docx.Document(file)
        return " ".join([para.text for para in doc.paragraphs])
    elif file.filename.endswith(".txt"):
        return file.read().decode("utf-8")
    elif file.filename.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file, engine="openpyxl")
        text = " ".join(df.astype(str).apply(lambda row: " ".join(row), axis=1))
        return text
    else:
        raise ValueError("Unsupported file type")


# ------------------------------
# Chunking
# ------------------------------
def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks


# ------------------------------
# Build FAISS index
# ------------------------------
def build_index(chunks):
    embeddings = embedder.encode(chunks)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return index, embeddings


# ------------------------------
# Query Llama with Hybrid RAG
# ------------------------------
def clean_output(output: str) -> str:
    """Basic cleanup for Llama output (no <think> traces like DeepSeek)."""
    return output.strip()


def query_llama(context, question, model="llama3.2:3b"):
    """Ask Llama model, preferring context but allowing outside knowledge."""
    if context.strip():
        prompt = (
            f"You are a strict assistant. Only use the provided context to answer. "
            f"If the answer is not in the context, reply exactly: "
            f"'The information is not available in the provided document.'\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )
    else:
        prompt = (
            f"You are a helpful assistant. Answer the question using your own knowledge.\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )

    result = subprocess.run(
        [OLLAMA_PATH, "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    raw_output = result.stdout.decode("utf-8")
    return clean_output(raw_output)


# ------------------------------
# Routes
# ------------------------------
@app.route("/upload", methods=["POST"])
def upload_document():
    try:
        if "file" not in request.files or "username" not in request.form:
            return jsonify({"error": "File and username are required"}), 400

        uploaded_file = request.files["file"]
        username = request.form["username"]
        document_outlet_name = request.form.get("document_outlet_name", None)

        # Extract text and chunk
        text = extract_text(uploaded_file)
        chunks = chunk_text(text)


        # Get embeddings
        embeddings = embedder.encode(chunks)

        # Save document + embeddings to DB
        doc_id = save_document_to_db(username, uploaded_file.filename, chunks, embeddings, document_outlet_name)

        return jsonify({
            "doc_id": doc_id,
            "document_outlet_name": document_outlet_name,
            "message": f"Document '{uploaded_file.filename}' loaded successfully."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/ask", methods=["POST"])
def ask_question():
    try:
        data = request.get_json()
        question = data.get("question")
        doc_id = data.get("doc_id")
        document_outlet_name = data.get("document_outlet_name", None)
        if not question:
            return jsonify({"error": "Question is required"}), 400

        context = ""
        if doc_id:
            try:
                chunks, index = load_document_from_db(doc_id, document_outlet_name)
                q_embed = embedder.encode([question])
                D, I = index.search(q_embed, k=3)
                context = " ".join([chunks[i] for i in I[0]])
            except Exception as e:
                print(e)
                return jsonify({"error": "Document not found or failed to load"}), 404

        # Hybrid: pass context if available, else fallback
        answer = query_llama(context, question, model="llama3.2:3b")

        return jsonify({
            "question": question,
            "doc_id": doc_id,
            "document_outlet_name": document_outlet_name,
            "answer": answer
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/ask-outlet", methods=["POST"])
def ask_question_outlet():
    try:
        data = request.get_json()
        question = data.get("question")
        document_outlet_name = data.get("document_outlet_name", None)
        if not question:
            return jsonify({"error": "Question is required"}), 400

        context = ""
        if document_outlet_name:
            try:
                chunks, index = load_document_from_db_outletwise(document_outlet_name)
                q_embed = embedder.encode([question])
                D, I = index.search(q_embed, k=3)
                context = " ".join([chunks[i] for i in I[0]])
            except Exception as e:
                print(e)
                return jsonify({"error": "Document not found or failed to load"}), 404

        # Hybrid: pass context if available, else fallback
        answer = query_llama(context, question, model="llama3.2:3b")

        return jsonify({
            "question": question,
            "document_outlet_name": document_outlet_name,
            "answer": answer
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



import redis
import json
import re
import datetime
from flask import Flask, request, jsonify

# ------------------------------
# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# ------------------------------

# def query_llama_with_slots(context, question, slots):
#     """
#     Calls LLaMA with context + question, and tries to extract slot values.

#     Args:
#         context (str): Text context from documents.
#         question (str): User's question.
#         slots (dict): Current slots, e.g., {"name": None, "date": None, "time": None}

#     Returns:
#         answer (str): LLaMA answer.
#         updated_slots (dict): Slots updated if LLaMA finds values.
#     """
#     # Step 1: Build a prompt for LLaMA to fill slots
#     slot_instructions = "\n".join([f"{k}: {v if v else '[empty]'}" for k, v in slots.items()])
#     prompt = (
#         f"You are a helpful assistant. Fill the following information from the user's input if available.\n"
#         f"Current slots:\n{slot_instructions}\n\n"
#         f"Context:\n{context}\n\n"
#         f"Question: {question}\n\n"
#         f"Provide the updated slot values in format:\n"
#         f"name=..., date=..., time=..., service_type=...\n"
#         f"And also answer the question."
#     )

#     # Step 2: Call your existing query_llama function
#     output = query_llama(question + "\n" + context + "\n" + prompt, question)

#     # Step 3: Extract slot values from output using regex
#     updated_slots = slots.copy()
#     for slot_name in slots.keys():
#         match = re.search(f"{slot_name}=([^,\\n]+)", output, re.IGNORECASE)
#         if match:
#             value = match.group(1).strip()
#             if value.lower() not in ["none", "[empty]"]:
#                 updated_slots[slot_name] = value

#     # Step 3.5: Validate date slot (accept only Monday–Friday)
#     date_value = updated_slots.get("date")
#     if date_value:
#         try:
#             date_obj = datetime.datetime.strptime(date_value, "%Y-%m-%d")
#             if date_obj.weekday() >= 5:  # 5=Saturday, 6=Sunday
#                 updated_slots["date"] = None  # invalid day
#         except ValueError:
#             updated_slots["date"] = None  # invalid format

#     # Step 4: Return LLaMA answer + updated slots
#     return output, updated_slots


def query_llama_with_no_slots(context, question):
    """
    Calls LLaMA with context + question. If slots are provided, tries to extract slot values.
    If slots are empty, just return answer from context.
    """

    # No slots → just answer using document context
    prompt = (
            f"You are a helpful assistant. Answer the user's question using the context.\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            f"If information is not available, say 'No information provided'."
        )

    output = query_llama(question + "\n" + context + "\n" + prompt, question)

    return output
    

from helper_func import get_db_connection  # assuming this exists

# ------------------------------
# Connect to Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# ------------------------------
# Utility to get slots for a command
def get_slots_for_command(command_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT slot_id, slot_name, required
        FROM outlet_command_slots
        WHERE command_id = %s
    """, (command_id,))
    slots = cursor.fetchall()
    cursor.close()
    conn.close()
    return slots


# @app.route("/ask-outlet-command-slots", methods=["POST"])
# def ask_outlet_command_slots():
#     try:
#         data = request.get_json()
#         document_outlet_name = data.get("document_outlet_name")
#         user_id = data.get("user_id")
#         command_id = data.get("command_id")  # selected command by user
#         user_slots = data.get("slots", {})   # optional new slot values
#         question = data.get("question", "")  # user question for LLaMA

#         if not document_outlet_name or not user_id or not command_id:
#             return jsonify({"error": "document_outlet_name, user_id, and command_id are required"}), 400

#         session_key = f"{document_outlet_name}_{user_id}_{command_id}"

#         # Load current session from Redis
#         session_json = r.get(session_key)
#         session_slots = json.loads(session_json) if session_json else {}

#         # Update session slots with frontend values
#         session_slots.update(user_slots)

#         # Fetch required slots for this command from DB
#         slots_required = get_slots_for_command(command_id)
#         slots_dict = {slot["slot_name"]: session_slots.get(slot["slot_name"]) for slot in slots_required}

#         # Check if all required slots are filled
#         ready_to_call_api = all(v is not None and v != "" for v in slots_dict.values())

#         # Determine if this command has subcommands
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)  # <-- important!
#         cursor.execute("SELECT COUNT(*) AS count FROM outlet_commands WHERE parent_command_id = %s", (command_id,))
#         subcommand_count = cursor.fetchone()["count"]


#         is_last_command = subcommand_count == 0

#         # Optionally call LLaMA if it's actionable and has no slots
#         llama_answer = None
#         if is_last_command and not slots_dict:
#             # Load document context

#             cursor.execute("SELECT command_text FROM outlet_commands WHERE command_id=%s", (command_id,))
#             row = cursor.fetchone()

#             # Use command_text as the question if frontend didn't provide one
#             if row and row.get("command_text"):
#                 question = row["command_text"]

#             try:
#                 chunks, index = load_document_from_db_outletwise(document_outlet_name)
#                 context = " ".join(chunks)  # simple concat; you can use vector search if needed
#                 llama_answer = query_llama_with_no_slots(context, question)
#             except Exception as e:
#                 llama_answer = f"No document context found: {str(e)}"
#         cursor.close()
#         conn.close()

#         # Save back to Redis (expires in 1 hour)
#         r.set(session_key, json.dumps(slots_dict), ex=3600)

#         return jsonify({
#             "document_outlet_name": document_outlet_name,
#             "command_id": command_id,
#             "slots": slots_dict,
#             "ready_to_call_api": ready_to_call_api,
#             "is_last_command": is_last_command,
#             "llama_answer": llama_answer
#         }), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# ------------------------------
@app.route("/ask-outlet-command-slots", methods=["POST"])
def ask_outlet_command_slots():
    try:
        data = request.get_json()
        document_outlet_name = data.get("document_outlet_name")
        user_id = data.get("user_id")
        command_id = data.get("command_id")  # can be None
        user_slots = data.get("slots", {})   # optional new slot values
        question = data.get("question", "")  # user question for LLaMA

        # Required fields
        if not document_outlet_name or not user_id:
            return jsonify({"error": "document_outlet_name and user_id are required"}), 400

        # ------------------------------
        # General question flow (no command_id)
        if not command_id and question:
            try:
                chunks, index = load_document_from_db_outletwise(document_outlet_name)
                context = " ".join(chunks)
                llama_answer = query_llama_with_no_slots(context, question)
            except Exception as e:
                llama_answer = f"No document context found: {str(e)}"

            return jsonify({
                "document_outlet_name": document_outlet_name,
                "command_id": None,
                "slots": {},
                "ready_to_call_api": True,
                "is_last_command": True,
                "llama_answer": llama_answer
            }), 200

        # ------------------------------
        # Normal command flow
        session_key = f"{document_outlet_name}_{user_id}_{command_id}"

        # Load current session from Redis
        session_json = r.get(session_key)
        session_slots = json.loads(session_json) if session_json else {}

        # Update session slots with frontend values
        session_slots.update(user_slots)

        # Fetch required slots for this command from DB
        slots_required = get_slots_for_command(command_id)
        slots_dict = {slot["slot_name"]: session_slots.get(slot["slot_name"]) for slot in slots_required}

        # Check if all required slots are filled
        ready_to_call_api = all(v is not None and v != "" for v in slots_dict.values())

        # Determine if this command has subcommands
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS count FROM outlet_commands WHERE parent_command_id = %s", (command_id,))
        subcommand_count = cursor.fetchone()["count"]
        is_last_command = subcommand_count == 0

        # Optionally call LLaMA if it's actionable and has no slots
        llama_answer = None
        if is_last_command and not slots_dict:
            # Fetch command_text if frontend didn't provide a question
            cursor.execute("SELECT command_text FROM outlet_commands WHERE command_id=%s", (command_id,))
            row = cursor.fetchone()
            if row and row.get("command_text") and not question:
                question = row["command_text"]

            try:
                chunks, index = load_document_from_db_outletwise(document_outlet_name)
                context = " ".join(chunks)
                llama_answer = query_llama_with_no_slots(context, question)
            except Exception as e:
                llama_answer = f"No document context found: {str(e)}"

        cursor.close()
        conn.close()

        # Save session slots back to Redis
        r.set(session_key, json.dumps(slots_dict), ex=3600)

        return jsonify({
            "document_outlet_name": document_outlet_name,
            "command_id": command_id,
            "slots": slots_dict,
            "ready_to_call_api": ready_to_call_api,
            "is_last_command": is_last_command,
            "llama_answer": llama_answer
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Flask Document + Excel Q&A API (Llama) is running!"})


@app.route("/ask-menu", methods=["POST"])
def ask_menu_endpoint():
    data = request.get_json()
    question = data.get("question")
    if not question:
        return jsonify({"error": "Question is required"}), 400

    response = ask_menu(question)
    return jsonify(response)


@app.route("/ask-image-upload", methods=["POST"])
def ask_image_upload():
    if "file" not in request.files or "username" not in request.form:
        return jsonify({"error": "File and username are required"}), 400

    image_file = request.files["file"]
    username = request.form["username"]
    image_path = f"/tmp/{image_file.filename}"
    image_file.save(image_path)

    response = ask_image(image_path)  # call existing ask_image.py function
    if "error" in response:
        return jsonify(response), 400

    # Save detected text in DB
    image_id = save_image_text(username, image_file.filename, response["detected_text"])

    return jsonify({
        "image_id": image_id,
        "detected_text": response["detected_text"],
        "explanation": response["explanation"],
        "message": "Image processed and stored successfully"
    })


@app.route("/ask-image-question", methods=["POST"])
def ask_image_question():
    data = request.get_json()
    image_id = data.get("image_id")
    question = data.get("question")

    if not image_id or not question:
        return jsonify({"error": "image_id and question are required"}), 400

    detected_text = load_image_text(image_id)
    if not detected_text:
        return jsonify({"error": "Image not found"}), 404

    # Send detected_text as context to Llama
    answer = query_llama(detected_text, question, model="llama3.2:3b")
    return jsonify({
        "image_id": image_id,
        "question": question,
        "answer": answer
    })


from flask import send_from_directory

# Serve uploaded images
@app.route("/uploads/commands/<filename>")
def uploaded_file(filename):
    return send_from_directory("uploads/commands", filename)



# Scheduler jobs wrapped with app context
from apscheduler.schedulers.background import BackgroundScheduler
from helper_func import delete_old_documents, delete_old_images
# ------------------------------
def scheduled_delete_documents():
    with app.app_context():
        print("[SCHEDULER] Running delete_old_documents")
        delete_old_documents()

def scheduled_delete_images():
    with app.app_context():
        print("[SCHEDULER] Running delete_old_images")
        delete_old_images()

# Start scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(scheduled_delete_documents, "interval", minutes=5)
scheduler.add_job(scheduled_delete_images, "interval", minutes=5)
scheduler.start()

# Allow iframe embedding
@app.after_request
def add_iframe_headers(response):
    # Option 1: Allow any site to embed (simplest)
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    # Option 2: Restrict to your frontend domain (safer)
    # response.headers['X-Frame-Options'] = 'ALLOW-FROM https://your-frontend-domain.com'

    response.headers['Content-Security-Policy'] = "frame-ancestors *"
    return response



from user_upload import user_bp
from command_module import command_bp
# Register the blueprint
app.register_blueprint(user_bp)
app.register_blueprint(command_bp)

if __name__ == "__main__":
    threading.Thread(target=cleanup_job, daemon=True).start()
    app.run(host="0.0.0.0", port=8015, debug=True)
