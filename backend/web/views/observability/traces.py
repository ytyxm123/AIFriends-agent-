from datetime import timedelta

from django.db.models import Avg, Sum
from django.utils.timezone import localtime, now
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from web.models.observability import Trace


def _fmt_time(value):
    return localtime(value).strftime('%Y-%m-%d %H:%M:%S') if value else ''


class TraceStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = min(max(int(request.GET.get('days', 7)), 1), 90)
        since = now() - timedelta(days=days)
        qs = Trace.objects.filter(started_at__gte=since)
        total = qs.count()
        success = qs.filter(status=Trace.Status.SUCCESS).count()
        failed = qs.filter(status=Trace.Status.FAILED).count()
        running = qs.filter(status=Trace.Status.RUNNING).count()
        agg = qs.aggregate(
            avg_duration=Avg('duration_ms'),
            total_input=Sum('input_tokens'),
            total_output=Sum('output_tokens'),
            total_cost=Sum('cost'),
        )
        return Response({
            'result': 'success',
            'days': days,
            'total': total,
            'success': success,
            'failed': failed,
            'running': running,
            'success_rate': round(success / total * 100, 1) if total else 0.0,
            'avg_duration_ms': round(agg['avg_duration'] or 0),
            'total_input_tokens': agg['total_input'] or 0,
            'total_output_tokens': agg['total_output'] or 0,
            'total_cost': round(agg['total_cost'] or 0, 4),
        })


def _serialize_trace(trace):
    return {
        'trace_id': str(trace.trace_id),
        'username': trace.user.user.username,
        'character': trace.friend.character.name,
        'input': trace.input[:100],
        'status': trace.status,
        'model': trace.model,
        'started_at': _fmt_time(trace.started_at),
        'duration_ms': trace.duration_ms,
        'total_tokens': trace.total_tokens,
        'cost': trace.cost,
    }


class TraceListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        days = min(max(int(request.GET.get('days', 7)), 1), 90)
        offset = int(request.GET.get('items_count', 0))
        page_size = 20
        qs = Trace.objects.filter(started_at__gte=now() - timedelta(days=days))
        status = request.GET.get('status')
        if status in dict(Trace.Status.choices):
            qs = qs.filter(status=status)
        model = request.GET.get('model', '').strip()
        if model:
            qs = qs.filter(model__icontains=model)
        keyword = request.GET.get('keyword', '').strip()
        if keyword:
            qs = qs.filter(user__user__username__icontains=keyword)
        traces = list(
            qs.select_related('user__user', 'friend__character')
            [offset:offset + page_size]
        )
        return Response({
            'result': 'success',
            'traces': [_serialize_trace(trace) for trace in traces],
            'has_more': len(traces) == page_size,
        })


class TraceDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, trace_id):
        trace = Trace.objects.select_related(
            'user__user', 'friend__character'
        ).filter(trace_id=trace_id).first()
        if trace is None:
            return Response({'result': 'error', 'message': '记录不存在'},
                            status=404)
        spans = [
            {
                'span_type': span.span_type,
                'name': span.name,
                'status': span.status,
                'started_at': _fmt_time(span.started_at),
                'offset_ms': int(
                    (span.started_at - trace.started_at).total_seconds() * 1000
                ),
                'duration_ms': span.duration_ms,
                'input': span.input,
                'output': span.output,
                'model': span.model,
                'input_tokens': span.input_tokens,
                'output_tokens': span.output_tokens,
                'error': span.error,
                'order': span.order,
            }
            for span in trace.spans.all()
        ]
        return Response({
            'result': 'success',
            'trace': {
                'trace_id': str(trace.trace_id),
                'username': trace.user.user.username,
                'character': trace.friend.character.name,
                'input': trace.input,
                'output': trace.output,
                'status': trace.status,
                'model': trace.model,
                'started_at': _fmt_time(trace.started_at),
                'ended_at': _fmt_time(trace.ended_at),
                'duration_ms': trace.duration_ms,
                'input_tokens': trace.input_tokens,
                'output_tokens': trace.output_tokens,
                'total_tokens': trace.total_tokens,
                'cost': trace.cost,
                'error': trace.error,
            },
            'spans': spans,
        })
