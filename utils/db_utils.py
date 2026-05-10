"""
Database utility functions
"""

from forensic import db
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

class DatabaseUtils:
    """Database helper utilities"""
    
    @staticmethod
    def execute_raw_sql(query, params=None):
        """Execute raw SQL query"""
        try:
            result = db.session.execute(text(query), params or {})
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error: {e}")
            raise
    
    @staticmethod
    def get_table_row_count(table_name):
        """Get row count for a table"""
        result = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar()
    
    @staticmethod
    def truncate_table(table_name):
        """Truncate a table (careful!)"""
        try:
            db.session.execute(text(f"TRUNCATE TABLE {table_name}"))
            db.session.commit()
            logger.info(f"Truncated table: {table_name}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"Failed to truncate {table_name}: {e}")
            raise
    
    @staticmethod
    def create_index_if_not_exists(table_name, index_name, columns):
        """Create index if it doesn't exist"""
        query = f"""
        CREATE INDEX IF NOT EXISTS {index_name}
        ON {table_name} ({', '.join(columns)})
        """
        try:
            db.session.execute(text(query))
            db.session.commit()
            logger.info(f"Created index {index_name} on {table_name}")
        except Exception as e:
            logger.warning(f"Index {index_name} may already exist: {e}")