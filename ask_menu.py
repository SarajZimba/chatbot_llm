import requests
import re
import subprocess

OLLAMA_PATH = "/usr/local/bin/ollama"

def query_deepseek(prompt, model="llama3.2:3b"):
    """
    Query DeepSeek with the given prompt and clean the response.
    Removes <think> tags and common reasoning text.
    """
    result = subprocess.run(
        [OLLAMA_PATH, "run", model],
        input=prompt.encode("utf-8"),
        capture_output=True
    )
    output = result.stdout.decode("utf-8")

    # Remove <think> sections & common reasoning traces
    output_new = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL)
    output_new = re.sub(r"(?i)(thinking|reasoning|let me think)[^\.]*\.?", "", output_new)
    return output_new.strip().strip('"').strip("'")

def get_dummy_products():
    """
    Fetch dummy products from DummyJSON API.
    Returns list of product dicts.
    """
    try:
        response = requests.get("https://dummyjson.com/products", timeout=10)
        if response.status_code == 200:
            return response.json().get("products", [])
        return []
    except (requests.RequestException, ValueError):
        return []

def ask_menu(question):
    """
    Dual-mode Q&A:
    - Product mode: generic or specific product queries.
    - General mode: fallback to DeepSeek for other questions.
    """
    products = get_dummy_products()
    context = ""

    # Build product context
    for product in products:
        context += (
            f"Name: {product['title']}\n"
            f"Description: {product['description']}\n"
            f"Price: ${product['price']}\n\n"
        )

    question_lower = question.lower()
    product_titles_lower = [p['title'].lower() for p in products]

    # Check if any product is mentioned specifically
    mentioned_products = [p for p in products if p['title'].lower() in question_lower]

    # Check for generic product query keywords
    generic_keywords = ["product", "products", "menu", "item", "list", "price", "catalog", "inventory", "show me", "all products"]
    is_generic_query = any(word in question_lower for word in generic_keywords)

    # Determine product-related mode
    is_product_related = is_generic_query or bool(mentioned_products)

    # -------------------- CASE 1: PRODUCT-RELATED --------------------
    if is_product_related:
        prompt = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n"
            f"IMPORTANT: Answer only with the product names exactly as written in the context, "
            f"separated by commas. Do not add explanations.\n"
            f"Example format: 'iPhone 9, iPhone X, Samsung Universe 9'"
        )

        response = query_deepseek(prompt)

        # Clean response
        cleaned_response = re.sub(
            r'(?i)(here are the products|the products are|based on the context|according to the context)[:\.]?\s*',
            '', response
        )
        cleaned_response = re.sub(r'[^a-zA-Z0-9,\s\-]', '', cleaned_response)
        raw_names = [name.strip() for name in cleaned_response.split(",") if name.strip()]

        # Include explicitly mentioned products
        for product in mentioned_products:
            if product['title'] not in raw_names:
                raw_names.append(product['title'])

        # Validate against product titles
        valid_titles = {p["title"]: p for p in products}
        selected_products, seen = [], set()
        for name in raw_names:
            if name in valid_titles:
                product = valid_titles[name]
                if product['title'] not in seen:
                    seen.add(product['title'])
                    selected_products.append(product)
            else:
                # fuzzy match
                for title, product in valid_titles.items():
                    if name.lower() in title.lower() or title.lower() in name.lower():
                        if product['title'] not in seen:
                            seen.add(product['title'])
                            selected_products.append(product)
                        break

        # Handle generic requests like "show me 3 products"
        number_match = re.search(r"show me (\d+)", question_lower)
        num_requested = int(number_match.group(1)) if number_match else None
        if num_requested and selected_products:
            selected_products = selected_products[:num_requested]

        # Build response
        product_names = [p["title"] for p in selected_products]
        matching_images = []
        for product in selected_products:
            img = product.get("thumbnail") or (product["images"][0] if product.get("images") else None)
            if img:
                matching_images.append({
                    "title": product["title"],
                    "image": img,
                    "price": f"${product['price']}",
                    "description": (
                        product['description'][:100] + "..."
                        if len(product['description']) > 100 else product['description']
                    )
                })

        if not product_names:
            answer_text = "No products found matching your query."
        elif len(product_names) == 1:
            answer_text = f"{product_names[0]} - ${selected_products[0]['price']}"
        else:
            answer_text = ", ".join(product_names)

        return {
            "mode": "product",
            "question": question,
            "answer": answer_text,
            "images": matching_images,
            "product_count": len(selected_products)
        }

    # -------------------- CASE 2: GENERAL KNOWLEDGE --------------------
    else:
        general_answer = query_deepseek(
            f"Question: {question}\nAnswer clearly and concisely."
        )
        return {
            "mode": "general",
            "question": question,
            "answer": general_answer
        }
