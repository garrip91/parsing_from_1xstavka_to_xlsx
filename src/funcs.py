import re


def del_space(x: str) -> str:
    return ' '.join(x.split())


def remove_trash(data: str):
    if el := re.findall(r'\?.+', data):
        data = data.replace(el[0], '')
    
    return data