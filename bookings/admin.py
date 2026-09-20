from django.contrib import admin
from django.utils.html import format_html
from .models import Booking, ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'phone', 'created_at', 'is_read']
    list_filter = ['is_read', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    ordering = ['-created_at']


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    """
    Admin interface for Booking model with advanced features
    """
    list_display = [
        'id', 'user_link', 'room_link', 'booking_type', 
        'start_time', 'end_time', 'status_badge', 
        'total_price', 'created_at'
    ]
    list_filter = [
        'status', 'booking_type', 'created_at', 
        'start_time', 'room__room_type'
    ]
    search_fields = [
        'user__username', 'user__email', 'guest_name', 
        'guest_email', 'room__room_number'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Booking Information', {
            'fields': ('user', 'room', 'booking_type', 'status')
        }),
        ('Time Schedule', {
            'fields': (
                'start_time', 'end_time', 
                'actual_checkin_time', 'actual_checkout_time'
            )
        }),
        ('Guest Information', {
            'fields': (
                'guest_name', 'guest_email', 
                'guest_phone', 'number_of_guests'
            )
        }),
        ('Pricing', {
            'fields': ('total_price',)
        }),
        ('Additional Information', {
            'fields': ('special_requests', 'notes'),
            'classes': ('collapse',)
        }),
        ('Cancellation Details', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'created_at', 'updated_at', 
        'actual_checkin_time', 'actual_checkout_time', 
        'cancelled_at'
    ]
    
    list_per_page = 25
    
    def user_link(self, obj):
        """Display user as clickable link"""
        return format_html(
            '<a href="/admin/auth/user/{}/change/">{}</a>',
            obj.user.id, obj.user.username
        )
    user_link.short_description = 'User'
    
    def room_link(self, obj):
        """Display room as clickable link"""
        return format_html(
            '<a href="/admin/rooms/room/{}/change/">Room {}</a>',
            obj.room.id, obj.room.room_number
        )
    room_link.short_description = 'Room'
    
    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'pending': '#FFA500',
            'confirmed': '#4CAF50',
            'checked_in': '#2196F3',
            'checked_out': '#9E9E9E',
            'cancelled': '#F44336',
            'expired': '#795548'
        }
        color = colors.get(obj.status, '#000000')
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        """Optimize queryset with select_related"""
        return super().get_queryset(request).select_related('user', 'room')
    
    actions = ['mark_as_confirmed', 'mark_as_cancelled']
    
    def mark_as_confirmed(self, request, queryset):
        """Bulk action to confirm bookings"""
        updated = queryset.filter(status='pending').update(status='confirmed')
        self.message_user(request, f'{updated} bookings marked as confirmed.')
    mark_as_confirmed.short_description = 'Mark selected as Confirmed'
    
    def mark_as_cancelled(self, request, queryset):
        """Bulk action to cancel bookings"""
        from django.utils import timezone
        updated = 0
        for booking in queryset.filter(status__in=['pending', 'confirmed']):
            booking.status = 'cancelled'
            booking.cancelled_at = timezone.now()
            booking.save()
            updated += 1
        self.message_user(request, f'{updated} bookings cancelled.')
    mark_as_cancelled.short_description = 'Cancel selected bookings'