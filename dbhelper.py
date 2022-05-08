from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,scoped_session
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///test.db',echo =False)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)
Base = declarative_base()





# ========================================================================
# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker, scoped_session
# from sqlalchemy.ext.declarative import declarative_base
#
# engine = create_engine('sqlite:///test.db', echo = False)
# session_factory = sessionmaker(bind=engine)
# Session = scoped_session(session_factory)
# Base = declarative_base()