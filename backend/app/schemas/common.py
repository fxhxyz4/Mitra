from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


def not_null(*fields: str) -> Any:
    """PATCH: an omitted field stays as is, but an explicit null for a required column is a 422, not a DB error."""

    def check(cls: type, v: object) -> object:
        if v is None:
            raise ValueError("значення не може бути порожнім")
        return v

    return field_validator(*fields, mode="before")(classmethod(check))
