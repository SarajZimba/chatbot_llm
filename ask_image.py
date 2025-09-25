import easyocr
import subprocess
import re

OLLAMA_PATH = "/usr/local/bin/ollama"

# Initialize OCR reader (supports multiple languages, e.g., ['en', 'ch_sim'])
reader = easyocr.Reader(['en'])


def clean_output(output: str) -> str:
    """Remove thinking traces and extra text."""
    output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL)
    output = re.sub(r".*?\.{3}done thinking\.\s*", "", output, flags=re.DOTALL)
    return output.strip()


def query_deepseek(text, model="llama3.2:3b"):
    """Send detected text to Llama for explanation (name kept for compatibility)."""
    prompt = (
        f"You are a helpful assistant. Explain clearly what this text means:\n\n"
        f"Text:\n{text}\n\n"
        f"Explanation:"
    )

    result = subprocess.run(
        [OLLAMA_PATH, "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    return clean_output(result.stdout.decode("utf-8"))


def ask_image(image_path: str):
    # OCR step
    results = reader.readtext(image_path, detail=0)  # detail=0 gives just the text list
    detected_text = " ".join(results).strip()

    if not detected_text:
        return {"error": "No text detected in image"}

    # Send to Llama for explanation
    explanation = query_deepseek(detected_text)

    return {
        "detected_text": detected_text,
        "explanation": explanation
    }
