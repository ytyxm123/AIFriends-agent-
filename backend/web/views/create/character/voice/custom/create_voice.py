from web.speech import CLONING_MODELS, default_tts_model, voice_request


def create_voice(voice_url, prefix, target_model=None):
    model = target_model or default_tts_model()
    if model not in CLONING_MODELS:
        raise ValueError('Unsupported voice cloning target_model')
    return voice_request('create_voice', target_model=model, prefix=prefix, url=voice_url)
