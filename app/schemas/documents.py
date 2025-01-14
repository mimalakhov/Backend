from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4

from beanie import BackLink, Delete, Document, Indexed, Link, before_event
from beanie.odm.operators.find.logical import And, Or
from pydantic import Field

from app.core.exceptions import ValidationError

from .models import CommentCreation, IssueBase, SprintCreation, UserRegister, WorkplaceCreation
from .types import Role, states


class User(Document, UserRegister):
    id: UUID = Field(default_factory=uuid4)
    email: Indexed(str, unique=True)
    password: str = Field(exclude=True)

    @property
    def created(self) -> datetime:
        """Datetime user was created from ID"""
        return self.id.generation_time

    @classmethod
    async def by_email(cls, email: str) -> "User":
        """Get a user by email"""
        return await cls.find_one(cls.email == email)

    def __eq__(self, other):
        if not isinstance(other, (User, UUID)):
            return False
        id = other if isinstance(other, UUID) else other.id
        return self.id == id


class UserAssignedWorkplace(Document):
    id: UUID = Field(default_factory=uuid4)
    user: Link["User"]
    workplace: BackLink["Workplace"] = Field(original_field="users", exclude=True)
    role: Role

    @before_event(Delete)
    async def delete_refs(self):
        self.user = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, (UserAssignedWorkplace, UUID)):
            return False
        id = other if isinstance(other, UUID) else other.id
        return self.id == id


class Workplace(Document, WorkplaceCreation):
    id: UUID = Field(default_factory=uuid4)
    states: List[str] = Field(default_factory=states)
    users: List[Link["UserAssignedWorkplace"]] = Field(default_factory=list, exclude=True)
    sprints: List[Link["Sprint"]] = Field(default_factory=list)
    issues: List[Link["Issue"]] = Field(default_factory=list)


class Sprint(Document, SprintCreation):
    id: UUID = Field(default_factory=uuid4)
    workplace: BackLink["Workplace"] = Field(original_field="sprints", exclude=True)
    issues: List[Link["Issue"]] = Field(default_factory=list)

    @before_event(Delete)
    async def delete_ref_workplace(self):
        self.workplace.sprints.remove(self.id)
        await self.workplace.save()

    async def validate_creation(
        sprint_creation: SprintCreation, workplace_id: UUID, sprint_id: UUID = None, check_self=False
    ):
        find_sprint = await Sprint.find_one(
            Sprint.workplace.id == workplace_id,
            Or(
                And(Sprint.start_date >= sprint_creation.start_date, Sprint.start_date < sprint_creation.end_date),
                And(Sprint.end_date > sprint_creation.start_date, Sprint.end_date <= sprint_creation.end_date),
                And(Sprint.start_date <= sprint_creation.start_date, Sprint.end_date >= sprint_creation.end_date),
            ),
            Sprint.id != sprint_id,
            fetch_links=True,
        )
        if find_sprint is not None:
            raise ValidationError("Спринты не должны пересекаться по дате.")

    def __eq__(self, other):
        if not isinstance(other, (Sprint, UUID)):
            return False
        id = other if isinstance(other, UUID) else other.id
        return self.id == id


class Issue(Document, IssueBase):
    id: UUID = Field(default_factory=uuid4)
    creation_date: datetime = Field(default_factory=datetime.now)
    workplace: BackLink["Workplace"] = Field(original_field="issues", exclude=True)
    author: Optional[Link["UserAssignedWorkplace"]]
    sprint: Optional[BackLink["Sprint"]] = Field(default=None, original_field="issues", exclude=True)
    implementers: List[Link["UserAssignedWorkplace"]] = Field(default_factory=list)
    comments: List[Link["Comment"]] = Field(default_factory=list)

    @before_event(Delete)
    async def delete_refs(self):
        self.workplace.issues.remove(self.id)
        await self.workplace.save()
        if self.sprint is not None:
            self.sprint.issues.remove(self.id)
            self.sprint.save()
        self.author = None
        self.implementers = []

    def __eq__(self, other):
        if not isinstance(other, (Issue, UUID)):
            return False
        id = other if isinstance(other, UUID) else other.id
        return self.id == id


class Comment(Document, CommentCreation):
    id: UUID = Field(default_factory=uuid4)
    creation_date: datetime = Field(default_factory=datetime.now)
    author: Optional[Link["UserAssignedWorkplace"]]
    issue: BackLink["Issue"] = Field(default=None, original_field="comments", exclude=True)

    @before_event(Delete)
    async def delete_refs(self):
        self.issue.comments.remove(self.id)
        await self.issue.save()
        self.author = None

    def __eq__(self, other):
        if not isinstance(other, (Comment, UUID)):
            return False
        id = other if isinstance(other, UUID) else other.id
        return self.id == id
