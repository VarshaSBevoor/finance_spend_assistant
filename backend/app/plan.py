from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Route = Literal["data", "policy", "both", "out_of_scope"]
Operator = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "is_null", "not_null"]


# Each model has extra="forbid": a field the model invents fails validation,
# which triggers the retry.
class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # `column` is a plain string on purpose. The allowlist of real columns is
    # checked in the validate step, so a bad column is a testable rejection.
    column: str
    op: Operator
    value: str | float | list[str] | None = None


class DataQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # No defaults on these four: the JSON schema then marks them required, so the
    # model cannot skip them. Empty is allowed, leaving them out is not.
    filters: list[Filter]
    group_by: list[str]
    aggregate: Literal["sum", "count", "rows"]
    sort: Literal["asc", "desc"] | None = None
    limit: int | None = Field(default=None, ge=1, le=100)
    # Extra columns to show when listing invoices, such as po_number. Optional: leaving it out
    # shows only the core columns, which is what most questions need.
    show_columns: list[str] = []

    # Runs after the fields are checked. The error text goes back to the model on retry.
    @model_validator(mode="after")
    def rows_are_not_grouped(self):
        if self.aggregate == "rows" and self.group_by:
            raise ValueError("aggregate 'rows' lists invoices and cannot use group_by. Put conditions in filters.")
        return self

    @model_validator(mode="after")
    def show_columns_need_rows(self):
        if self.show_columns and self.aggregate != "rows":
            raise ValueError("show_columns only works with aggregate 'rows', which lists invoices.")
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    data_query: DataQuery | None  # required, but null is allowed
    policy_sections: list[str]
    reason: str

    # The model often leaves out the part a route needs. Catching it here lets the retry fix it.
    @model_validator(mode="after")
    def route_has_what_it_needs(self):
        needs_data = self.route in ("data", "both")
        needs_policy = self.route in ("policy", "both")

        if needs_data and self.data_query is None:
            raise ValueError(f"route '{self.route}' needs a data_query.")
        if needs_policy and not self.policy_sections:
            raise ValueError(f"route '{self.route}' needs at least one id in policy_sections.")
        if not needs_data and self.data_query is not None:
            raise ValueError(f"route '{self.route}' must not have a data_query.")
        if not needs_policy and self.policy_sections:
            raise ValueError(f"route '{self.route}' must not have policy_sections.")
        return self
