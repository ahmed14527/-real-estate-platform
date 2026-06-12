from django.contrib import admin
from listings.models import Listing

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 
        'property_type', 
        'transaction_type', 
        'city', 
        'price', 
        'area', 
        'contact_phone', 
        'updated_at'
    )
    list_filter = ('property_type', 'transaction_type', 'city')
    search_fields = ('contact_phone', 'city', 'property_type', 'raw_text')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Extracted Data', {
            'fields': ('property_type', 'transaction_type', 'city', 'price', 'area', 'contact_phone')
        }),
        ('Original Listing', {
            'fields': ('raw_text',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
