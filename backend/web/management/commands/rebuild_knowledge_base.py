from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from web.documents.utils.insert_documents import insert_documents


class Command(BaseCommand):
    help = 'Rebuild the local LanceDB knowledge base from KNOWLEDGE_SOURCE_PATH.'

    def handle(self, *args, **options):
        from os import getenv

        source = Path(getenv('KNOWLEDGE_SOURCE_PATH', './web/documents/data.txt'))
        if not source.exists():
            raise CommandError(
                f'Knowledge source not found: {source}. '
                'Copy web/documents/data.example.txt to web/documents/data.txt first.'
            )
        insert_documents()
        self.stdout.write(self.style.SUCCESS('Knowledge base rebuilt.'))
