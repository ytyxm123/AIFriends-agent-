from django.conf import settings


DEFAULTS = {
    'BATCH_SIZE': 10,
    'RECENT_TURNS': 10,
    'RECENT_TOKEN_BUDGET': 4000,
    'CONTEXT_TOKEN_BUDGET': 1600,
    'SUMMARY_TOKEN_BUDGET': 600,
    'TOP_K': 6,
    'CANDIDATE_LIMIT': 500,
    'MIN_CONFIDENCE': 0.7,
    'MIN_RELEVANCE': 0.25,
    'MODEL_TIMEOUT': 15,
    'USE_EMBEDDINGS': True,
    'MODEL': 'qwen-plus',
    'EMBEDDING_MODEL': 'text-embedding-v4',
    'EMBEDDING_DIMENSIONS': 1024,
}


def setting(name):
    return getattr(settings, 'AGENT_MEMORY', {}).get(name, DEFAULTS[name])
