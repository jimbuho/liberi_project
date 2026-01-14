#!/usr/bin/env python
"""
Test script to validate OCR improvements with the sample Ecuadorian ID card image.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/Users/macbookproi964gb/Documents/ZExtra/Proyecto X/code/liberi_project')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

from apps.core.verification_helpers import VerificationHelpers

# Path to the uploaded sample image
image_path = "/Users/macbookproi964gb/.gemini/antigravity/brain/dabe6c34-0f9e-4535-a6b7-737ebec3be58/uploaded_image_1766094281159.jpg"

print("=" * 80)
print("TESTING OCR VALIDATION WITH SAMPLE ECUADORIAN ID CARD")
print("=" * 80)
print()

# Test 1: Extract text from image
print("TEST 1: Text Extraction")
print("-" * 80)
text = VerificationHelpers.extract_text_from_image(image_path)
print(f"Extracted text ({len(text)} characters):")
print(text)
print()

# Test 2: Validate if it's a valid ID card
print("\nTEST 2: ID Card Validation")
print("-" * 80)
result = VerificationHelpers.is_valid_id_card_image(image_path, side='front')
print(f"Is valid: {result['is_valid']}")
print(f"Confidence: {result['confidence']:.2f}")
print(f"Reasons: {result['reasons']}")
print()

# Test 3: Extract ID information
print("\nTEST 3: Information Extraction")
print("-" * 80)
id_info = VerificationHelpers.extract_id_info_from_text(text, side='front')
print(f"Success: {id_info['success']}")
print(f"Apellidos: {id_info.get('apellidos', 'N/A')}")
print(f"Nombres: {id_info.get('nombres', 'N/A')}")
print(f"ID Number: {id_info.get('id_number', 'N/A')}")
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
if result['is_valid']:
    print("✅ SUCCESS: The ID card validation now PASSES!")
    print(f"   Confidence: {result['confidence']:.1%}")
else:
    print("❌ FAILED: The ID card validation still fails")
    print(f"   Reasons: {', '.join(result['reasons'])}")
print("=" * 80)
