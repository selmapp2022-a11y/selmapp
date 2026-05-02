#!/usr/bin/env python3
"""
Import CEFR vocabulary data from CSV file into the database.
"""

import sys
import os
import csv
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import init_db, get_db
from app.models.content import Vocabulary, DifficultyLevel
from sqlalchemy.orm import Session
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def import_cefr_vocabulary(csv_file_path: str, db: Session):
    """Import CEFR vocabulary data from CSV file."""

    # Check if CSV file exists
    if not os.path.exists(csv_file_path):
        logger.error(f"CSV file not found: {csv_file_path}")
        return

    # Count existing vocabulary entries
    existing_count = db.query(Vocabulary).count()
    logger.info(f"Existing vocabulary entries: {existing_count}")

    # Read CSV file
    imported_count = 0
    skipped_count = 0
    duplicate_count = 0

    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)

        for row_num, row in enumerate(csv_reader, 2):  # Start from 2 because header is row 1
            try:
                headword = row.get('headword', '').strip()
                cefr_level = row.get('CEFR', '').strip()

                if not headword or not cefr_level:
                    logger.warning(f"Row {row_num}: Missing headword or CEFR level")
                    skipped_count += 1
                    continue

                # Validate CEFR level
                try:
                    difficulty_level = DifficultyLevel(cefr_level.upper())
                except ValueError:
                    logger.warning(f"Row {row_num}: Invalid CEFR level '{cefr_level}' for word '{headword}'")
                    skipped_count += 1
                    continue

                # Check if word already exists
                existing_word = db.query(Vocabulary).filter(
                    Vocabulary.word == headword,
                    Vocabulary.difficulty_level == difficulty_level
                ).first()

                if existing_word:
                    duplicate_count += 1
                    continue

                # Create new vocabulary entry
                vocabulary = Vocabulary(
                    word=headword,
                    definition=f"CEFR {cefr_level} vocabulary word",  # Basic definition
                    difficulty_level=difficulty_level,
                    cefr_source="cefr_official",
                    is_core_vocabulary=True,
                    topic_categories=["general"]  # Default category
                )

                db.add(vocabulary)
                imported_count += 1

                # Commit in batches to avoid memory issues
                if imported_count % 1000 == 0:
                    db.commit()
                    logger.info(f"Imported {imported_count} words so far...")

            except Exception as e:
                logger.error(f"Error processing row {row_num}: {e}")
                skipped_count += 1
                continue

    # Final commit
    db.commit()

    logger.info("Import Summary:")
    logger.info(f"- Imported: {imported_count} words")
    logger.info(f"- Skipped: {skipped_count} words")
    logger.info(f"- Duplicates: {duplicate_count} words")
    logger.info(f"- Total processed: {imported_count + skipped_count + duplicate_count}")

    # Verify import
    final_count = db.query(Vocabulary).count()
    logger.info(f"Final vocabulary count: {final_count}")
    logger.info(f"Net increase: {final_count - existing_count}")

async def main():
    """Main function to run the import."""
    logger.info("Starting CEFR vocabulary import...")

    # CSV file path - adjust this path as needed
    csv_file_path = "../../resources/vocabulary/ENGLISH_CERF_WORDS.csv"

    # Initialize database
    logger.info("Initializing database connection...")
    await init_db()

    # Get database session
    db_generator = get_db()
    db = await db_generator.__anext__()

    try:
        # Import vocabulary data
        import_cefr_vocabulary(csv_file_path, db)
        logger.info("CEFR vocabulary import completed successfully!")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        await db.rollback()
        raise
    finally:
        await db.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
