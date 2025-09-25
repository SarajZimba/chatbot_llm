import mysql.connector
import numpy as np
import io
from uuid import uuid4
import faiss

# Connect to MariaDB
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="llm"
    )

# Serialize numpy array to bytes
def serialize_embedding(embedding):
    buf = io.BytesIO()
    np.save(buf, embedding)
    return buf.getvalue()

# Deserialize bytes to numpy array
def deserialize_embedding(blob):
    buf = io.BytesIO(blob)
    return np.load(buf)


def save_document_to_db(username, filename, chunks, embeddings, document_outlet_name):
    doc_id = str(uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()

    # Save document metadata
    cursor.execute(
        "INSERT INTO documents (id, username, filename, document_outlet_name) VALUES (%s, %s, %s, %s)",
        (doc_id, username, filename, document_outlet_name)
    )

    # Save embeddings per chunk
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        cursor.execute(
            "INSERT INTO embeddings (document_id, chunk_index, chunk_text, embedding, document_outlet_name) VALUES (%s, %s, %s, %s, %s)",
            (doc_id, idx, chunk, serialize_embedding(emb), document_outlet_name)
        )

    conn.commit()
    cursor.close()
    conn.close()
    return doc_id

def load_document_from_db(doc_id, document_outlet_name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # cursor.execute("SELECT chunk_text, embedding FROM embeddings WHERE document_id=%s and document_outlet_name=%s ORDER BY chunk_index ASC", (doc_id, document_outlet_name))

    if document_outlet_name is None:
        cursor.execute("""
            SELECT chunk_text, embedding 
            FROM embeddings 
            WHERE document_id=%s AND document_outlet_name IS NULL
            ORDER BY chunk_index ASC
        """, (doc_id,))
    else:
        cursor.execute("""
            SELECT chunk_text, embedding 
            FROM embeddings 
            WHERE document_id=%s AND document_outlet_name=%s
            ORDER BY chunk_index ASC
        """, (doc_id, document_outlet_name))

    rows = cursor.fetchall()
    chunks = [row['chunk_text'] for row in rows]
    embeddings = np.array([deserialize_embedding(row['embedding']) for row in rows])
    
    cursor.close()
    conn.close()
    
    # Build FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return chunks, index

import mysql.connector
import uuid

def save_image_text(username, filename, detected_text):
    image_id = str(uuid.uuid4())
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO image_ocr (id, username, filename, detected_text) VALUES (%s, %s, %s, %s)",
        (image_id, username, filename, detected_text)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return image_id

def load_image_text(image_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT detected_text FROM image_ocr WHERE id=%s", (image_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        return row["detected_text"]
    return None

def delete_old_documents():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM documents WHERE do created_at < NOW() - INTERVAL 30 MINUTE AND document_outlet_name IS NULL")
    conn.commit()
    cursor.close()
    conn.close()

def delete_old_images():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM image_ocr WHERE created_at < NOW() - INTERVAL 30 MINUTE")
    conn.commit()
    cursor.close()
    conn.close()


def load_document_from_db_outletwise(document_outlet_name):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # cursor.execute("SELECT chunk_text, embedding FROM embeddings WHERE document_id=%s and document_outlet_name=%s ORDER BY chunk_index ASC", (doc_id, document_outlet_name))

    cursor.execute("""
        SELECT chunk_text, embedding 
        FROM embeddings 
        WHERE document_outlet_name=%s
        ORDER BY chunk_index ASC
        """, (document_outlet_name,))

    rows = cursor.fetchall()
    chunks = [row['chunk_text'] for row in rows]
    embeddings = np.array([deserialize_embedding(row['embedding']) for row in rows])
    
    cursor.close()
    conn.close()
    
    # Build FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    return chunks, index


def get_command_slots(command_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT slot_name 
        FROM outlet_command_slots 
        WHERE command_id=%s AND required=1
    """, (command_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    # Return a dictionary with slot names initialized to None
    return {row['slot_name']: None for row in rows}

def match_command(document_outlet_name, question):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT command_id, command_text FROM outlet_commands WHERE document_outlet_name=%s", (document_outlet_name,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    for row in rows:
        if row['command_text'].lower() in question.lower():
            return row['command_id'], row['command_text']
    return None, None