from django.conf import settings

def global_context(request):
    """
    Context processor for global settings variables
    """
    return {
        'google_tag_manager_id': getattr(settings, 'GOOGLE_TAG_MANAGER_ID', None),
        'base_url': settings.BASE_URL,
    }
