import secrets

from constance import config
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Show (or regenerate) the bearer token used by the Home Assistant API at /api/ha/"

    def add_arguments(self, parser):
        parser.add_argument('--regenerate', action='store_true',
                            help='Generate a new token (invalidates the old one)')
        parser.add_argument('--disable', action='store_true',
                            help='Clear the token, disabling the Home Assistant API')

    def handle(self, *args, **options):
        if options['disable']:
            config.HA_API_TOKEN = ''
            self.stdout.write("Home Assistant API disabled (token cleared).")
            return

        if options['regenerate'] or not config.HA_API_TOKEN:
            config.HA_API_TOKEN = secrets.token_urlsafe(32)
            self.stdout.write("Generated a new Home Assistant API token:")

        self.stdout.write(config.HA_API_TOKEN)
