from rest_framework import serializers
from listings.models import Listing

class ListingSerializer(serializers.ModelSerializer):
    price = serializers.FloatField(required=False, allow_null=True)
    area = serializers.FloatField()

    class Meta:
        model = Listing
        fields = [
            'id',
            'property_type',
            'transaction_type',
            'city',
            'price',
            'area',
            'contact_phone',
            'raw_text',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
