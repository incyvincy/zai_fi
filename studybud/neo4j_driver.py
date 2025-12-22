"""
Neo4j Driver - Single connection instance for the entire Django application.
This prevents creating multiple connections on every request.
"""

from neo4j import GraphDatabase
from django.conf import settings

# Create ONE driver instance that will be reused
driver = GraphDatabase.driver(
    f"neo4j://{settings.NEO4J_HOST}:{settings.NEO4J_PORT}",
    auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD),
)

def run_cypher(query, params=None):
    """
    Execute a Cypher query and return the results as a list of dictionaries.
    
    Args:
        query (str): The Cypher query to execute
        params (dict): Parameters for the query (optional)
    
    Returns:
        list: Query results as a list of dictionaries
    """
    with driver.session() as session:
        return session.run(query, params or {}).data()

def close_driver():
    """
    Close the Neo4j driver connection.
    Should be called when the application shuts down.
    """
    driver.close()
