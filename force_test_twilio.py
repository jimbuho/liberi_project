import os
import django
import time
from django.conf import settings
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'liberi_project.settings')
django.setup()

# Print current mode
print(f"WHATSAPP_TEST_MODE: {settings.WHATSAPP_TEST_MODE}")
print(f"SENDER_NUMBER: {settings.TWILIO_WHATSAPP_FROM}")

# Params for the test
RECIPIENT = '593998981436'
# Let's try 'payment_confirmed' because it is a simple TEXT template (no buttons usually, safer for testing)
TEMPLATE_NAME = 'payment_confirmed' 
TEMPLATE_CONFIG = settings.TWILIO_TEMPLATES.get(TEMPLATE_NAME)
TEMPLATE_SID = TEMPLATE_CONFIG['content_sid']

# This template usually has 2 variables: {{1}} customer_name, {{2}} service_name
VARIABLES = {'1': 'Test Customer', '2': 'Test Service'} 
import json
content_vars_json = json.dumps(VARIABLES)

print(f"\n🚀 TEST FORCE SEND: {TEMPLATE_NAME}")
print(f"   Recipient: {RECIPIENT}")
print(f"   SID: {TEMPLATE_SID}")
print(f"   Variables: {content_vars_json}")

client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

try:
    print("\nAttempting to send via Twilio API...")
    message = client.messages.create(
        from_=settings.TWILIO_WHATSAPP_FROM,
        to=f'whatsapp:+{RECIPIENT}',
        content_sid=TEMPLATE_SID,
        content_variables=content_vars_json
    )
    
    print(f"✅ API Call Successful!")
    print(f"   Message SID: {message.sid}")
    print(f"   Initial Status: {message.status}")
    
    print("\n⏳ Monitoring delivery status (10s)...")
    for i in range(5):
        time.sleep(2)
        msg = client.messages(message.sid).fetch()
        print(f"   [{i+1}] Status: {msg.status}")
        if msg.status in ['failed', 'undelivered']:
            print(f"   ❌ Delivery Failed! Error: {msg.error_code} - {msg.error_message}")
            break
        if msg.status in ['delivered', 'read']:
            print("   ✅ Message Delivered!")
            break

except TwilioRestException as e:
    print(f"❌ Twilio API Error:")
    print(f"   Code: {e.code}")
    print(f"   Message: {e.msg}")
    print(f"   More info: {e.more_info}")
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
