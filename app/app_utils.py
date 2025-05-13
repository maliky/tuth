from app.constants import UNDEFINED_CHOICES


def make_choices(main_list: list[str] = [UNDEFINED_CHOICES]) -> list[tuple[str, str]]:
    return [(elt, elt.replace("_", " ").title()) for elt in main_list]
