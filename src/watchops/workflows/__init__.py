"""Workflow definitions for WatchOps."""

from .nginx_5xx import Nginx5xxWorkflow
from .http_error_rate import HttpErrorRateWorkflow
from .cpu_spike import CpuSpikeWorkflow

__all__ = [
    "Nginx5xxWorkflow",
    "HttpErrorRateWorkflow",
    "CpuSpikeWorkflow",
]
