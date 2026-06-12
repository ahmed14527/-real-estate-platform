from django.urls import re_path
from listings.views import IngestListingView, SearchListingView, MatchListingView

urlpatterns = [
    re_path(r'^listings/?$', IngestListingView.as_view(), name='ingest-listing'),
    re_path(r'^listings/search/?$', SearchListingView.as_view(), name='search-listings'),
    re_path(r'^listings/match/?$', MatchListingView.as_view(), name='match-listings'),
]
