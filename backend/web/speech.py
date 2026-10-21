"""Shared model selection for voice cloning and speech synthesis."""
import os

import requests


DEFAULT_TTS_MODEL = 'cosyvoice-v3-flash'
CLONING_MODELS = (
    'cosyvoice-v3.5-plus', 'cosyvoice-v3.5-flash',
    'cosyvoice-v3-plus', 'cosyvoice-v3-flash', 'cosyvoice-v2',
)


def default_tts_model():
    model = os.getenv('TTS_MODEL', DEFAULT_TTS_MODEL)
    if model not in CLONING_MODELS:
        raise ValueError('TTS_MODEL must be a supported CosyVoice cloning model')
    return model


def synthesis_model(voice_id):
    """Custom voice IDs encode their bound model; never reuse them across models.

    Built-in voices use the configured default. Old custom voices keep their
    original model until explicitly re-created from the source recording.
    """
    for model in CLONING_MODELS:
        if voice_id.startswith(model + '-'):
            return model
    if voice_id.startswith(('cosyvoice-', 'qwen-')):
        raise ValueError('Unsupported custom voice model; re-create a compatible voice')
    return default_tts_model()


class SpeechServiceError(RuntimeError):
    def __init__(self, code):
        # Only keep the service error code, not raw payloads or signed URLs.
        self.code = str(code or 'SpeechTaskFailed')[:100]
        super().__init__(self.code)

    @property
    def user_message(self):
        if 'FreeTier' in self.code:
            return '语音模型免费额度已用完或到期，请检查百炼额度设置；文字回复不受影响。'
        if 'InvalidParameter' in self.code:
            return '语音模型或音色不匹配，请检查音色配置；文字回复不受影响。'
        return '语音服务暂时不可用，已继续文字回复。'


def voice_request(action, **parameters):
    """Enrollment API with bounded waits and credential-safe exceptions."""
    url = os.getenv('VOICE_URL')
    key = os.getenv('API_KEY')
    if not url or not key:
        raise ValueError('VOICE_URL and API_KEY are required')
    response = requests.post(url, headers={
        'Authorization': f'Bearer {key}', 'Content-Type': 'application/json',
    }, json={'model': 'voice-enrollment', 'input': {'action': action, **parameters}}, timeout=20)
    payload = response.json()
    if not response.ok or payload.get('code'):
        raise SpeechServiceError(payload.get('code') or f'HTTP{response.status_code}')
    return payload
