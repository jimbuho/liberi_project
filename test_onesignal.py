from django.conf import settings
import os
import django
import uuid

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "liberi_project.settings")
django.setup()

from apps.notifications.onesignal_service import OneSignalService

def test_onesignal_config():
    print("Testing OneSignal Configuration...")
    
    app_id = getattr(settings, 'ONESIGNAL_APP_ID', os.getenv('ONESIGNAL_APP_ID'))
    api_key = getattr(settings, 'ONESIGNAL_REST_API_KEY', os.getenv('ONESIGNAL_REST_API_KEY'))
    
    print(f"APP ID: {app_id}")
    print(f"API KEY: {api_key[:10]}..." if api_key else "API KEY: None")
    
    # Generate a random UUID
    random_uuid = str(uuid.uuid4())
    print(f"\nTesting API Connection with random UUID: {random_uuid}")
    
    success, response = OneSignalService.send_notification(
        player_ids=[random_uuid],
        title="Test Notification",
        message="This is a test to verify credentials."
    )
    
    print(f"Success: {success}")
    print(f"Response: {response}")
    
    if isinstance(response, dict):
        if 'errors' in response:
            print(f"Received Errors: {response['errors']}")
            # Example error for valid auth but invalid player: {'errors': ['All included players are not subscribed']}
            if isinstance(response['errors'], list) and ('All included players are not subscribed' in response['errors'][0] or 'Invalid player_ids' in str(response['errors'])):
                 print("✅ Connection Successful! (API accepted the request but rejected the player ID as not subscribed)")
            else:
                 print("⚠️ Received errors, but connection likely established.")
        elif 'id' in response:
             print("✅ Notification Sent Successfully!")
    elif "HTTP Error" in str(response):
        if "401" in str(response) or "403" in str(response):
            print("❌ Auth Error - Credentials likely invalid")
        else:
            print(f"❌ Other HTTP Error: {response}")

if __name__ == "__main__":
    test_onesignal_config()
