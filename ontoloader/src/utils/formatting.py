
def ignore_if_empty(template: str, param=None):
    return template.format(param) if param else ''
