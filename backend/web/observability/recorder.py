"""TraceRecorder creates a Trace, collects spans in memory and persists them."""
import contextlib
import json

from django.db import transaction
from django.utils.timezone import now

from web.models.observability import Span, Trace
from .pricing import calculate_cost

MAX_OUTPUT_CHARS = 5000
MAX_FIELD_CHARS = 2000


def truncate(value, limit):
    if not isinstance(value, str):
        value = str(value)
    return value[:limit]


def json_safe(data):
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return {'repr': truncate(data, MAX_FIELD_CHARS)}


class SpanRecord:
    __slots__ = ('span_type', 'name', 'status', 'started_at', 'ended_at',
                 'input', 'output', 'model', 'input_tokens',
                 'output_tokens', 'error', 'order')

    def __init__(self, span_type, name, input_data=None, model=''):
        self.span_type = span_type
        self.name = name
        self.status = Span.Status.RUNNING
        self.started_at = now()
        self.ended_at = None
        self.input = input_data if input_data is not None else {}
        self.output = ''
        self.model = model
        self.input_tokens = 0
        self.output_tokens = 0
        self.error = ''
        self.order = 0


class TraceRecorder:
    def __init__(self, *, user, friend, message, model=''):
        self.trace = Trace.objects.create(
            user=user,
            friend=friend,
            input=message[:5000],
            model=model or '',
            status=Trace.Status.RUNNING,
        )
        self.spans = []
        self._counter = 0
        self._finished = False

    @property
    def trace_id(self):
        return self.trace.trace_id

    def start_span(self, span_type, name, input_data=None, model=''):
        record = SpanRecord(span_type, name, json_safe(input_data), model)
        record.order = self._counter
        self._counter += 1
        self.spans.append(record)
        return record

    def end_span(self, record, *, output='', status=Span.Status.SUCCESS,
                 input_tokens=0, output_tokens=0, error=''):
        record.status = status
        record.ended_at = now()
        record.output = truncate(output, MAX_OUTPUT_CHARS)
        record.input_tokens = input_tokens
        record.output_tokens = output_tokens
        record.error = truncate(error, MAX_FIELD_CHARS)

    @contextlib.contextmanager
    def span(self, span_type, name, input_data=None, model=''):
        record = self.start_span(span_type, name, input_data, model)
        try:
            yield record
        except Exception as exc:
            self.end_span(record, status=Span.Status.FAILED,
                          error=f'{type(exc).__name__}: {exc}')
            raise
        else:
            if record.status == Span.Status.RUNNING:
                self.end_span(record)

    def finish(self, *, output='', input_tokens=0, output_tokens=0,
               total_tokens=0, status=Trace.Status.SUCCESS, error=''):
        if self._finished:
            return self.trace
        self._finished = True
        ended_at = now()
        duration_ms = int((ended_at - self.trace.started_at).total_seconds() * 1000)
        if status == Trace.Status.SUCCESS:
            cost = calculate_cost(self.trace.model, input_tokens, output_tokens)
        else:
            cost = 0.0
        with transaction.atomic():
            for record in self.spans:
                if record.ended_at is None:
                    record.ended_at = ended_at
                    if record.status == Span.Status.RUNNING:
                        record.status = (
                            Span.Status.FAILED
                            if status == Trace.Status.FAILED
                            else Span.Status.SUCCESS
                        )
            Span.objects.bulk_create(
                [self._build_span(record) for record in self.spans]
            )
            self.trace.output = truncate(output, MAX_OUTPUT_CHARS)
            self.trace.status = status
            self.trace.ended_at = ended_at
            self.trace.duration_ms = duration_ms
            self.trace.input_tokens = input_tokens
            self.trace.output_tokens = output_tokens
            self.trace.total_tokens = total_tokens or (input_tokens + output_tokens)
            self.trace.cost = cost
            self.trace.error = truncate(error, 200)
            self.trace.save()
        return self.trace

    def _build_span(self, record):
        if record.ended_at is not None:
            duration_ms = int(
                (record.ended_at - record.started_at).total_seconds() * 1000
            )
        else:
            duration_ms = 0
        return Span(
            trace=self.trace,
            span_type=record.span_type,
            name=record.name,
            status=record.status,
            started_at=record.started_at,
            ended_at=record.ended_at,
            duration_ms=duration_ms,
            input=record.input,
            output=record.output,
            model=record.model,
            input_tokens=record.input_tokens,
            output_tokens=record.output_tokens,
            error=record.error,
            order=record.order,
        )
