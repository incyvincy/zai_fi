"""
Stubbed Neo4j connection module.

The project requested temporarily disabling all database connections and writes.
This module intentionally provides no-op implementations so importing code
will not attempt to connect to Neo4j.
"""

class Neo4jConnection:
    @classmethod
    def get_driver(cls):
        return None

    @classmethod
    def close(cls):
        return None

    @classmethod
    def execute_query(cls, query, parameters=None):
        return []

    @classmethod
    def execute_write(cls, query, parameters=None):
        return None

    @classmethod
    def execute_read(cls, query, parameters=None):
        return []
