from rest_framework.response import Response
from rest_framework import status


def success_response(data=None, message=None, status_code=status.HTTP_200_OK):
    """
    Formato estándar para respuestas exitosas
    """
    response_data = {}
    if message:
        response_data['message'] = message
    if data is not None:
        response_data['data'] = data
    
    return Response(response_data, status=status_code)


def error_response(message, errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Formato estándar para respuestas de error
    """
    response_data = {
        'error': message
    }
    if errors:
        response_data['errors'] = errors
    
    return Response(response_data, status=status_code)


def paginated_response(queryset, serializer_class, request, **kwargs):
    """
    Helper para paginación estándar
    """
    from rest_framework.pagination import PageNumberPagination
    
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        serializer = serializer_class(page, many=True, context={'request': request}, **kwargs)
        return paginator.get_paginated_response(serializer.data)
    
    serializer = serializer_class(queryset, many=True, context={'request': request}, **kwargs)
    return Response(serializer.data)
