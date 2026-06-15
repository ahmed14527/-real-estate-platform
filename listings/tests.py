from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal

from listings.models import Listing
from listings.normalizer import normalize_phone
from listings.extractor import mock_extract_listing, mock_parse_search_query

class PhoneNormalizationTestCase(APITestCase):
    def test_phone_normalization_formats(self):
        self.assertEqual(normalize_phone("0551234567"), "+966551234567")
        
        self.assertEqual(normalize_phone("٠٥٥١٢٣٤٥٦٧"), "+966551234567")
        
        self.assertEqual(normalize_phone("966500112233+"), "+966500112233")
        
        self.assertEqual(normalize_phone("0512345678"), "+966512345678")
        
        self.assertEqual(normalize_phone("٠٥٦٧٧٨٨٩٩"), "+96656778899")


class ListingIngestTestCase(APITestCase):
    def setUp(self):
        self.ingest_url = reverse('ingest-listing')
        
        self.listing_1_text = (
            "للبيع أرض صناعية بالدمام المنطقة الصناعية الثانية، "
            "المساحة ١٢٥٠ متر، السعر ٢٫٨ مليون ريال قابل للتفاوض. للتواصل: ٠٥٥١٢٣٤٥٦٧"
        )
        
        self.listing_2_text = (
            "أرض صناعية الدمام ١٢٥٠م للبيع 2800000 — جوال 0551234567"
        )
        
        self.listing_3_text = (
            "مستودع للإيجار بالدمام، مساحة ٨٠٠ متر، الإيجار السنوي ١٥٠ ألف. الرقم 966500112233+"
        )

    def test_ingest_and_deduplicate(self):
        response = self.client.post(self.ingest_url, {"raw_text": self.listing_1_text}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["action"], "inserted")
        self.assertEqual(response.data["property_type"], "industrial land")
        self.assertEqual(response.data["city"], "Dammam")
        self.assertEqual(response.data["contact_phone"], "+966551234567")
        self.assertEqual(Decimal(str(response.data["area"])), Decimal("1250.0"))
        self.assertEqual(Decimal(str(response.data["price"])), Decimal("2800000.0"))
        
        self.assertEqual(Listing.objects.count(), 1)
        listing_id = response.data["id"]

      
        response_dup = self.client.post(self.ingest_url, {"raw_text": self.listing_2_text}, format='json')
        self.assertEqual(response_dup.status_code, status.HTTP_200_OK)
        self.assertEqual(response_dup.data["action"], "updated")
        self.assertEqual(response_dup.data["id"], listing_id) 
        
        self.assertEqual(response_dup.data["raw_text"], self.listing_2_text)
        
        self.assertEqual(Listing.objects.count(), 1)

    def test_ingest_different_listings(self):
        res1 = self.client.post(self.ingest_url, {"raw_text": self.listing_1_text}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        
        res3 = self.client.post(self.ingest_url, {"raw_text": self.listing_3_text}, format='json')
        self.assertEqual(res3.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res3.data["action"], "inserted")
        self.assertEqual(res3.data["property_type"], "warehouse")
        self.assertEqual(res3.data["transaction_type"], "rent")
        self.assertEqual(res3.data["contact_phone"], "+966500112233")
        self.assertEqual(Decimal(str(res3.data["price"])), Decimal("150000.0"))
        
        self.assertEqual(Listing.objects.count(), 2)

    def test_ingest_invalid_inputs(self):
        response = self.client.post(self.ingest_url, {"raw_text": ""}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        response = self.client.post(self.ingest_url, {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ListingSearchTestCase(APITestCase):
    def setUp(self):
        self.search_url = reverse('search-listings')
        
        Listing.objects.create(
            property_type="industrial land",
            transaction_type="sale",
            city="Dammam",
            price=2800000.0,
            area=1250.0,
            contact_phone="+966551234567",
            raw_text="Sample 1"
        )
        
        Listing.objects.create(
            property_type="warehouse",
            transaction_type="rent",
            city="Dammam",
            price=150000.0,
            area=800.0,
            contact_phone="+966500112233",
            raw_text="Sample 2"
        )
        
        Listing.objects.create(
            property_type="villa",
            transaction_type="sale",
            city="Khobar",
            price=1200000.0,
            area=400.0,
            contact_phone="+966539988776",
            raw_text="Sample 3"
        )

    def test_search_by_city(self):
        response = self.client.get(self.search_url, {"city": "Dammam"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        response_khobar = self.client.get(self.search_url, {"city": "khobar"})
        self.assertEqual(response_khobar.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_khobar.data), 1)
        self.assertEqual(response_khobar.data[0]["property_type"], "villa")

    def test_search_by_property_type(self):
        response = self.client.get(self.search_url, {"property_type": "warehouse"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["property_type"], "warehouse")

    def test_search_by_max_price(self):
        response = self.client.get(self.search_url, {"max_price": "200000"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["property_type"], "warehouse")
        
        response_mid = self.client.get(self.search_url, {"max_price": "1500000"})
        self.assertEqual(response_mid.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_mid.data), 2)

    def test_search_by_min_area(self):
        response = self.client.get(self.search_url, {"min_area": "1000"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["property_type"], "industrial land")


class ListingMatchTestCase(APITestCase):
    def setUp(self):
        self.match_url = reverse('match-listings')
        
        Listing.objects.create(
            property_type="industrial land",
            transaction_type="sale",
            city="Dammam",
            price=2800000.0,
            area=1250.0,
            contact_phone="+966551234567",
            raw_text="Sample 1"
        )
        
        Listing.objects.create(
            property_type="warehouse",
            transaction_type="rent",
            city="Dammam",
            price=150000.0,
            area=800.0,
            contact_phone="+966500112233",
            raw_text="Sample 2"
        )

    def test_natural_language_search_match(self):
        query = "أبغى أرض صناعية بالدمام تحت ٣ مليون"
        response = self.client.get(self.match_url, {"q": query})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        filters = response.data["filters_applied"]
        self.assertEqual(filters["city"], "Dammam")
        self.assertEqual(filters["property_type"], "industrial land")
        self.assertEqual(filters["max_price"], 3000000.0)
        
        results = response.data["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["property_type"], "industrial land")
        self.assertEqual(results[0]["city"], "Dammam")


class ListingIngestExtraTestCase(APITestCase):
    def setUp(self):
        self.ingest_url = reverse('ingest-listing')

    def test_trap_plot_number(self):
       
        raw_text = (
            "للبيع أرض بالدمام حي الأمانة، قطعة رقم 12500، المساحة 950 متر، "
            "السعر ٢٫٨ مليون ريال. للتواصل: ٠٥١٢٣٤٥٦٧٨"
        )
        response = self.client.post(self.ingest_url, {"raw_text": raw_text}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["action"], "inserted")
        self.assertEqual(Decimal(str(response.data["area"])), Decimal("950.0"))
        self.assertEqual(Decimal(str(response.data["price"])), Decimal("2800000.0"))
        self.assertEqual(response.data["contact_phone"], "+966512345678")

    def test_best_effort_phone_normalization_no_drop(self):
       
        raw_text = "للبيع أرض بالدمام حي الشعلة مساحة ٦٠٠ متر السعر 4000000 ريال، التواصل خاص"
        response = self.client.post(self.ingest_url, {"raw_text": raw_text}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["action"], "inserted")
        self.assertEqual(response.data["contact_phone"], "+966000000000")
        
     
        raw_text_2 = "للبيع أرض بالدمام حي الشعلة مساحة ٦٠٠ متر السعر 4500000 ريال، التواصل خاص"
        response_2 = self.client.post(self.ingest_url, {"raw_text": raw_text_2}, format='json')
        self.assertEqual(response_2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_2.data["action"], "inserted")
        self.assertEqual(response_2.data["contact_phone"], "+966000000000")
        
        self.assertEqual(Listing.objects.filter(contact_phone="+966000000000").count(), 2)

    def test_deduplicate_keeps_existing_price_when_new_price_is_none(self):
        # 1. Ingest a listing with a price
        raw_text_1 = "للبيع أرض بالدمام مساحة ١١٠٠ متر بسعر ٢ مليون ريال للتواصل 0559999999"
        res1 = self.client.post(self.ingest_url, {"raw_text": raw_text_1}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data["action"], "inserted")
        self.assertEqual(Decimal(str(res1.data["price"])), Decimal("2000000.0"))
        
        # 2. Ingest duplicate listing with NO price
        raw_text_2 = "أرض بالدمام مساحة ١١٠٠ متر للتواصل 0559999999"
        res2 = self.client.post(self.ingest_url, {"raw_text": raw_text_2}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["action"], "updated")
        
        # 3. Assert that the price in the DB did NOT get overwritten to None
        listing = Listing.objects.get(id=res2.data["id"])
        self.assertEqual(listing.price, Decimal("2000000.00"))
