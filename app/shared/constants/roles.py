from .perms import DEFAULT_ROLE_TO_COLLEGE, UserRole

# Explicit list of role identifiers used across the project
USER_ROLES = [role for role, _ in UserRole.choices]

__all__ = ["DEFAULT_ROLE_TO_COLLEGE", "USER_ROLES"]
