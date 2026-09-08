from __future__ import annotations

"""Production composition for the public API.

The main service owns product reads, multi-league state and analysis. The push
worker is separate and should not be the dependency that ordinary app screens
need in order to load.
"""

from api.app import app
from api.platform_middleware import install_platform_middleware
from api.product_api import register_product_routes
from api.tenant_api import register_tenant_routes

register_product_routes(app)
register_tenant_routes(app)
install_platform_middleware(app)
