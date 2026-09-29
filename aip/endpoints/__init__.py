# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
AIP Endpoints

Provides endpoint implementations for Device Server and Device Client.
"""

from .base import AIPEndpoint
from .client_endpoint import DeviceClientEndpoint
from .server_endpoint import DeviceServerEndpoint

__all__ = [
    "AIPEndpoint",
    "DeviceServerEndpoint",
    "DeviceClientEndpoint",
]
