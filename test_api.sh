#!/bin/bash

echo "🧪 TEST COMPLETO DEL API - LIBERI MVP"
echo "======================================"

BASE_URL="http://localhost:8000"

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 1. Test endpoints públicos
echo -e "\n${YELLOW}1️⃣  Test: Listar Categorías (público)${NC}"
curl -s "${BASE_URL}/api/categories/" | python3 -m json.tool
echo -e "${GREEN}✓ Categorías${NC}\n"

echo -e "${YELLOW}2️⃣  Test: Listar Servicios (público)${NC}"
curl -s "${BASE_URL}/api/services/" | python3 -m json.tool
echo -e "${GREEN}✓ Servicios${NC}\n"

# 2. Login y obtener token
echo -e "${YELLOW}3️⃣  Test: Login${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "${BASE_URL}/api/login/" \
  -H "Content-Type: application/json" \
  -d '{"username": "maria_nails", "password": "password123"}')

echo "$LOGIN_RESPONSE" | python3 -m json.tool

# Extraer token
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['access'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo -e "${RED}❌ Error: No se pudo obtener el token${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Token obtenido: ${TOKEN:0:50}...${NC}\n"

# 3. Test endpoints protegidos
echo -e "${YELLOW}4️⃣  Test: Listar Proveedores (requiere auth)${NC}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "${BASE_URL}/api/providers/?status=approved" \
  | python3 -m json.tool
echo -e "${GREEN}✓ Proveedores${NC}\n"

echo -e "${YELLOW}5️⃣  Test: Mi perfil de proveedor${NC}"
curl -s -H "Authorization: Bearer $TOKEN" \
  "${BASE_URL}/api/providers/me/" \
  | python3 -m json.tool
echo -e "${GREEN}✓ Mi perfil${NC}\n"

echo -e "${YELLOW}6️⃣  Test: Mis ubicaciones (como cliente)${NC}"
# Primero hacer login como cliente
CLIENT_LOGIN=$(curl -s -X POST "${BASE_URL}/api/login/" \
  -H "Content-Type: application/json" \
  -d '{"username": "juan_cliente", "password": "password123"}')

CLIENT_TOKEN=$(echo "$CLIENT_LOGIN" | python3 -c "import sys, json; print(json.load(sys.stdin)['tokens']['access'])" 2>/dev/null)

curl -s -H "Authorization: Bearer $CLIENT_TOKEN" \
  "${BASE_URL}/api/locations/" \
  | python3 -m json.tool
echo -e "${GREEN}✓ Ubicaciones${NC}\n"

echo -e "${YELLOW}7️⃣  Test: Crear ubicación${NC}"
curl -s -X POST -H "Authorization: Bearer $CLIENT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "Av. 6 de Diciembre N36-123 y Naciones Unidas",
    "reference": "Edificio Multicentro, piso 5",
    "label": "oficina",
    "latitude": -0.180653,
    "longitude": -78.467834
  }' \
  "${BASE_URL}/api/locations/" \
  | python3 -m json.tool
echo -e "${GREEN}✓ Ubicación creada${NC}\n"

echo -e "${YELLOW}8️⃣  Test: Registro de nuevo usuario${NC}"
curl -s -X POST "${BASE_URL}/api/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test_user",
    "email": "test@example.com",
    "password": "test1234",
    "password_confirm": "test1234",
    "phone": "0999999999",
    "role": "customer",
    "first_name": "Test",
    "last_name": "User"
  }' \
  | python3 -m json.tool
echo -e "${GREEN}✓ Usuario registrado${NC}\n"

echo "======================================"
echo -e "${GREEN}✅ Tests completados${NC}"
echo "======================================"
