from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages

from .models import LegalDocument, LegalAcceptance


def get_client_ip(request):
    """Obtiene la IP del cliente desde la request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Obtiene el user agent del cliente"""
    return request.META.get('HTTP_USER_AGENT', '')


def legal_document_view(request, document_type):
    """
    Muestra un documento legal activo según su tipo
    URL: /legal/document/<document_type>/
    """
    valid_types = [choice[0] for choice in LegalDocument.DOCUMENT_TYPES]
    if document_type not in valid_types:
        return redirect('home')
    
    document = get_object_or_404(
        LegalDocument,
        document_type=document_type,
        is_active=True,
        status='published'
    )
    
    template_map = {
        'terms_user': 'legal/terms_user.html',
        'privacy_user': 'legal/privacy_user.html',
        'terms_provider': 'legal/terms_provider.html',
        'privacy_provider': 'legal/privacy_provider.html',
    }
    
    template = template_map.get(document_type, 'legal/document.html')
    
    context = {
        'document': document,
        'document_type': document_type,
    }
    
    return render(request, template, context)


@login_required
def accept_legal_document(request):
    """
    Procesa la aceptación de documentos legales
    Recibe: POST con document_type en los datos
    Retorna: JSON con resultado
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    document_type = request.POST.get('document_type')
    
    valid_types = [choice[0] for choice in LegalDocument.DOCUMENT_TYPES]
    if document_type not in valid_types:
        return JsonResponse({'error': 'Tipo de documento inválido'}, status=400)
    
    try:
        document = LegalDocument.objects.get(
            document_type=document_type,
            is_active=True,
            status='published'
        )
    except LegalDocument.DoesNotExist:
        return JsonResponse({
            'error': 'Documento no disponible'
        }, status=404)
    
    acceptance, created = LegalAcceptance.objects.get_or_create(
        user=request.user,
        document=document,
        defaults={
            'ip_address': get_client_ip(request),
            'user_agent': get_user_agent(request),
        }
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Documento aceptado exitosamente',
        'document_type': document_type,
    })


@login_required
def consent_view(request):
    """
    Muestra documentos legales pendientes de aceptación
    Solo los necesarios según el rol del usuario
    URL: /legal/consent/
    """
    
    user_role = request.user.profile.role if hasattr(request.user, 'profile') else 'customer'
    
    if user_role == 'provider':
        required_documents = ['terms_provider', 'privacy_provider']
    else:
        required_documents = ['terms_user', 'privacy_user']
    
    active_documents = LegalDocument.objects.filter(
        document_type__in=required_documents,
        is_active=True,
        status='published'
    )
    
    pending_documents = []
    for document in active_documents:
        if not LegalAcceptance.objects.filter(
            user=request.user,
            document=document
        ).exists():
            pending_documents.append(document)
    
    if not pending_documents:
        messages.info(request, 'Ya has aceptado todos los documentos legales')
        return redirect('dashboard')
    
    context = {
        'pending_documents': pending_documents,
        'user_role': user_role,
    }
    
    return render(request, 'legal/consent.html', context)


def api_check_legal_acceptance(request, document_type):
    """
    API para verificar si un usuario ha aceptado un documento
    Retorna JSON
    """
    if not request.user.is_authenticated:
        return JsonResponse({'accepted': False})
    
    valid_types = [choice[0] for choice in LegalDocument.DOCUMENT_TYPES]
    if document_type not in valid_types:
        return JsonResponse({'error': 'Tipo inválido'}, status=400)
    
    try:
        document = LegalDocument.objects.get(
            document_type=document_type,
            is_active=True
        )
    except LegalDocument.DoesNotExist:
        return JsonResponse({'error': 'Documento no disponible'}, status=404)
    
    accepted = LegalAcceptance.objects.filter(
        user=request.user,
        document=document
    ).exists()
    
    return JsonResponse({
        'accepted': accepted,
        'document_type': document_type,
        'version': document.version,
    })