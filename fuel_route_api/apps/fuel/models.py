from __future__ import annotations

import uuid

from django.db import models


class GeocodeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    OK = "ok", "OK"
    FAILED = "failed", "Failed"


class FuelStation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opis_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=128)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField(null=True, blank=True)
    retail_price = models.DecimalField(max_digits=10, decimal_places=6)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    geocode_status = models.CharField(
        max_length=16,
        choices=GeocodeStatus.choices,
        default=GeocodeStatus.PENDING,
    )
    geocode_source = models.CharField(max_length=32, null=True, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["geocode_status"]),
            models.Index(fields=["state"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.opis_id})"


class GeocodeCache(models.Model):
    address_hash = models.CharField(primary_key=True, max_length=64)
    address_normalized = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    formatted_address = models.TextField()
    source = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["address_normalized"])]
