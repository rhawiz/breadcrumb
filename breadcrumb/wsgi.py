"""
WSGI config for breadcrumb project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/howto/deployment/wsgi/
"""

import os, sys
sys.path.append('/opt/bitnami/apps/django/django_projects/breadcrumb')
os.environ.setdefault("PYTHON_EGG_CACHE", "/opt/bitnami/apps/django/django_projects/breadcrumb/egg_cache")


from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "breadcrumb.settings")

application = get_wsgi_application()
