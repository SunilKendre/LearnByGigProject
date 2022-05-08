from dbhelper import Base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship, backref
from datetime import datetime


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(Integer, nullable=False, unique=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    tg_username = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow())
    gigs = relationship("Gig", secondary='gigusers', viewonly=True)

    @classmethod
    def get_user_by_chatid(cls, session, chat_id):
        return session.query(cls).filter(cls.chat_id == chat_id).first()

    @classmethod
    def get_user_by_id(cls, session, id):
        return session.query(cls).filter(cls.id == id).first()

    def __repr__(self):
        return f'User: Id = {self.id},  chat_id = {self.chat_id}, first_name = {self.first_name}, last_name = {self.last_name},'\
               f'tg_username = {self.tg_username}, created_at = {self.created_at} '


class Gig(Base):
    __tablename__ = 'gigs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    short_description = Column(Text, nullable=False)
    instructions = Column(Text, nullable=True)
    owner_chat_id = Column(Integer, nullable=False)
    created_at = Column(Integer, nullable=False, default=datetime.utcnow())
    updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
    steps = relationship('Step', back_populates='gig', lazy='dynamic')
    users = relationship('User', secondary='gigusers', viewonly=True)

    @classmethod
    def get_gig(cls, session, id):
        return session.query(cls).filter(cls.id == id).first()

    def update_description(self, session, description):
        self.short_description = description
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def update_instructions(self, session, instructions):
        self.instructions = instructions
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def __repr__(self):
        return f'Gig: Id - {self.id}, short_description - {self.short_description}, instructions - {self.instructions}, owner_chat_id - {self.owner_chat_id}, created_at - {self.created_at} '


class Step(Base):  # step object of Step (step.gigusers ->) && step.stepgigusers
    __tablename__ = 'steps'
    id = Column(Integer, primary_key=True, autoincrement=True)
    localstepid = Column(Integer, nullable=False)
    gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
    step_text = Column(Text, nullable=False)
    created_at = Column(Integer, nullable=False, default=datetime.utcnow())
    updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
    gig = relationship('Gig')
    gigusers = relationship('GigUser', secondary='stepgigusers', viewonly=True)

    def update_step(self, session, step_text):
        self.step_text = step_text
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def __repr__(self):
        return f"<Steps: Id - {self.id}, Gig_id - {self.gig_id}, step_text - {self.step_text}>"


class GigUser(Base):  # giguser object of GigUser. giguser.steps && giguser.stepgigusers
    __tablename__ = 'gigusers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    taken_at = Column(DateTime, nullable=False, default=datetime.utcnow())
    finished_at = Column(DateTime, nullable=True)
    gig = relationship('Gig', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
    user = relationship('User', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
    steps = relationship('Step', secondary='stepgigusers', viewonly=True)

    @classmethod
    def get_giguser_by_gigid_userid(cls, session, gigid, userid):
        return session.query(cls).filter(cls.gig_id == gigid).filter(cls.user_id == userid).first()

    @classmethod
    def get_giguser_by_id(cls, session, id):
        return session.query(cls).filter(cls.id == id).first()

    def __repr__(self):
        return f"<GigUser: Id - {self.id}, gig_id - {self.gig_id}, user_id - {self.user_id}, taken_at - {self.taken_at}>"


class StepGigUser(Base):  # stepgiguser object of StepGigUser, stepgiguser.step, stepgiguser.giguser
    __tablename__ = 'stepgigusers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(Integer, ForeignKey('steps.id'), nullable=False)
    giguser_id = Column(Integer, ForeignKey('gigusers.id'), nullable=False)
    work_comment = Column(Text, nullable=True)
    work_photo = Column(Text, nullable=True)
    work_link = Column(Text, nullable=True)
    review = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    step = relationship('Step', backref=backref('stepgigusers', cascade='all, delete-orphan', lazy='dynamic'))
    giguser = relationship('GigUser', backref=backref('stepgigusers', cascade='all, delete-orphan', lazy='dynamic'))

    @classmethod
    def get_stepgiguser_by_stepid_giguserid(cls, session, stepid, giguserid):
        return session.query(cls).filter(cls.step_id == stepid).filter(cls.giguser_id == giguserid).first()

    def update_review(self, session, review, reviewed_at=datetime.utcnow()):
        self.review = review
        self.reviewed_at = reviewed_at
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def update_comment(self, session, comment):
        self.work_comment = comment
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def update_link(self, session, links):
        self.work_link = links
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def update_photo(self, session, photos):
        self.work_photo = photos
        session.add(self)
        try:
            session.commit()
            return self
        except:
            session.rollback()
            return None

    def __repr__(self):
        return f"<StepGigUser: Id - {self.id}, step_id - {self.step_id}, giguser_id - {self.giguser_id}, work_comment - {self.work_comment}, work_link - {self.work_link}, work_photo - {self.work_photo}, review - {self.review}, submitted_at - {self.submitted_at}>"




# //////////////////////////////////////////////////////////////////////////////

# from dbhelper import Base
# from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
# from sqlalchemy.orm import relationship, backref
# from datetime import datetime
#
#
# class User(Base):
#     __tablename__ = 'users'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     chat_id = Column(Integer, nullable=False, unique=True)
#     first_name = Column(String(100), nullable=True)
#     last_name = Column(String(100), nullable=True)
#     tg_username = Column(String(100), nullable=True)
#     created_at = Column(DateTime, default=datetime.utcnow())
#     gigs = relationship("Gig", secondary='gigusers', viewonly=True)
#
#     @classmethod
#     def get_user_by_chatid(cls, session, chat_id):
#         return session.query(cls).filter(cls.chat_id == chat_id).first()
#
#     def __repr__(self):
#         return f'User: Id = {self.id},  chat_id = {self.chat_id}, first_name = {self.first_name}, last_name = {self.last_name},'\
#                f'tg_username = {self.tg_username}, created_at = {self.created_at} '
#
#
# class Gig(Base):
#     __tablename__ = 'gigs'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     short_description = Column(Text, nullable=False)
#     instructions = Column(Text, nullable=True)
#     owner_chat_id = Column(Integer, nullable=False)
#     created_at = Column(Integer, nullable=False, default=datetime.utcnow())
#     updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
#     steps = relationship('Step', back_populates='gig', lazy='dynamic')
#     users = relationship('User', secondary='gigusers', viewonly=True)
#
#     @classmethod
#     def get_gig(cls, session, id):
#         return session.query(cls).filter(cls.id == id).first()
#
#     def __repr__(self):
#         return f'Gig: Id - {self.id}, short_description - {self.short_description}, instructions - {self.instructions}, owner_chat_id - {self.owner_chat_id}, created_at - {self.created_at} '
#
#
# class Step(Base):  # step object of Step (step.gigusers ->) && step.stepgigusers
#     __tablename__ = 'steps'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     localstepid = Column(Integer, nullable=False)
#     gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
#     step_text = Column(Text, nullable=False)
#     created_at = Column(Integer, nullable=False, default=datetime.utcnow())
#     updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
#     gig = relationship('Gig')
#     gigusers = relationship('GigUser', secondary='stepgigusers', viewonly=True)
#
#     def __repr__(self):
#         return f"<Steps: Id - {self.id}, Gig_id - {self.gig_id}, step_text - {self.step_text}>"
#
#
# class GigUser(Base):  # giguser object of GigUser. giguser.steps && giguser.stepgigusers
#     __tablename__ = 'gigusers'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
#     user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
#     taken_at = Column(DateTime, nullable=False, default=datetime.utcnow())
#     finished_at = Column(DateTime, nullable=True)
#     gig = relationship('Gig', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
#     user = relationship('User', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
#     steps = relationship('Step', secondary='stepgigusers', viewonly=True)
#
#     @classmethod
#     def get_giguser_by_gigid_userid(cls, session, gigid, userid):
#         return session.query(cls).filter(cls.gig_id == gigid).filter(cls.user_id == userid).first()
#
#     def __repr__(self):
#         return f"<GigUser: Id - {self.id}, gig_id - {self.gig_id}, user_id - {self.user_id}, taken_at - {self.taken_at}>"
#
#
# class StepGigUser(Base):  # stepgiguser object of StepGigUser, stepgiguser.step, stepgiguser.giguser
#     __tablename__ = 'stepgigusers'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     step_id = Column(Integer, ForeignKey('steps.id'), nullable=False)
#     giguser_id = Column(Integer, ForeignKey('gigusers.id'), nullable=False)
#     work_comment = Column(Text, nullable=True)
#     work_photo = Column(Text, nullable=True)
#     work_link = Column(Text, nullable=True)
#     review = Column(Text, nullable=True)
#     submitted_at = Column(DateTime, nullable=True)
#     reviewed_at = Column(DateTime, nullable=True)
#     step = relationship('Step', backref=backref('stepgigusers', cascade='all, delete-orphan', lazy='dynamic'))
#     giguser = relationship('GigUser', backref=backref('stepgigusers', cascade='all, delete-orphan', lazy='dynamic'))
#
#     @classmethod
#     def get_stepgiguser_by_stepid_giguserid(cls, session, stepid, giguserid):
#         return session.query(cls).filter(cls.step_id == stepid).filter(cls.giguser_id == giguserid).first()
#
#     def __repr__(self):
#         return f"<StepGigUser: Id - {self.id}, step_id - {self.step_id}, giguser_id - {self.giguser_id}, work_comment - {self.work_comment}, work_link - {self.work_link}, work_photo - {self.work_photo}, review - {self.review}, submitted_at - {self.submitted_at}>"
#
#
#
#
# # =============================================================================================
# # # from typing import ClassVar
# # # import sqlalchemy
# # from sqlalchemy.orm import relationship, session
# # from sqlalchemy.sql.schema import ForeignKeyConstraint
# # from dbhelper import Base
# # from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
# # from sqlalchemy.orm import relationship, backref
# # from datetime import datetime
# #
# #
# # # from main.main import instructions_of_new_gig
# #
# #
# # # Classes/Tables
# # # User(id,chat_id,username,first_name,last_name,created_at)
# # # Gigs(id,Owner_chat_id,high_level_desc,steps,created_at)
# # # GigUser_Table/relationship(user_id,gigs_id,)
# #
# # class User(Base):
# #     __tablename__ = 'users'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     chat_id = Column(Integer, nullable=False, unique=True)
# #     first_name = Column(String(100), nullable=True)
# #     last_name = Column(String(100), nullable=True)
# #     tg_username = Column(String(100), nullable=True)
# #     created_at = Column(DateTime, default=datetime.utcnow())
# #     gigs = relationship('Gig', secondary='gigusers', viewonly=True)
# #
# #     @classmethod
# #     def get_user_by_chatid(cls, session, chat_id):
# #         return session.query(cls).filter(cls.chat_id == chat_id).first()
# #
# #     def __repr__(self):
# #         return f"<User:Id ={self.id},chat_id-{self.chat_id},first_name-{self.first_name},last_name-{self.last_name}," \
# #                f"tg_username-{self.tg_username},created_at-{self.created_at}>"
# #
# #
# # class Gig(Base):
# #     __tablename__ = 'gigs'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     short_description = Column(Text, nullable=False)
# #     instructions = Column(Text, nullable=True)
# #     owner_chat_id = Column(Integer, nullable=False)
# #     created_at = Column(Integer, nullable=False, default=datetime.utcnow())
# #     updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
# #     steps = relationship('Step', back_populates='gig', lazy='dynamic')
# #     users = relationship('User', secondary='gigusers', viewonly=True )
# #
# #     @classmethod
# #     def get_gig(cls, session, id):
# #         return session.query(cls).filter(cls.id == id).first()
# #
# #     def __repr__(self):
# #         return f"<Gig:Id ={self.id},short_description-{self.short_description},instructions - {self.instructions},owner_chat_id-{self.owner_chat_id},created_at-{self.created_at}>"
# #
# #
# # class Step(Base):
# #     __tablename__ = 'steps'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
# #     step_text = Column(Text, nullable=False)
# #     created_at = Column(Integer, nullable=False, default=datetime.utcnow())
# #     updated_at = Column(Integer, nullable=False, default=datetime.utcnow())
# #     gig = relationship('Gig')
# #
# #     def __repr__(self):
# #         return f"<Step:Id{self.id},Gig.id-{self.gig_id},step_text-{self.step_text}>"
# #
# #
# # class GigUser(Base):
# #     __tablename__ = 'gigusers'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     gig_id = Column(Integer, ForeignKey('gigs.id'), nullable=False)
# #     user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
# #     taken_at = Column(DateTime, nullable=False, default=datetime.utcnow())
# #     finished_at = Column(DateTime, nullable=True)
# #     gig = relationship('Gig', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
# #     user = relationship('User', backref=backref('gigusers', cascade='all, delete-orphan', lazy='dynamic'))
# #
# #     def __repr__(self):
# #         return f"<GigUser: ID - {self.id}, gig_id - {self.gig_id}, user_id - {self.user_id}, taken_at - {self.taken_at}"
# #
# #
# # class StepUser(Base):
# #     __tablename__ = 'stepusers'
# #     id = Column(Integer, primary_key=True, autoincrement=True)
# #     step_id = Column(Integer, ForeignKey('steps.id'), nullable=False)
# #     user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
# #     work_comment = Column(Text, nullable=True)
# #     work_photo = Column(Text, nullable=True)
# #     work_link = Column(Text, nullable=True)
# #     review = Column(Text, nullable=True)
# #     submitted_at = Column(DateTime, nullable=True)
# #     reviewed_at = Column(DateTime, nullable=True)
# #     step = relationship('Step', backref=backref('stepusers', cascade='all, delete-orphan', lazy='dynamic'))
# #     user = relationship('User', backref=backref('stepusers', cascade='all, delete-orphan', lazy='dynamic'))
# #
# #     def __repr__(self):
# #         return f"<StepUser: ID - {self.id}, step_id - {self.step_id}, user_id - {self.user_id}, submitted_at - {self.submitted_at}"
#
#
#
#
#
