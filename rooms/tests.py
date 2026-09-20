from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from bookings.models import Booking
from bookings.services import BookingService
from rooms.models import Room


class RoomManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='roomtester',
            email='roomtester@example.com',
            password='testpass123'
        )
        self.room = Room.objects.create(
            room_number='R-100',
            room_type='double',
            capacity=2,
            hourly_rate=500,
            daily_rate=8000,
            floor=2,
            amenities=['WiFi', 'AC'],
            description='Comfortable double room',
            status='available',
            image_url='https://example.com/room.jpg',
        )

    def test_room_model_is_created_with_expected_defaults(self):
        self.assertEqual(str(self.room), 'Room R-100 - Double')
        self.assertTrue(self.room.is_available_for_booking())
        self.assertEqual(self.room.capacity, 2)

    def test_room_search_filters_only_available_rooms(self):
        start = timezone.now() + timezone.timedelta(days=1)
        end = start + timezone.timedelta(days=2)

        available = BookingService.get_available_rooms(
            start_time=start,
            end_time=end,
            room_type='double',
            min_capacity=2,
        )

        self.assertIn(self.room, available)

    def test_booking_service_blocks_overlapping_booking_window(self):
        start = timezone.now() + timezone.timedelta(days=3)
        end = start + timezone.timedelta(days=1)

        Booking.objects.create(
            user=self.user,
            room=self.room,
            booking_type='daily',
            start_time=start,
            end_time=end,
            guest_name='Test Guest',
            guest_email='guest@example.com',
            guest_phone='01712345678',
            number_of_guests=2,
            total_price=8000,
            status='confirmed',
            special_requests=''
        )

        overlapping_start = start + timezone.timedelta(hours=12)
        overlapping_end = end + timezone.timedelta(hours=12)

        available = BookingService.get_available_rooms(
            start_time=overlapping_start,
            end_time=overlapping_end,
            room_type='double',
            min_capacity=2,
        )

        self.assertNotIn(self.room, available)

    def test_room_availability_check_rejects_maintenance_room(self):
        self.room.status = 'maintenance'
        self.room.save()

        start = timezone.now() + timezone.timedelta(days=4)
        end = start + timezone.timedelta(days=1)

        is_available, message = BookingService.check_room_availability(
            self.room.id,
            start,
            end,
        )

        self.assertFalse(is_available)
        self.assertIn('currently', message)
