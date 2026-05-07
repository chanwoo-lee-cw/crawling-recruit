from sqlalchemy import select
from sqlalchemy.orm import Session
from db.models.skill_keyword import SkillKeyword


class SkillKeywordRepository:
    def __init__(self, session: Session):
        self.session = session

    def exists(self, keyword: str) -> bool:
        return self.session.scalars(
            select(SkillKeyword).where(SkillKeyword.keyword.ilike(keyword))
        ).first() is not None

    def add(self, keyword: str) -> bool:
        if self.exists(keyword):
            return False
        self.session.add(SkillKeyword(keyword=keyword))
        return True

    def find_all(self) -> list[str]:
        return list(self.session.scalars(
            select(SkillKeyword.keyword).order_by(SkillKeyword.keyword)
        ).all())

    def delete(self, keyword: str) -> SkillKeyword | None:
        obj = self.session.scalars(
            select(SkillKeyword).where(SkillKeyword.keyword.ilike(keyword))
        ).first()
        if obj:
            self.session.delete(obj)
        return obj
