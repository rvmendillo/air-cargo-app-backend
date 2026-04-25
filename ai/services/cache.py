from .embeddings import cosine_similarity

SEMANTIC_CACHE = []
SIMILARITY_THRESHOLD = 0.80


def search_cache(embedding):
    for item in SEMANTIC_CACHE:
        score = cosine_similarity(embedding, item["embedding"])

        if score >= SIMILARITY_THRESHOLD:
            return item["result"]

    return None


def store_cache(embedding, result):
    SEMANTIC_CACHE.append({
        "embedding": embedding,
        "result": result
    })