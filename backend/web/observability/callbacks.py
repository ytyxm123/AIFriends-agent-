"""LangChain callback handler that turns model/tool calls into spans."""
from langchain_core.callbacks import BaseCallbackHandler

from web.models.observability import Span
from .recorder import truncate


class TraceCallbackHandler(BaseCallbackHandler):
    def __init__(self, recorder):
        self.recorder = recorder
        self.runs = {}

    @staticmethod
    def _model_name(serialized, kwargs):
        invocation = kwargs.get('invocation_params') or {}
        return (
            invocation.get('model')
            or invocation.get('model_name')
            or (serialized or {}).get('name')
            or ''
        )

    async def on_chat_model_start(self, serialized, messages, *, run_id,
                                  parent_run_id=None, **kwargs):
        model = self._model_name(serialized, kwargs)
        if model and not self.recorder.trace.model:
            self.recorder.trace.model = model
            self.recorder.trace.save(update_fields=['model'])
        contents = []
        for batch in messages:
            for message in batch:
                content = getattr(message, 'content', message)
                contents.append(truncate(content, 1000))
        record = self.recorder.start_span(
            Span.SpanType.LLM, 'model_call', {'messages': contents}, model=model
        )
        self.runs[run_id] = record

    async def on_llm_end(self, response, *, run_id, parent_run_id=None, **kwargs):
        record = self.runs.pop(run_id, None)
        if record is None:
            return
        usage = {}
        output = ''
        try:
            message = response.generations[0][0].message
            usage = getattr(message, 'usage_metadata', None) or {}
            output = getattr(message, 'content', '') or ''
        except (AttributeError, IndexError):
            pass
        self.recorder.end_span(
            record,
            output=output,
            input_tokens=usage.get('input_tokens', 0) or 0,
            output_tokens=usage.get('output_tokens', 0) or 0,
        )

    async def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        record = self.runs.pop(run_id, None)
        if record is not None:
            self.recorder.end_span(
                record, status=Span.Status.FAILED,
                error=f'{type(error).__name__}: {error}'
            )

    async def on_tool_start(self, serialized, input_str, *, run_id,
                            parent_run_id=None, **kwargs):
        name = (serialized or {}).get('name') or 'tool'
        span_type = (
            Span.SpanType.RETRIEVAL
            if name == 'search_knowledge_base'
            else Span.SpanType.TOOL
        )
        record = self.recorder.start_span(
            span_type, name, {'input': truncate(input_str, 1000)}
        )
        self.runs[run_id] = record

    async def on_tool_end(self, output, *, run_id, parent_run_id=None, **kwargs):
        record = self.runs.pop(run_id, None)
        if record is None:
            return
        text = output if isinstance(output, str) else str(output)
        self.recorder.end_span(record, output=text)

    async def on_tool_error(self, error, *, run_id, parent_run_id=None, **kwargs):
        record = self.runs.pop(run_id, None)
        if record is not None:
            self.recorder.end_span(
                record, status=Span.Status.FAILED,
                error=f'{type(error).__name__}: {error}'
            )
