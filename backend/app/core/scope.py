from __future__ import annotations

from dataclasses import dataclass

from app.models.user import User, UserRole


@dataclass(frozen=True)
class ScopeContext:
    """Server-derived venture and branch authorization context.

    Client-supplied company/branch values never create authority. The context is
    derived from the current database user on every authenticated request.
    """

    user_id: int
    role: UserRole
    business_group_id: int
    company_id: int | None
    all_companies: bool
    branch_ids: tuple[int, ...]
    permissions: frozenset[str]

    @property
    def all_branches(self) -> bool:
        return not self.branch_ids


ROLE_PERMISSIONS: dict[UserRole, frozenset[str]] = {
    UserRole.SUPER_ADMIN: frozenset({"*"}),
    UserRole.ADMIN: frozenset(
        {
            "venture.manage",
            "master.read",
            "master.write",
            "inventory.read",
            "inventory.write",
            "sales.read",
            "sales.write",
            "billing.read",
            "billing.write",
            "purchases.read",
            "purchases.write",
            "reports.read",
            "ai.use",
        }
    ),
    UserRole.STORE_MANAGER: frozenset(
        {
            "master.read",
            "inventory.read",
            "inventory.write",
            "sales.read",
            "sales.write",
            "billing.read",
            "billing.write",
            "purchases.read",
            "purchases.write",
            "reports.read",
            "ai.use",
        }
    ),
    UserRole.STAFF: frozenset(
        {
            "master.read",
            "inventory.read",
            "inventory.write",
            "sales.read",
            "sales.write",
            "billing.read",
            "billing.write",
            "purchases.read",
        }
    ),
    UserRole.ORDER_TAKER: frozenset({"cafe.orders.read", "cafe.orders.write", "master.read"}),
    UserRole.KITCHEN: frozenset({"cafe.kitchen.read", "cafe.kitchen.write"}),
    UserRole.ANALYST: frozenset({"master.read", "reports.read", "ai.use"}),
}


def scope_context_for_user(user: User) -> ScopeContext:
    all_companies = user.role == UserRole.SUPER_ADMIN
    if all_companies:
        branch_ids: tuple[int, ...] = ()
    elif user.role in {UserRole.ADMIN, UserRole.ANALYST}:
        branch_ids = ()
    elif user.branch_id is not None:
        branch_ids = (user.branch_id,)
    else:
        branch_ids = ()

    return ScopeContext(
        user_id=user.id,
        role=user.role,
        business_group_id=user.business_group_id,
        company_id=user.company_id,
        all_companies=all_companies,
        branch_ids=branch_ids,
        permissions=ROLE_PERMISSIONS[user.role],
    )


def has_permission(scope: ScopeContext, permission: str) -> bool:
    return "*" in scope.permissions or permission in scope.permissions
