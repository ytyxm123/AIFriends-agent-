"""Model pricing, in CNY per million tokens.

The table is a best-effort default; verify against each provider's official
pricing and override it via Django settings:

    LLM_PRICING = {'my-model': {'input': 1.0, 'output': 3.0}}
"""
from django.conf import settings

DEFAULT_PRICING = {
    'deepseek-reasoner': {'input': 4.0, 'output': 16.0},
    'deepseek': {'input': 2.0, 'output': 8.0},
    'qwen-plus': {'input': 0.8, 'output': 2.0},
    'qwen-turbo': {'input': 0.3, 'output': 1.0},
}


def get_price(model):
    overrides = getattr(settings, 'LLM_PRICING', {}) or {}
    table = {**DEFAULT_PRICING, **overrides}
    model = model or ''
    if model in table:
        return table[model]
    # Longest prefix match wins, e.g. deepseek-v4-flash matches deepseek.
    prefixes = [key for key in table if model.startswith(key)]
    if prefixes:
        return table[max(prefixes, key=len)]
    return {'input': 0.0, 'output': 0.0}


def calculate_cost(model, input_tokens, output_tokens):
    price = get_price(model)
    cost = (
        input_tokens / 1_000_000 * price['input']
        + output_tokens / 1_000_000 * price['output']
    )
    return round(cost, 6)
