from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import logging

from listings.models import Listing
from listings.serializers import ListingSerializer
from listings.normalizer import normalize_phone
from listings.extractor import extract_listing_fields, parse_search_query

logger = logging.getLogger(__name__)

class IngestListingView(APIView):
   
    def post(self, request):
        raw_text = request.data.get("raw_text")
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return Response(
                {"error": "Missing or invalid 'raw_text' in request body."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            extracted = extract_listing_fields(raw_text)
            
            if not extracted.property_type or not extracted.city or extracted.area <= 0:
                return Response(
                    {
                        "error": "Failed to extract valid listing details. Ensure property_type, city, and area are present.",
                        "extracted_fields": extracted.dict()
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
                
            normalized_phone = normalize_phone(extracted.contact_phone)
            if not normalized_phone:
                normalized_phone = "+966000000000"
                
            with transaction.atomic():
               
                existing = None
                if normalized_phone != "+966000000000":
                    existing = Listing.objects.select_for_update().filter(
                        contact_phone=normalized_phone,
                        city__iexact=extracted.city.strip(),
                        property_type__iexact=extracted.property_type.strip(),
                        area__gte=extracted.area - 1.0,
                        area__lte=extracted.area + 1.0
                    ).first()
                
                if existing:
                    if extracted.price is not None:
                        existing.price = extracted.price
                    existing.transaction_type = extracted.transaction_type
                    existing.raw_text = raw_text.strip()
                    existing.save()
                    action = "updated"
                    instance = existing
                    logger.info(f"Duplicate found for contact {normalized_phone}. Listing ID {existing.id} updated.")
                else:
                    instance = Listing.objects.create(
                        property_type=extracted.property_type.strip().lower(),
                        transaction_type=extracted.transaction_type.strip().lower(),
                        city=extracted.city.strip(),
                        price=extracted.price,
                        area=extracted.area,
                        contact_phone=normalized_phone,
                        raw_text=raw_text.strip()
                    )
                    action = "inserted"
                    logger.info(f"New listing inserted. Listing ID {instance.id} created.")
            
            serializer = ListingSerializer(instance)
            response_data = serializer.data
            response_data["action"] = action
            
            return Response(
                response_data,
                status=status.HTTP_200_OK if action == "updated" else status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Error ingesting listing: {e}", exc_info=True)
            return Response(
                {"error": f"Internal server error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SearchListingView(APIView):
    
    def get(self, request):
        city = request.query_params.get("city")
        property_type = request.query_params.get("property_type")
        max_price = request.query_params.get("max_price")
        min_area = request.query_params.get("min_area")
        
        queryset = Listing.objects.all().order_by("-updated_at")
        
        if city:
            queryset = queryset.filter(city__iexact=city.strip())
        if property_type:
            queryset = queryset.filter(property_type__iexact=property_type.strip())
        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                return Response(
                    {"error": "Invalid 'max_price' query parameter. Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        if min_area:
            try:
                queryset = queryset.filter(area__gte=float(min_area))
            except ValueError:
                return Response(
                    {"error": "Invalid 'min_area' query parameter. Must be a number."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        serializer = ListingSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MatchListingView(APIView):
 
    def get(self, request):
        q = request.query_params.get("q")
        if not q or not isinstance(q, str) or not q.strip():
            return Response(
                {"error": "Missing or empty 'q' query parameter."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            filters = parse_search_query(q)
            
            queryset = Listing.objects.all().order_by("-updated_at")
            
            if filters.city:
                queryset = queryset.filter(city__iexact=filters.city.strip())
            if filters.property_type:
                queryset = queryset.filter(property_type__iexact=filters.property_type.strip())
            if filters.max_price is not None:
                queryset = queryset.filter(price__lte=filters.max_price)
            if filters.min_area is not None:
                queryset = queryset.filter(area__gte=filters.min_area)
                
            serializer = ListingSerializer(queryset, many=True)
            
            return Response({
                "filters_applied": {
                    "city": filters.city,
                    "property_type": filters.property_type,
                    "max_price": filters.max_price,
                    "min_area": filters.min_area
                },
                "results": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error parsing or executing natural language query: {e}", exc_info=True)
            return Response(
                {"error": f"Failed to process query: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
