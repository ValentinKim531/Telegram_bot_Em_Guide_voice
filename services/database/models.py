from abc import ABC, abstractmethod
from enum import Enum
from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Integer,
    ForeignKey,
    Time,
    Date,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()


class User(Base):
    """
    Model for users in the database.
    """

    __tablename__ = "users"

    userid = Column(BigInteger, primary_key=True)
    username = Column(String)
    firstname = Column(String)
    lastname = Column(String)
    fio = Column(String)
    birthdate = Column(Date)
    menstrual_cycle = Column(String)
    country = Column(String)
    city = Column(String)
    medication = Column(String)
    const_medication = Column(String)
    const_medication_name = Column(String)
    reminder_time = Column(Time)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    language = Column(String)
    role = Column(String)

    def __repr__(self):
        return (
            "<userid={}, "
            "username='{}', "
            "firstname='{}', "
            "lastname='{}', "
            "fio='{}', "
            "birthdate='{}', "
            "menstrual_cycle='{}', "
            "country='{}', "
            "city='{}', "
            "medication='{}', "
            "const_medication='{}', "
            "const_medication_name='{}', "
            "reminder_time='{}', "
            "created_at='{}', "
            "updated_at='{}', "
            "language='{}', "
            "role='{}')>"
        ).format(
            self.userid,
            self.username,
            self.firstname,
            self.lastname,
            self.fio,
            self.birthdate,
            self.menstrual_cycle,
            self.country,
            self.city,
            self.medication,
            self.const_medication,
            self.const_medication_name,
            self.reminder_time,
            self.created_at,
            self.updated_at,
            self.language,
            self.role,
        )


class Survey(Base):
    """
    Model for survey in the database.
    """

    __tablename__ = "survey"

    userid = Column(
        BigInteger,
        ForeignKey("users.userid", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    headache_today = Column(String)
    pain_intensity = Column(Integer)
    pain_area = Column(String)
    area_detail = Column(String)
    pain_type = Column(String)
    comments = Column(String)

    user = relationship("User", backref="survey")

    def __repr__(self):
        return (
            "<userid={}, "
            "created_at='{}', "
            "updated_at='{}', "
            "headache_today='{}', "
            "pain_intensity='{}', "
            "pain_area='{}', "
            "area_detail='{}', "
            "pain_type='{}', "
            "comments='{}')>"
        ).format(
            self.userid,
            self.created_at,
            self.updated_at,
            self.headache_today,
            self.pain_intensity,
            self.pain_area,
            self.area_detail,
            self.pain_type,
            self.comments,
        )


class Database(ABC):
    """
    Simple Database API
    """

    @abstractmethod
    async def create_tables(self) -> None:
        """
        Create tables in database.
        """
        pass

    @abstractmethod
    async def add_entity(
        self, entity_data: any, model_class: type[Base]
    ) -> None:
        """
        Add a new entity to the database.

        :param entity_data: Data of the entity to add. It can be either
        an instance of a model class or a dictionary.
        :param model_class: The class of the model corresponding to the entity.
        """
        pass

    @abstractmethod
    async def get_entity_parameter(
        self,
        entity_id: int,
        parameter: str,
        model_class: type[Base],
    ) -> any:
        """
        Get a specific parameter of an entity.

        :param entity_id: The ID of the entity.
        :param parameter: The name of the parameter.
        :param model_class: The class of the model corresponding to the entity.

        :return: The value of the specified parameter.
        """
        pass

    @abstractmethod
    async def get_entities(self, model_class: type[Base]) -> any:
        """
        Retrieve a list of entities from the database.

        :param model_class: The class of the model corresponding to the entity.

        :return: A list of entity objects or None if an error occurs.
        """
        pass

    @abstractmethod
    async def update_entity_parameter(
        self,
        entity_id: int,
        parameter: str,
        value: any,
        model_class: type[Base],
    ) -> None:
        """
        Update a specific parameter of an entity.

        :param entity_id: The ID of the entity.
        :param parameter: The name of the parameter to update.
        :param value: The new value of the parameter.
        :param model_class: The class of the model corresponding to the entity.
        :param session: The database session to use.

        :return: None
        """
        pass

    @abstractmethod
    async def delete_entity(
        self, entity_id: int, model_class: type[Base]
    ) -> None:
        """
        Delete an entity from the database.

        :param entity_id: The ID of the entity to delete.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        pass


class UserParams(Enum):
    """
    Model for user parameters.
    """

    TABLE_NAME: str = "users"

    USER_ID_COL: str = "userid"
    USER_NAME_COL: str = "username"
    USER_FIRST_NAME_COL: str = "firstname"
    USER_LAST_NAME_COL: str = "lastname"
    USER_START_DATE_COL: str = "startdate"
    USER_LANG_COL: str = "language"
    USER_ROLE_COL: str = "role"
