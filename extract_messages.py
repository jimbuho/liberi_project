"""
Script para extraer el contenido de los emails de tasks.py y crear templates
"""
import re
import os

# Leer tasks.py
with open('apps/core/tasks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Encontrar todos los bloques de message = f"""..."""
pattern = r'message = f"""(.*?)"""'
matches = re.findall(pattern, content, re.DOTALL)

print(f"Encontrados {len(matches)} mensajes hardcodeados")
print("="*80)

for i, match in enumerate(matches, 1):
    print(f"\n{i}. Mensaje encontrado:")
    print("-"*80)
    print(match[:200] + "..." if len(match) > 200 else match)
    print("-"*80)
