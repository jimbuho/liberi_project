web: gunicorn liberi_project.wsgi:application
worker: celery -A liberi_project worker --loglevel=info
beat: celery -A liberi_project beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler