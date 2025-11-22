# backend/core/management/commands/setup_demo.py
from django.core.management.base import BaseCommand
import os

class Command(BaseCommand):
    help = 'Setup complete demo environment'

    def handle(self, *args, **options):
        # Execute the demo setup script
        script_path = os.path.join(os.path.dirname(__file__), '../../../create_demo_data.py')
        with open(script_path, 'r') as f:
            exec(f.read())