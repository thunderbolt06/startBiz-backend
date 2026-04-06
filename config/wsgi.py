import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

# Run migrations on Vercel cold start (SQLite in /tmp is ephemeral but writable)
try:
    from django.core.management import call_command
    call_command('migrate', '--run-syncdb', verbosity=0)
except Exception:
    pass
