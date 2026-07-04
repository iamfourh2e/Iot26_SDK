"""
iot26_edge — IoT26 edge SDK.

Usage::

    from iot26_edge import IoT26Gateway

    gw = IoT26Gateway(
        device_id    = "your-device-uuid",
        device_token = "eyJhbGci...",
        api_base     = "https://your-server.com",
        mqtt_broker  = "your-server.com",
    )
    gw.run()
"""

from .gateway import IoT26Gateway
from .client  import IoT26Client

__all__ = ["IoT26Gateway", "IoT26Client"]
__version__ = "0.1.0"
