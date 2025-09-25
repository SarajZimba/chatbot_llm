import streamlit as st
import faiss
import pickle
import subprocess
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import docx
import re
# ------------------------------
# Functions (same as before)
# ------------------------------
def extract_text(file):
    if file.name.endswith(".pdf"):
        reader = PdfReader(file)
        return " ".join([page.extract_text() or "" for page in reader.pages])
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        return " ".join([para.text for para in doc.paragraphs])
    elif file.name.endswith(".txt"):
        return file.read().decode("utf-8")
    else:
        raise ValueError("Unsupported file type")

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i+chunk_size])
        chunks.append(chunk)
    return chunks

embedder = SentenceTransformer("all-MiniLM-L6-v2")

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
#    return result.stdout.decode("utf-8")
    
    output = result.stdout.decode("utf-8")
    print("output", output)
    # 1. Remove <think>...</think> blocks
    output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()
    print("output_new_after_think_removed", output)
    # 2. If "Answer:" exists, keep only that part
    if "Answer:" in output:
        output = output.split("Answer:", 1)[1].strip()

    # 3. Fallback: just return cleaned text
    return output.strip()

# ------------------------------
# Streamlit UI
# ------------------------------
st.title("📄 Document Q&A with DeepSeek-R1")

uploaded_file = st.file_uploader("Upload a PDF, DOCX, or TXT file", type=["pdf", "docx", "txt"])

if uploaded_file is not None:
    with st.spinner("Reading document..."):
        text = extract_text(uploaded_file)
        chunks = chunk_text(text)
        index, _ = build_index(chunks)
        # Save chunks temporarily
        with open("chunks.pkl", "wb") as f:
            pickle.dump(chunks, f)
    st.success("Document loaded and processed!")

    question = st.text_input("Ask a question about the document:")

    if question:
        q_embed = embedder.encode([question])
        D, I = index.search(q_embed, k=3)
        with open("chunks.pkl", "rb") as f:
            chunks = pickle.load(f)
        context = " ".join([chunks[i] for i in I[0]])
        with st.spinner("Getting answer from DeepSeek..."):
            answer = query_deepseek(context, question)
        st.subheader("Answer:")
        st.write(answer)
