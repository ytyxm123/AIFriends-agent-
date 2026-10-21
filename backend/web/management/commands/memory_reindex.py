from django.core.management.base import BaseCommand

from web.models.memory import MemoryFact
from web.views.friend.message.memory.config import setting
from web.views.friend.message.memory.retrieval import active_facts, embed_texts


class Command(BaseCommand):
    help = 'Rebuild missing/changed-model fact vectors; requires a working embedding API.'

    def add_arguments(self, parser):
        parser.add_argument('--friend-id', type=int, required=True)

    def handle(self, *args, **options):
        rebuilt = 0
        for fact in active_facts(options['friend_id']).order_by('id').iterator():
            if (fact.embedding_model == setting('EMBEDDING_MODEL') and
                    len(fact.embedding) == setting('EMBEDDING_DIMENSIONS')):
                continue
            vectors = embed_texts([fact.content])
            if not vectors:
                break
            # Do not attach an old vector if a worker changed the fact during the API call.
            rebuilt += MemoryFact.objects.filter(pk=fact.pk, version=fact.version, active=True).update(
                embedding=vectors[0], embedding_model=setting('EMBEDDING_MODEL'))
        self.stdout.write(f'Rebuilt {rebuilt} memory vectors.')
