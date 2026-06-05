from pprint import pprint

from app.parsers.code_parser import (
    CodeParser
)

parser = CodeParser()

result = parser.parse_repository(
    "app"
)

pprint(
    result.model_dump()
)