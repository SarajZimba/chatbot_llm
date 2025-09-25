from flask import Flask, request, jsonify
from flask_cors import CORS
import faiss
import pickle
import subprocess
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import docx
import re
app = Flask(__name__)
CORS(app)

embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Store chunks and index globally
DOCUMENT_INDEX = {"index": None, "chunks": None}

def extract_text(file):
    if file.filename.endswith(".pdf"):
        reader = PdfReader(file)
        return " ".join([page.extract_text() or "" for page in reader.pages])
    elif file.filename.endswith(".docx"):
        doc = docx.Document(file)
        return " ".join([para.text for para in doc.paragraphs])
    elif file.filename.endswith(".txt"):
        return file.read().decode("utf-8")
    else:
        raise ValueError("Unsupported file type")

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks

def build_index(chunks):
    embeddings = embedder.encode(chunks)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return index, embeddings

def query_deepseek(context, question, model="deepseek-r1:1.5b"):
    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer only from the context above."
    result = subprocess.run(
        ["ollama", "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    output = result.stdout.decode("utf-8")
    print("output", output)
    # Remove <think>...</think> blocks if present
    output_new = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL)
    print("output_new", output_new)
    return output_new.strip()
#    return result.stdout.decode("utf-8")

# ------------------------------
# Step 1: Upload document
# ------------------------------
@app.route("/upload", methods=["POST"])
def upload_document():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        uploaded_file = request.files["file"]
        text = extract_text(uploaded_file)
        chunks = chunk_text(text)
        index, _ = build_index(chunks)

        # Save globally
        DOCUMENT_INDEX["chunks"] = chunks
        DOCUMENT_INDEX["index"] = index

        return jsonify({"message": "Document loaded successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------
# Step 2: Ask question
# ------------------------------
@app.route("/ask", methods=["POST"])
def ask_question():
    try:
        data = request.get_json()
        question = data.get("question")
        if not question:
            return jsonify({"error": "Question is required"}), 400
        if DOCUMENT_INDEX["index"] is None:
            return jsonify({"error": "No document loaded"}), 400

        index = DOCUMENT_INDEX["index"]
        chunks = DOCUMENT_INDEX["chunks"]

        q_embed = embedder.encode([question])
        D, I = index.search(q_embed, k=3)
        context = " ".join([chunks[i] for i in I[0]])

        answer = query_deepseek(context, question)

        return jsonify({
            "question": question,
            "answer": answer
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8012, debug=True)
