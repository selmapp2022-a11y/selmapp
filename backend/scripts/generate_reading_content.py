#!/usr/bin/env python3
"""
Script for batch generating reading content using AI and leveled vocabulary
Usage: python generate_reading_content.py --level A1 --topics travel,food --count 5
"""

import asyncio
import argparse
import sys
import os
from typing import List

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.services.ai_reading_service import ai_reading_service
from app.models.content import DifficultyLevel
from app.models.reading import ReadingTextType
from app.crud.reading import reading_text, reading_exercise, vocabulary_highlight
from app.schemas.reading import ReadingTextCreate, ReadingExerciseCreate, VocabularyHighlightCreate
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContentGenerator:
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = AsyncSessionLocal()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def generate_content_for_level(
        self, 
        level: DifficultyLevel, 
        topics: List[str], 
        text_types: List[ReadingTextType],
        count_per_combination: int = 1
    ):
        """Generate reading content for a specific level"""
        logger.info(f"Generating content for level {level.value}")
        
        total_generated = 0
        successful = 0
        failed = 0
        
        for topic in topics:
            for text_type in text_types:
                for i in range(count_per_combination):
                    try:
                        logger.info(f"Generating {text_type.value} about {topic} (#{i+1})")
                        
                        # Generate content
                        result = await ai_reading_service.generate_reading_text_with_vocabulary(
                            db=self.session,
                            level=level,
                            text_type=text_type,
                            topic=topic,
                            word_count=200 if level in [DifficultyLevel.A1, DifficultyLevel.A2] else 300,
                            vocabulary_count=8 if level in [DifficultyLevel.A1, DifficultyLevel.A2] else 12,
                            include_comprehension_questions=True
                        )
                        
                        # Save to database
                        reading_text_id = await self._save_to_database(result)
                        
                        logger.info(f"Successfully generated and saved reading text ID: {reading_text_id}")
                        successful += 1
                        total_generated += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to generate {text_type.value} about {topic}: {str(e)}")
                        failed += 1
                        total_generated += 1
        
        logger.info(f"Level {level.value} complete: {successful}/{total_generated} successful")
        return {"total": total_generated, "successful": successful, "failed": failed}
    
    async def _save_to_database(self, generated_content: dict) -> int:
        """Save generated content to database"""
        try:
            # Create reading text
            reading_text_data = ReadingTextCreate(
                title=f"{generated_content['topic'].title()} - {generated_content['text_type'].title()}",
                content=generated_content["text_content"],
                text_type=ReadingTextType(generated_content["text_type"]),
                difficulty_level=DifficultyLevel(generated_content["level"]),
                word_count=generated_content["word_count"],
                topic=generated_content["topic"],
                keywords=[vocab["word"] for vocab in generated_content["vocabulary_used"]],
                source="AI Generated",
                estimated_reading_time=max(1, generated_content["word_count"] // 200)
            )
            
            saved_text = await reading_text.create(self.session, obj_in=reading_text_data)
            
            # Create vocabulary highlights
            for vocab in generated_content["vocabulary_used"]:
                text_lower = generated_content["text_content"].lower()
                word_position = text_lower.find(vocab["word"].lower())
                
                if word_position != -1:
                    highlight_data = VocabularyHighlightCreate(
                        reading_text_id=saved_text.id,
                        word=vocab["word"],
                        definition=vocab["definition"],
                        part_of_speech=vocab.get("part_of_speech", ""),
                        difficulty_level=DifficultyLevel(generated_content["level"]),
                        start_position=word_position,
                        end_position=word_position + len(vocab["word"]),
                        example_sentence=vocab.get("example", "")
                    )
                    await vocabulary_highlight.create(self.session, obj_in=highlight_data)
            
            # Create comprehension questions
            if generated_content.get("comprehension_questions"):
                for i, question in enumerate(generated_content["comprehension_questions"]):
                    exercise_data = ReadingExerciseCreate(
                        reading_text_id=saved_text.id,
                        title=f"Question {i+1}",
                        question=question["question"],
                        exercise_type=question.get("type", "multiple_choice"),
                        options=question.get("options", []),
                        correct_answer=question["correct_answer"],
                        explanation=question.get("explanation", ""),
                        points=1,
                        order_index=i
                    )
                    await reading_exercise.create(self.session, obj_in=exercise_data)
            
            await self.session.commit()
            return saved_text.id
            
        except Exception as e:
            await self.session.rollback()
            raise Exception(f"Failed to save to database: {str(e)}")

async def main():
    parser = argparse.ArgumentParser(description="Generate reading content using AI")
    parser.add_argument("--level", type=str, choices=["A1", "A2", "B1", "B2", "C1", "C2"], 
                       help="CEFR level to generate content for")
    parser.add_argument("--all-levels", action="store_true", 
                       help="Generate content for all CEFR levels")
    parser.add_argument("--topics", type=str, default="travel,food,family,work,health",
                       help="Comma-separated list of topics")
    parser.add_argument("--text-types", type=str, default="article,story,news",
                       help="Comma-separated list of text types")
    parser.add_argument("--count", type=int, default=1,
                       help="Number of texts to generate per topic/type combination")
    parser.add_argument("--dry-run", action="store_true",
                       help="Generate content but don't save to database")
    
    args = parser.parse_args()
    
    # Parse topics and text types
    topics = [topic.strip() for topic in args.topics.split(",")]
    text_types = [ReadingTextType(t.strip()) for t in args.text_types.split(",")]
    
    # Determine levels to process
    if args.all_levels:
        levels = [DifficultyLevel.A1, DifficultyLevel.A2, DifficultyLevel.B1, 
                 DifficultyLevel.B2, DifficultyLevel.C1, DifficultyLevel.C2]
    elif args.level:
        levels = [DifficultyLevel(args.level)]
    else:
        logger.error("Please specify either --level or --all-levels")
        return
    
    logger.info(f"Starting content generation...")
    logger.info(f"Levels: {[l.value for l in levels]}")
    logger.info(f"Topics: {topics}")
    logger.info(f"Text types: {[t.value for t in text_types]}")
    logger.info(f"Count per combination: {args.count}")
    logger.info(f"Dry run: {args.dry_run}")
    
    total_stats = {"total": 0, "successful": 0, "failed": 0}
    
    async with ContentGenerator() as generator:
        for level in levels:
            try:
                if args.dry_run:
                    logger.info(f"DRY RUN: Would generate content for level {level.value}")
                    continue
                
                stats = await generator.generate_content_for_level(
                    level, topics, text_types, args.count
                )
                
                total_stats["total"] += stats["total"]
                total_stats["successful"] += stats["successful"]
                total_stats["failed"] += stats["failed"]
                
            except Exception as e:
                logger.error(f"Error processing level {level.value}: {str(e)}")
                continue
    
    logger.info("Content generation complete!")
    logger.info(f"Total: {total_stats['total']}, Successful: {total_stats['successful']}, Failed: {total_stats['failed']}")

if __name__ == "__main__":
    asyncio.run(main()) 