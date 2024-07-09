import logging
from typing import Optional, Union, Type, Any
from sqlalchemy import (
    select,
    update,
    and_,
    Column,
    cast,
    String,
    Integer,
    func,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from .models import Base, Database
from utils.config import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST, DB_PORT


logger = logging.getLogger(__name__)


class Postgres(Database):
    """
    Implementation of the Database interface for PostgreSQL.
    """

    def __init__(self):
        self._DB_HOST = DB_HOST
        self._DB_PORT = DB_PORT
        self._DB_NAME = DB_NAME
        self._DB_USER = DB_USER
        self._DB_PASSWORD = DB_PASSWORD

        try:
            self.engine = create_async_engine(
                f"postgresql+asyncpg://{self._DB_USER}:{self._DB_PASSWORD}"
                f"@{self._DB_HOST}:{self._DB_PORT}/{self._DB_NAME}"
            )
            self.Session = async_sessionmaker(
                bind=self.engine, expire_on_commit=False, class_=AsyncSession
            )

        except Exception as e:
            print("class <Postgres> connection error:", e)

    async def create_tables(self) -> None:
        """
        Create tables in database.
        """
        try:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        except Exception as e:
            print(f"class <Postgres> create_tables error: {e}")

    async def add_entity(
        self,
        entity_data: Union[dict, Base],
        model_class: type[Base],
    ) -> None:
        """
        Add a new entity to the database.

        :param entity_data: Data of the entity to add. It can be either
        an instance of a model class or a dictionary.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        try:
            async with self.Session() as session:
                if isinstance(entity_data, dict):
                    entity = model_class(**entity_data)
                else:
                    entity = entity_data

                session.add(entity)
                await session.commit()
        except Exception as e:
            print(f"class <Postgres> add_entity error: {e}")

    async def get_entity_parameter(
        self,
        model_class: type[Base],
        filters: Optional[dict] = None,
        parameter: Optional[str] = None,
    ) -> Optional[Union[Base, Any]]:
        """
        Get an entity or a specific parameter of an entity from the database.

        :param model_class: The class of the model corresponding to the entity.
        :param filters: A dictionary of filters to apply.
        :param parameter: The specific parameter to retrieve.

        :return: The entity or the value of the specified parameter.
        """
        try:
            async with self.Session() as session:
                if filters:
                    stmt = select(model_class).filter_by(**filters)
                    result = await session.execute(stmt)
                    entity = result.scalars().first()

                    if entity and parameter:
                        return getattr(entity, parameter, None)
                    return entity

        except Exception as e:
            logger.error(f"Error in get_entity_parameter: {e}")
        return None

    async def get_entities_parameter(
        self, model_class: Type[Base], filters: Optional[dict] = None
    ) -> Optional[list[Base]]:
        """
        Get entities from the database based on filters.

        :param model_class: The class of the model corresponding to the entities.
        :param filters: A dictionary of filters to apply.

        :return: A list of entities.
        """
        try:
            async with self.Session() as session:
                if filters:
                    stmt = select(model_class).filter_by(**filters)
                    result = await session.execute(stmt)
                    return result.scalars().all()

        except Exception as e:
            logger.error(f"Error in get_entities_parameter: {e}")
        return None

    async def get_entities(self, model_class: type[Base]) -> Optional[list]:
        """
        Retrieve a list of entities from the database.

        :param model_class: The class of the model corresponding to the entity.

        :return: A list of entity objects or None if an error occurs.
        """
        try:
            async with self.Session() as session:
                entities = await session.execute(select(model_class))
                return entities.scalars().all()
        except Exception as e:
            print(f"class <Postgres> get_entities error:", e)
            return None

    async def update_entity_parameter(
        self,
        entity_id: Union[int, tuple],
        parameter: str,
        value: any,
        model_class: type[Base],
    ) -> None:
        """
        Update a specific parameter of an entity.

        :param entity_id: The ID of the entity. It can be an int for single key or a tuple for composite key.
        :param parameter: The name of the parameter to update.
        :param value: The new value of the parameter.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        try:
            async with self.Session() as session:
                if isinstance(entity_id, tuple):
                    entity = await session.get(model_class, entity_id)
                else:
                    entity = await session.get(model_class, (entity_id,))

                if entity:
                    setattr(entity, parameter, value)
                    await session.commit()
        except Exception as e:
            print(f"class <Postgres> update_entity_parameter error: {e}")

    async def delete_entity(
        self, entity_id: int, model_class: type[Base]
    ) -> None:
        """
        Delete an entity from the database.

        :param entity_id: The ID of the entity to delete.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        try:
            async with self.Session() as session:
                entity = await session.get(model_class, entity_id)
                if entity:
                    await session.delete(entity)
                    await session.commit()
        except Exception as e:
            print(f"class <Postgres> delete_entity error: {e}")

    async def delete_entity_parameter(
        self,
        entity_id: int,
        parameter: str,
        model_class: type[Base],
    ) -> None:
        """
        Delete a specific parameter of an entity.

        :param entity_id: The ID of the entity.
        :param parameter: The name of the parameter to delete.
        :param model_class: The class of the model corresponding to the entity.

        :return: None
        """
        try:
            async with self.Session() as session:
                stmt = (
                    update(model_class)
                    .where(model_class.userid == entity_id)
                    .values({parameter: None})
                )
                await session.execute(stmt)
                await session.commit()
        except Exception as e:
            print(f"class <Postgres> delete_entity_parameter error: {e}")
