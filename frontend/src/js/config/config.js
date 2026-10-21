const CONFIG_API = {
    HTTP_URL: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000',
    VAD_URL: import.meta.env.VITE_VAD_BASE_URL || 'http://127.0.0.1:5173/vad/'
}

export default CONFIG_API
