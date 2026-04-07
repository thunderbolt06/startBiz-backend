import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config.tracing import setup_tracing
setup_tracing()

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Auto-migrate the SQLite database on every startup so the schema is always current.
try:
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)
except Exception:
    pass
