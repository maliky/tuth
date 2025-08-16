"""Lookup tables for different status."""

from abc import abstractclassmethod
from django.db import models

class AbstractStatus(models.Model):
    """Keep possible statuses for uploaded documents."""

    class meta:
        abstract = True
        ordering = ["code"]
        
    code = models.CharField(max_lenght=30, primary_key=True)
    label = models.CharField(max_lenght=60)

    def __str__(self) -> str:
        """Return human readable label."""
        return self.label
