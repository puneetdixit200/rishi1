from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.core.config import DeploymentMode, Settings, settings


def include_local_hub_routes(app: FastAPI, app_settings: Settings) -> None:
    from app.api.routes.ai import router as ai_router
    from app.api.routes.auth import router as auth_router
    from app.api.routes.branches import router as branches_router
    from app.api.routes.business_settings import router as business_settings_router
    from app.api.routes.categories import router as categories_router
    from app.api.routes.customers import router as customers_router
    from app.api.routes.dashboard import router as dashboard_router
    from app.api.routes.exports import router as exports_router
    from app.api.routes.forecasts import router as forecasts_router
    from app.api.routes.inventory import router as inventory_router
    from app.api.routes.invoices import router as invoices_router
    from app.api.routes.products import router as products_router
    from app.api.routes.purchase_orders import router as purchase_orders_router
    from app.api.routes.sales import router as sales_router
    from app.api.routes.suppliers import router as suppliers_router

    for router in (
        auth_router,
        business_settings_router,
        categories_router,
        suppliers_router,
        branches_router,
        products_router,
        customers_router,
        invoices_router,
        inventory_router,
        sales_router,
        dashboard_router,
        purchase_orders_router,
        forecasts_router,
        exports_router,
        ai_router,
    ):
        app.include_router(router, prefix=app_settings.api_prefix)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or settings
    docs_enabled = resolved_settings.resolved_api_docs_enabled
    app = FastAPI(
        title=resolved_settings.app_name,
        description=(
            "Local operational retail and Cafe API."
            if resolved_settings.deployment_mode == DeploymentMode.LOCAL_HUB
            else "Limited hybrid cloud coordination gateway."
        ),
        version="0.1.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix=resolved_settings.api_prefix)
    if resolved_settings.deployment_mode == DeploymentMode.LOCAL_HUB:
        include_local_hub_routes(app, resolved_settings)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            content = {"error": detail}
        else:
            content = {
                "error": {
                    "code": "http_error",
                    "message": str(detail),
                }
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=exc.headers,
        )

    return app


app = create_app()
