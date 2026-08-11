from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.core.scope import ScopeContext
from app.models import (
    AIChatSession,
    AuditLog,
    Branch,
    BusinessGroup,
    BusinessProfile,
    Category,
    Company,
    Customer,
    CustomerLedgerEntry,
    CustomerPayment,
    FiscalPeriod,
    Forecast,
    GSTRegistration,
    Inventory,
    InventoryBatch,
    Invoice,
    InvoiceSequence,
    PaymentMode,
    PrintTemplate,
    Product,
    ProductBarcode,
    ProductPriceHistory,
    PurchaseOrder,
    Sale,
    SerialNumber,
    StockMovement,
    Supplier,
    User,
    UserRole,
)


class ScopeViolationError(ValueError):
    """Raised when a write attempts to cross the authenticated venture scope."""


class ScopedSession(Session):
    """SQLAlchemy Session that applies request scope when one has been bound."""


# User is intentionally excluded from this generic business-row read filter.
# Identity rows frequently appear as aliased creator/approver helper joins in
# already-scoped business queries. Applying User.company_id as loader criteria to
# those aliases can generate invalid SQL and is unnecessary for business-data
# isolation. Authentication loads users explicitly, and P3 user-management APIs
# apply dedicated user-scope predicates instead.
COMPANY_MODELS = (
    Branch,
    BusinessProfile,
    Category,
    Customer,
    CustomerLedgerEntry,
    CustomerPayment,
    FiscalPeriod,
    Forecast,
    GSTRegistration,
    Inventory,
    InventoryBatch,
    Invoice,
    InvoiceSequence,
    PaymentMode,
    PrintTemplate,
    Product,
    ProductBarcode,
    ProductPriceHistory,
    PurchaseOrder,
    Sale,
    SerialNumber,
    StockMovement,
    Supplier,
    AIChatSession,
    AuditLog,
)

BRANCH_MODELS = (
    Branch,
    Customer,
    CustomerLedgerEntry,
    CustomerPayment,
    Forecast,
    GSTRegistration,
    Inventory,
    InventoryBatch,
    Invoice,
    PurchaseOrder,
    Sale,
    SerialNumber,
    StockMovement,
    AIChatSession,
)

# Foreign-object relationships whose company ownership must match the active
# venture on every create/update. Children that are reached only through a
# scoped parent (for example InvoiceItem -> Invoice) are protected by the
# parent's scoped lookup/transaction and are not duplicated here.
REFERENCE_COMPANY_MODELS: dict[type[Any], tuple[tuple[str, type[Any]], ...]] = {
    Product: (("category_id", Category), ("supplier_id", Supplier)),
    ProductBarcode: (("product_id", Product),),
    ProductPriceHistory: (("product_id", Product),),
    InventoryBatch: (("product_id", Product), ("branch_id", Branch)),
    SerialNumber: (("product_id", Product), ("branch_id", Branch)),
    Inventory: (("product_id", Product), ("branch_id", Branch)),
    StockMovement: (("product_id", Product), ("branch_id", Branch)),
    Customer: (("branch_id", Branch),),
    CustomerLedgerEntry: (("customer_id", Customer), ("branch_id", Branch)),
    CustomerPayment: (("customer_id", Customer), ("branch_id", Branch), ("payment_mode_id", PaymentMode)),
    Sale: (("branch_id", Branch),),
    Invoice: (("branch_id", Branch), ("customer_id", Customer), ("sale_id", Sale)),
    PurchaseOrder: (("supplier_id", Supplier), ("branch_id", Branch)),
    Forecast: (("product_id", Product), ("category_id", Category), ("branch_id", Branch)),
    AIChatSession: (("user_id", User), ("branch_id", Branch)),
    AuditLog: (("user_id", User),),
}


def bind_scope(session: Session, scope: ScopeContext) -> None:
    session.info["scope_context"] = scope


def current_scope(session: Session) -> ScopeContext | None:
    value = session.info.get("scope_context")
    return value if isinstance(value, ScopeContext) else None


def _scoped_get(session: Session, model: type[Any], object_id: int) -> Any | None:
    return session.get(model, object_id, execution_options={"scope_bypass": True})


@event.listens_for(ScopedSession, "do_orm_execute")
def _apply_read_scope(execute_state: ORMExecuteState) -> None:
    if not execute_state.is_select or execute_state.execution_options.get("scope_bypass"):
        return

    scope = current_scope(execute_state.session)
    if scope is None or scope.all_companies:
        return
    if scope.company_id is None:
        # A non-global user without a company is an invalid authorization state.
        execute_state.statement = execute_state.statement.where(False)
        return

    statement = execute_state.statement
    company_id = scope.company_id
    business_group_id = scope.business_group_id

    for model in COMPANY_MODELS:
        statement = statement.options(
            with_loader_criteria(
                model,
                model.company_id == company_id,
                include_aliases=True,
            )
        )

    statement = statement.options(
        with_loader_criteria(Company, Company.id == company_id, include_aliases=True),
        with_loader_criteria(
            BusinessGroup,
            BusinessGroup.id == business_group_id,
            include_aliases=True,
        ),
    )

    if scope.branch_ids:
        branch_ids = scope.branch_ids
        statement = statement.options(
            with_loader_criteria(Branch, Branch.id.in_(branch_ids), include_aliases=True)
        )
        for model in BRANCH_MODELS:
            if model is Branch:
                continue
            statement = statement.options(
                with_loader_criteria(
                    model,
                    model.branch_id.in_(branch_ids),
                    include_aliases=True,
                )
            )

    execute_state.statement = statement


@event.listens_for(ScopedSession, "before_flush")
def _enforce_write_scope(session: ScopedSession, _flush_context: Any, _instances: Any) -> None:
    scope = current_scope(session)
    if scope is None:
        # Migrations, deterministic seeds, and trusted maintenance scripts may use
        # a session without request scope. Runtime API sessions bind scope during
        # authentication before business writes occur.
        return

    for obj in set(session.new).union(session.dirty):
        if isinstance(obj, User) and obj.role == UserRole.SUPER_ADMIN:
            if not scope.all_companies and obj.id != scope.user_id:
                raise ScopeViolationError("Only Super Admin may create or modify a Super Admin account.")
            continue

        if not scope.all_companies and hasattr(type(obj), "company_id"):
            if scope.company_id is None:
                raise ScopeViolationError("Authenticated user has no company scope.")
            object_company_id = getattr(obj, "company_id", None)
            if object_company_id is None:
                setattr(obj, "company_id", scope.company_id)
            elif object_company_id != scope.company_id:
                raise ScopeViolationError("Write attempted outside the authenticated company scope.")

        if not scope.all_companies and scope.branch_ids and hasattr(type(obj), "branch_id"):
            branch_id = getattr(obj, "branch_id", None)
            if branch_id is not None and branch_id not in scope.branch_ids:
                raise ScopeViolationError("Write attempted outside the authenticated branch scope.")

        references = REFERENCE_COMPANY_MODELS.get(type(obj), ())
        if not references:
            continue
        object_company_id = getattr(obj, "company_id", None)
        if object_company_id is None:
            continue

        with session.no_autoflush:
            for attribute, target_model in references:
                target_id = getattr(obj, attribute, None)
                if target_id is None:
                    continue
                target = _scoped_get(session, target_model, target_id)
                if target is None:
                    raise ScopeViolationError(f"Referenced {target_model.__name__} does not exist.")
                target_company_id = getattr(target, "company_id", None)
                if target_company_id is not None and target_company_id != object_company_id:
                    raise ScopeViolationError(
                        f"Referenced {target_model.__name__} belongs to a different company."
                    )
