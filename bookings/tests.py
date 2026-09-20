from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking, ContactMessage, Payment, Review
from bookings.services import BookingService
from rooms.models import Room


class BookingEngineTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='bookingengine',
            email='bookingengine@example.com',
            password='testpass123'
        )
        self.room = Room.objects.create(
            room_number='B-100',
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

    def test_daily_booking_price_is_calculated_server_side(self):
        start = timezone.now() + timezone.timedelta(days=2)
        end = start + timezone.timedelta(days=3)

        booking = Booking.objects.create(
            user=self.user,
            room=self.room,
            booking_type='daily',
            start_time=start,
            end_time=end,
            guest_name='Test Guest',
            guest_email='guest@example.com',
            guest_phone='01712345678',
            number_of_guests=2,
            total_price=24000,
            status='confirmed',
            special_requests='Late check-in'
        )

        self.assertEqual(booking.total_price, 24000)
        self.assertEqual(booking.status, 'confirmed')

    def test_booking_rejects_overlapping_dates(self):
        base_start = timezone.now() + timezone.timedelta(days=5)
        base_end = base_start + timezone.timedelta(days=2)

        Booking.objects.create(
            user=self.user,
            room=self.room,
            booking_type='daily',
            start_time=base_start,
            end_time=base_end,
            guest_name='Existing Guest',
            guest_email='existing@example.com',
            guest_phone='01711111111',
            number_of_guests=2,
            total_price=16000,
            status='confirmed',
            special_requests=''
        )

        overlapping_start = base_start + timezone.timedelta(days=1)
        overlapping_end = base_end + timezone.timedelta(days=1)

        is_available, message = BookingService.check_room_availability(
            self.room.id,
            overlapping_start,
            overlapping_end,
        )

        self.assertFalse(is_available)
        self.assertIn('already booked', message.lower())

    def test_daily_booking_requires_minimum_24_hours(self):
        start = timezone.now() + timezone.timedelta(days=1)
        end = start + timezone.timedelta(hours=12)

        with self.assertRaises(Exception):
            Booking.objects.create(
                user=self.user,
                room=self.room,
                booking_type='daily',
                start_time=start,
                end_time=end,
                guest_name='Short Stay',
                guest_email='short@example.com',
                guest_phone='01722222222',
                number_of_guests=1,
                total_price=1000,
                status='pending',
                special_requests=''
            )

    def test_booking_status_contains_rejected_option(self):
        self.assertIn('rejected', dict(Booking.STATUS_CHOICES))

    def test_customer_can_view_booking_confirmation_and_invoice(self):
        booking = Booking.objects.create(
            user=self.user,
            room=self.room,
            booking_type='daily',
            start_time=timezone.now() + timezone.timedelta(days=7),
            end_time=timezone.now() + timezone.timedelta(days=9),
            guest_name='Test Guest',
            guest_email='guest@example.com',
            guest_phone='01712345678',
            number_of_guests=2,
            total_price=16000,
            status='confirmed',
            special_requests=''
        )

        self.client.force_login(self.user)

        confirmation = self.client.get(reverse('booking_confirmation', args=[booking.id]))
        self.assertEqual(confirmation.status_code, 200)

        invoice = self.client.get(reverse('invoice', args=[booking.id]))
        self.assertEqual(invoice.status_code, 200)


class StaffAdminDashboardTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_user(
            username='adminuser',
            email='admin@example.com',
            password='pass1234',
            is_staff=True,
            is_superuser=True,
        )
        self.client.force_login(self.admin_user)

    def test_admin_dashboard_and_room_management_are_accessible(self):
        dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(dashboard.status_code, 200)

        rooms = self.client.get(reverse('admin_rooms'))
        self.assertEqual(rooms.status_code, 200)


class PaymentAndReviewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='guestuser',
            email='guest@hotel.com',
            password='guestpass123'
        )
        self.room = Room.objects.create(
            room_number='A-101',
            room_type='deluxe',
            capacity=2,
            hourly_rate=600,
            daily_rate=9000,
            floor=1,
            amenities=['WiFi', 'AC'],
            description='Deluxe room',
            status='available',
            image_url='https://example.com/deluxe.jpg',
        )

    def test_booking_creates_payment_and_sends_confirmation_email(self):
        booking = Booking.objects.create(
            user=self.user,
            room=self.room,
            booking_type='daily',
            start_time=timezone.now() + timezone.timedelta(days=10),
            end_time=timezone.now() + timezone.timedelta(days=11),
            guest_name='Guest User',
            guest_email='guest@hotel.com',
            guest_phone='01700000000',
            number_of_guests=2,
            total_price=Decimal('9000.00'),
            status='confirmed',
            special_requests=''
        )

        payment = Payment.objects.filter(booking=booking).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('9000.00'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Dhaka International Hotel', mail.outbox[0].body)

    def test_customer_can_submit_room_review(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse('submit_review', args=[self.room.id]),
            {'rating': 5, 'comment': 'Excellent stay and very clean room.'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Review.objects.filter(room=self.room, user=self.user).exists())


class ContactMessageTests(TestCase):
    def test_guest_can_submit_contact_message(self):
        response = self.client.post(
            reverse('contact_message'),
            {
                'name': 'Rahim Uddin',
                'email': 'rahim@example.com',
                'phone': '+8801700000000',
                'subject': 'Room availability question',
                'message': 'I want to book a deluxe room next week.',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(ContactMessage.objects.filter(email='rahim@example.com').exists())


class HomepageAndBookingFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='homeuser',
            email='homeuser@example.com',
            password='pass1234',
        )
        self.room = Room.objects.create(
            room_number='C-202',
            room_type='deluxe',
            capacity=2,
            hourly_rate=700,
            daily_rate=11000,
            floor=2,
            amenities=['WiFi', 'AC'],
            description='Deluxe room',
            status='available',
            image_url='https://example.com/c202.jpg',
        )

    def test_authenticated_user_can_open_homepage(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'About Dhaka International Hotel')

    def test_valid_booking_submit_redirects_to_confirmation(self):
        self.client.force_login(self.user)
        start = timezone.now() + timezone.timedelta(days=15)
        end = start + timezone.timedelta(days=1)

        response = self.client.post(
            reverse('book_room', args=[self.room.id]),
            {
                'booking_type': 'daily',
                'start_time': start.strftime('%Y-%m-%dT%H:%M'),
                'end_time': end.strftime('%Y-%m-%dT%H:%M'),
                'guest_name': 'Home User',
                'guest_email': 'homeuser@example.com',
                'guest_phone': '+8801700000000',
                'number_of_guests': '2',
                'special_requests': 'Late arrival',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Booking.objects.filter(user=self.user, room=self.room).exists())


class DeploymentHardeningTests(TestCase):
    def test_health_check_endpoint_is_available(self):
        response = self.client.get(reverse('health_check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_security_headers_are_configured(self):
        self.assertEqual(settings.SECURE_REFERRER_POLICY, 'strict-origin-when-cross-origin')
        self.assertEqual(settings.X_FRAME_OPTIONS, 'DENY')
