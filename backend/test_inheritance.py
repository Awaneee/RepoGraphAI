from pprint import pprint

from app.parsers.code_parser import (
    CodeParser
)

parser = CodeParser()

repository = parser.parse_repository(
    "app"
)

for parsed_file in repository.files:

    for cls in parsed_file.classes:

        pprint(
            {
                "class": cls.name,
                "inherits_from":
                cls.inherits_from
            }
        )