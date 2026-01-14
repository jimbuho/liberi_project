#!/bin/bash

# Script para ejecutar los tests de verificación
# Uso: ./run_tests.sh

echo "🧪 Ejecutando Tests de Verificación..."
echo "======================================"

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    echo "✅ Activando entorno virtual..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "✅ Activando entorno virtual..."
    source .venv/bin/activate
else
    echo "⚠️  No se encontró entorno virtual. Asegúrate de tener Django instalado."
fi

# Ejecutar tests
echo ""
echo "🚀 Ejecutando tests..."
python manage.py test apps.core.tests.test_verification_helpers --verbosity=2

# Mostrar resultado
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ ¡Todos los tests pasaron!"
else
    echo ""
    echo "❌ Algunos tests fallaron. Revisa el output arriba."
fi
