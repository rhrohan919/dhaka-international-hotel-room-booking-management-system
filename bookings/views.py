from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
from datetime import datetime
from django.utils.dateparse import parse_datetime

from .models import Booking
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    BookingCreateSerializer, BookingSerializer, BookingListSerializer,
    CancelBookingSerializer
)
from .services import BookingService


# ============================================================================
# AUTHENTICATION VIEWS
# ============================================================================

class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate token for the new user
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'token': token.key
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    User login endpoint
    POST /api/auth/login/
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get or create token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'Login successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            },
            'token': token.key
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    User logout endpoint
    POST /api/auth/logout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Delete the user's token
        request.user.auth_token.delete()
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    User profile endpoint
    GET /api/auth/profile/
    PUT/PATCH /api/auth/profile/
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


# ============================================================================
# BOOKING VIEWS
# ============================================================================

# class BookingPagination(PageNumberPagination):
#     """Custom pagination for bookings"""
#     page_size = 10
#     page_size_query_param = 'page_size'
#     max_page_size = 100


class BookingListCreateView(generics.ListCreateAPIView):
    """
    List user bookings and create new bookings
    GET /api/bookings/
    POST /api/bookings/
    """
    permission_classes = [permissions.IsAuthenticated]
    # pagination_class = BookingPagination

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BookingCreateSerializer
        return BookingListSerializer

    def get_queryset(self):
        """Return bookings for the authenticated user with filters"""
        queryset = Booking.objects.filter(user=self.request.user).select_related('room')
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by booking type
        booking_type = self.request.query_params.get('booking_type', None)
        if booking_type:
            queryset = queryset.filter(booking_type=booking_type)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                queryset = queryset.filter(start_time__gte=start_dt)
            except ValueError:
                pass
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                queryset = queryset.filter(end_time__lte=end_dt)
            except ValueError:
                pass
        
        # Filter upcoming/past bookings
        filter_type = self.request.query_params.get('filter', None)
        if filter_type == 'upcoming':
            queryset = queryset.filter(
                status__in=['pending', 'confirmed'],
                start_time__gt=timezone.now()
            )
        elif filter_type == 'past':
            queryset = queryset.filter(
                Q(status__in=['checked_out', 'cancelled', 'expired']) |
                Q(end_time__lt=timezone.now())
            )
        elif filter_type == 'active':
            queryset = queryset.filter(
                status__in=['confirmed', 'checked_in'],
                start_time__lte=timezone.now(),
                end_time__gte=timezone.now()
            )
        
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        
        # Return detailed booking data
        detail_serializer = BookingSerializer(booking)
        return Response({
            'message': 'Booking created successfully',
            'booking': detail_serializer.data
        }, status=status.HTTP_201_CREATED)


class BookingDetailView(generics.RetrieveAPIView):
    """
    Retrieve booking details
    GET /api/bookings/{id}/
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Only return bookings for the authenticated user"""
        return Booking.objects.filter(user=self.request.user).select_related('room', 'user')


class BookingCheckInView(APIView):
    """
    Check-in to a booking
    POST /api/bookings/{id}/checkin/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.select_related('room').get(
                id=pk, 
                user=request.user
            )
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)

        success, message = BookingService.perform_checkin(booking)
        
        if not success:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = BookingSerializer(booking)
        return Response({
            'message': message,
            'booking': serializer.data
        }, status=status.HTTP_200_OK)


class BookingCheckOutView(APIView):
    """
    Check-out from a booking
    POST /api/bookings/{id}/checkout/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.select_related('room').get(
                id=pk, 
                user=request.user
            )
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)

        success, message, extra_charges = BookingService.perform_checkout(booking)
        
        if not success:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = BookingSerializer(booking)
        response_data = {
            'message': message,
            'booking': serializer.data
        }
        
        if extra_charges > 0:
            response_data['extra_charges'] = float(extra_charges)
            response_data['message'] += f' (Extra charges: ৳{extra_charges})'
        
        return Response(response_data, status=status.HTTP_200_OK)


class BookingCancelView(APIView):
    """
    Cancel a booking
    POST /api/bookings/{id}/cancel/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.select_related('room').get(
                id=pk, 
                user=request.user
            )
        except Booking.DoesNotExist:
            return Response({
                'error': 'Booking not found'
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = CancelBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        cancellation_reason = serializer.validated_data.get('cancellation_reason', '')
        success, message = BookingService.cancel_booking(booking, cancellation_reason)
        
        if not success:
            return Response({
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)

        detail_serializer = BookingSerializer(booking)
        return Response({
            'message': message,
            'booking': detail_serializer.data
        }, status=status.HTTP_200_OK)


class BookingHistoryView(generics.ListAPIView):
    """
    Get user's booking history
    GET /api/bookings/history/
    """
    serializer_class = BookingListSerializer
    permission_classes = [permissions.IsAuthenticated]
    # pagination_class = BookingPagination

    def get_queryset(self):
        """Return all bookings for the authenticated user, ordered by date"""
        return Booking.objects.filter(
            user=self.request.user
        ).select_related('room').order_by('-created_at')


# ============================================================================
# AVAILABILITY CHECK VIEW
# ============================================================================

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def check_availability(request):
    """
    Check room availability for a given time period
    GET /api/bookings/check-availability/?room_id=1&start_time=...&end_time=...
    """
    room_id = request.query_params.get('room_id')
    start_time_str = request.query_params.get('start_time')
    end_time_str = request.query_params.get('end_time')

    # Validate parameters
    if not all([room_id, start_time_str, end_time_str]):
        return Response({
            'error': 'room_id, start_time, and end_time are required'
        }, status=status.HTTP_400_BAD_REQUEST)

    try:

        start_time = parse_datetime(start_time_str)
        end_time = parse_datetime(end_time_str)
        
        if start_time is None or end_time is None:
            raise ValueError("Invalid datetime")
        
        # Make timezone-aware if naive
        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time)
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time)
            
    except (ValueError, TypeError):
        return Response({
            'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'
        }, status=status.HTTP_400_BAD_REQUEST)

    # Check availability
    is_available, message = BookingService.check_room_availability(
        room_id, start_time, end_time
    )

    return Response({
        'available': is_available,
        'message': message,
        'room_id': room_id,
        'start_time': start_time,
        'end_time': end_time
    }, status=status.HTTP_200_OK)
