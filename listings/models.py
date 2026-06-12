from django.db import models

class Listing(models.Model):
    property_type = models.CharField(max_length=100, db_index=True)       
    transaction_type = models.CharField(max_length=50)                  
    city = models.CharField(max_length=100, db_index=True)               
    price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, db_index=True)  
    area = models.DecimalField(max_digits=12, decimal_places=2, db_index=True)  
    contact_phone = models.CharField(max_length=50)                      
    raw_text = models.TextField()                                        
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "listings"
        indexes = [
            models.Index(fields=["contact_phone", "city", "property_type", "area"], name="listings_dedup_idx"),
        ]

    def __str__(self):
        return f"{self.property_type} in {self.city} - {self.transaction_type} ({self.area} sqm)"
