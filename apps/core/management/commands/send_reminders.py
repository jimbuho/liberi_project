from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Booking, Notification
from apps.notifications.utils import send_appointment_reminder_notification
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sends appointment reminders for upcoming bookings'

    def handle(self, *args, **options):
        now = timezone.now()
        # Look for bookings starting in the next 3 hours
        window_start = now
        window_end = now + timedelta(hours=3)
        
        bookings = Booking.objects.filter(
            status='accepted',
            payment_status='paid',
            scheduled_time__range=(window_start, window_end)
        )
        
        count = 0
        self.stdout.write(f"Checking {bookings.count()} bookings for reminders...")
        
        for booking in bookings:
            # Check if reminder already sent to customer
            # We assume if sent to customer, it was sent to provider too (handled in utils)
            already_sent = Notification.objects.filter(
                booking=booking,
                title='Recordatorio de Cita',
                notification_type='system' 
            ).exists()
            
            if not already_sent:
                try:
                    send_appointment_reminder_notification(booking)
                    count += 1
                    self.stdout.write(self.style.SUCCESS(f"Sent reminder for Booking {booking.id}"))
                except Exception as e:
                    logger.error(f"Error sending reminder for {booking.id}: {e}")
                    self.stdout.write(self.style.ERROR(f"Error sending reminder for {booking.id}: {e}"))
            else:
                self.stdout.write(f"Reminder already sent for Booking {booking.id}")
                    
        self.stdout.write(self.style.SUCCESS(f"Finished. Sent {count} reminders."))
