import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Auto-migrate only when using ephemeral SQLite (no DATABASE_URL set)
import os as _os
if not _os.getenv("DATABASE_URL"):
    try:
        from django.core.management import call_command
        call_command('migrate', '--run-syncdb', verbosity=0)
    except Exception:
        pass
