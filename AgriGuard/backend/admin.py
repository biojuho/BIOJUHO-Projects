"""
AgriGuard Admin Panel — SQLAdmin 기반 어드민 UI
http://localhost:8002/admin 에서 접근
"""

import os

from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from database import engine
from models import User, Product, TrackingEvent, Certificate, SensorReading


# ── Authentication ──────────────────────────────────────────

class AdminAuth(AuthenticationBackend):
    """Simple password-based admin auth. Set ADMIN_PASSWORD in .env."""

    async def login(self, request: Request) -> bool:
        form = await request.form()
        password = form.get("password", "")
        expected = os.environ.get("ADMIN_PASSWORD", "agriguard-admin")
        if password == expected:
            request.session.update({"admin_authenticated": True})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return request.session.get("admin_authenticated", False)


# ── Model Views ─────────────────────────────────────────────

class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-users"

    column_list = [User.id, User.name, User.role, User.organization, User.created_at]
    column_searchable_list = [User.name, User.organization, User.role]
    column_sortable_list = [User.name, User.role, User.created_at]
    column_default_sort = ("created_at", True)
    can_export = True
    page_size = 25


class ProductAdmin(ModelView, model=Product):
    name = "Product"
    name_plural = "Products"
    icon = "fa-solid fa-box"

    column_list = [
        Product.id, Product.name, Product.category,
        Product.origin, Product.is_verified,
        Product.requires_cold_chain, Product.harvest_date,
    ]
    column_searchable_list = [Product.name, Product.category, Product.origin]
    column_sortable_list = [Product.name, Product.category, Product.harvest_date, Product.is_verified]
    column_default_sort = ("name", False)
    can_export = True
    export_types = ["csv", "json"]
    page_size = 25

    @action(name="verify", label="Mark Verified", confirmation_message="Mark selected products as verified?")
    async def action_verify(self, request: Request) -> None:
        from sqlalchemy.orm import Session
        from database import SessionLocal

        pks = request.query_params.get("pks", "").split(",")
        db: Session = SessionLocal()
        try:
            db.query(Product).filter(Product.id.in_(pks)).update(
                {"is_verified": True}, synchronize_session="fetch"
            )
            db.commit()
        finally:
            db.close()


class TrackingEventAdmin(ModelView, model=TrackingEvent):
    name = "Tracking Event"
    name_plural = "Tracking Events"
    icon = "fa-solid fa-truck"

    column_list = [
        TrackingEvent.id, TrackingEvent.product_id,
        TrackingEvent.status, TrackingEvent.location, TrackingEvent.timestamp,
    ]
    column_searchable_list = [TrackingEvent.status, TrackingEvent.location]
    column_sortable_list = [TrackingEvent.timestamp, TrackingEvent.status]
    column_default_sort = ("timestamp", True)
    can_export = True
    page_size = 50


class CertificateAdmin(ModelView, model=Certificate):
    name = "Certificate"
    name_plural = "Certificates"
    icon = "fa-solid fa-certificate"

    column_list = [
        Certificate.cert_id, Certificate.product_id,
        Certificate.cert_type, Certificate.issued_by, Certificate.issue_date,
    ]
    column_searchable_list = [Certificate.cert_type, Certificate.issued_by]
    column_sortable_list = [Certificate.issue_date, Certificate.cert_type]
    column_default_sort = ("issue_date", True)
    can_export = True
    page_size = 25


class SensorReadingAdmin(ModelView, model=SensorReading):
    name = "Sensor Reading"
    name_plural = "Sensor Readings"
    icon = "fa-solid fa-temperature-half"

    column_list = [
        SensorReading.sensor_id, SensorReading.temperature,
        SensorReading.humidity, SensorReading.battery,
        SensorReading.zone, SensorReading.status, SensorReading.timestamp,
    ]
    column_searchable_list = [SensorReading.sensor_id, SensorReading.zone, SensorReading.status]
    column_sortable_list = [SensorReading.timestamp, SensorReading.temperature, SensorReading.humidity]
    column_default_sort = ("timestamp", True)
    can_export = True
    export_max_rows = 10000
    page_size = 50


# ── Admin Factory ───────────────────────────────────────────

def setup_admin(app) -> Admin:
    """Mount SQLAdmin on the FastAPI app. Call from main.py."""
    secret_key = os.environ.get("SECRET_KEY", "agriguard-dev-secret-change-me")
    auth_backend = AdminAuth(secret_key=secret_key)

    admin = Admin(
        app,
        engine,
        authentication_backend=auth_backend,
        title="AgriGuard Admin",
    )

    admin.add_view(UserAdmin)
    admin.add_view(ProductAdmin)
    admin.add_view(TrackingEventAdmin)
    admin.add_view(CertificateAdmin)
    admin.add_view(SensorReadingAdmin)

    return admin
