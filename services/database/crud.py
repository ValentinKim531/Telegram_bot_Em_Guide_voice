from typing import Optional, Union
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from .models import Base, Database
from utils.config import DB_NAME, DB_PASSWORD, DB_USER, DB_HOST, DB_PORT


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
        try:
            async with self.Session() as session:
                entity = await session.get(model_class, entity_id)
                if entity:
                    return getattr(entity, parameter, None)
        except Exception as e:
            print(
                f"Error in get_entity_parameter for {model_class.__name__}: {e}"
            )
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

        :return: None
        """
        try:
            async with self.Session() as session:
                user = await session.get(model_class, entity_id)
                if user:
                    setattr(user, parameter, value)
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
