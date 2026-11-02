"""Display labels for users, e.g. "Technical Manager" or "Technician".

One helper computes the label (readmes/README-api-conventions.md §6), so API
responses and Activity "change" values never disagree about it.
"""

from apps.accounts.models import User, UserRole

FIXED_ROLE_LABELS = {
    UserRole.CLIENT: "Client POC",
    UserRole.FACILITY_MANAGER: "Facility Manager",
    UserRole.WORKER: "Technician",
}


def get_role_label(user: User) -> str:
    if user.role == UserRole.DEPARTMENT_POC:
        # Every POC account leads exactly one Department (see Department.poc_user).
        return f"{user.poc_department.name} Manager"
    return FIXED_ROLE_LABELS[user.role]


def get_name_with_role_label(user: User) -> str:
    """Return a display-ready person, e.g. "Prakash Kumar (Technician)"."""
    return f"{user.name} ({get_role_label(user)})"
