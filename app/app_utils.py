from app.constants import UNDEFINED_CHOICES


def make_choices(main_list=None) -> list[tuple[str, str]]:
    # Default arg is a mutable list literal – if you ever mutate it you’ll share state across calls.  I don't get it check. why not default arg
    main_list = main_list or [UNDEFINED_CHOICES]
    return [(elt, elt.replace("_", " ").title()) for elt in main_list]


def make_course_code(name, number):
    return f"{name}{number}".upper()
