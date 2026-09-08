from __future__ import annotations

"""Production composition for the public API.

`api.app` remains the small core FastAPI app used heavily by tests. This module
adds platform middleware and multi-league routes without starting the separate
push monitor. Keeping composition explicit prevents the main API and push worker
from accidentally becoming the same process as the product grows.
"""

from api.app import app
from api.platform_middleware import install_platform_middleware
from api.tenant_api import register_tenant_routes

register_tenant_routes(app)
install_platform_middleware(app)
