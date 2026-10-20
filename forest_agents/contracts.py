"""Planning output contracts; these deliberately cannot certify a game feature."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Claim(Record):
    kind: Literal["observed", "inferred", "proposed", "unknown"]
    statement: str
    evidence: list[str]

    @model_validator(mode="after")
    def observed_needs_reference(self):
        if self.kind == "observed" and not self.evidence:
            raise ValueError("Observed claims require evidence references")
        return self


class Milestone(Record):
    id: str
    outcome: str
    owner: str
    depends_on: list[str]
    acceptance_evidence: list[str] = Field(min_length=1)
    state: Literal["proposed"]


class OpenQuestion(Record):
    question: str
    owner: str
    unblocking_action: str


class Handover(Record):
    scope: Literal["planning_only"]
    status: Literal["COMPLETE", "PARTIAL", "BLOCKED", "NO_FINDINGS"]
    recommendation: str
    claims: list[Claim]
    milestones: list[Milestone]
    open_questions: list[OpenQuestion]
    critique: list[str]
    next_owner: str

    @model_validator(mode="after")
    def milestone_graph(self):
        items = {m.id: m for m in self.milestones}
        if len(items) != len(self.milestones):
            raise ValueError("Duplicate milestone IDs")
        visiting, done = set(), set()

        def visit(mid):
            if mid in visiting:
                raise ValueError("Cyclic milestone dependencies")
            if mid in done:
                return
            visiting.add(mid)
            for dep in items[mid].depends_on:
                if dep not in items:
                    raise ValueError("Include referenced milestones in this handover")
                visit(dep)
            visiting.remove(mid)
            done.add(mid)

        for mid in items:
            visit(mid)
        return self
