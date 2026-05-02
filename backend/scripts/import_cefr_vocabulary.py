#!/usr/bin/env python3
"""
CEFR Vocabulary Import Script

This script imports vocabulary words from the ENGLISH_CERF_WORDS.csv file
into the database with enhanced features for language learning.
"""

import asyncio
import csv
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional, Set
import re

# Add the parent directory to the path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal, engine
from app.models.content import Vocabulary, DifficultyLevel
from app.schemas.content import VocabularyCreate
from app.crud.content import vocabulary_crud

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CEFRVocabularyImporter:
    """Import CEFR vocabulary from CSV with enhanced processing"""
    
    def __init__(self, csv_file_path: str):
        self.csv_file_path = Path(csv_file_path)
        self.stats = {
            "total_processed": 0,
            "successful_imports": 0,
            "skipped_duplicates": 0,
            "errors": 0,
            "by_level": {}
        }
        
        # Topic categorization based on common word patterns
        self.topic_categories = {
            # Family and relationships
            "family": ["mother", "father", "sister", "brother", "parent", "child", "family", "relative", "husband", "wife", "son", "daughter", "grandmother", "grandfather"],
            
            # Work and education
            "work": ["work", "job", "office", "business", "company", "employee", "manager", "teacher", "student", "school", "university", "education", "study"],
            
            # Food and drink
            "food": ["food", "eat", "drink", "restaurant", "kitchen", "cook", "meal", "breakfast", "lunch", "dinner", "bread", "water", "coffee", "tea"],
            
            # Travel and transport
            "travel": ["travel", "trip", "journey", "car", "bus", "train", "plane", "airport", "hotel", "ticket", "passport", "luggage", "vacation", "holiday"],
            
            # Health and body
            "health": ["health", "doctor", "hospital", "medicine", "sick", "pain", "body", "head", "hand", "foot", "eye", "ear", "mouth", "nose"],
            
            # Home and living
            "home": ["home", "house", "room", "bedroom", "kitchen", "bathroom", "furniture", "table", "chair", "bed", "door", "window", "garden"],
            
            # Shopping and money
            "shopping": ["shop", "store", "buy", "sell", "money", "price", "expensive", "cheap", "pay", "bank", "card", "cash"],
            
            # Time and weather
            "time": ["time", "day", "week", "month", "year", "morning", "afternoon", "evening", "night", "today", "tomorrow", "yesterday"],
            "weather": ["weather", "sun", "rain", "snow", "wind", "hot", "cold", "warm", "cool", "cloudy", "sunny"],
            
            # Colors and appearance
            "colors": ["color", "red", "blue", "green", "yellow", "black", "white", "brown", "pink", "orange", "purple", "grey"],
            
            # Numbers and quantities
            "numbers": ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred", "thousand", "million"],
            
            # Emotions and feelings
            "emotions": ["happy", "sad", "angry", "excited", "worried", "tired", "surprised", "afraid", "love", "hate", "like", "enjoy", "feel"],
            
            # Nature and environment
            "nature": ["nature", "tree", "flower", "animal", "bird", "fish", "sea", "mountain", "river", "forest", "park", "beach"],
            
            # Technology and communication
            "technology": ["computer", "phone", "internet", "email", "website", "technology", "digital", "online", "message", "call", "text"],
            
            # Sports and hobbies
            "sports": ["sport", "football", "tennis", "swimming", "running", "game", "play", "team", "win", "lose", "hobby", "music", "book", "read"]
        }
        
        # Common part of speech patterns
        self.pos_patterns = {
            # Verb patterns
            "verb": [r".*ing$", r".*ed$", r".*s$", r"^(go|come|make|take|get|give|see|know|think|say|tell|ask|work|play|run|walk|eat|drink|sleep|live|die|love|like|want|need|help|try|use|find|look|feel|seem|become|happen|start|stop|finish|continue|remember|forget|learn|teach|understand|speak|listen|read|write|buy|sell|pay|cost|spend|save|win|lose|open|close|begin|end).*"],
            
            # Noun patterns
            "noun": [r".*tion$", r".*sion$", r".*ness$", r".*ment$", r".*ity$", r".*er$", r".*or$", r".*ist$", r".*ism$", r".*age$", r".*hood$", r".*ship$", r".*dom$"],
            
            # Adjective patterns
            "adjective": [r".*able$", r".*ible$", r".*ful$", r".*less$", r".*ous$", r".*ive$", r".*al$", r".*ic$", r".*ly$", r".*y$", r"^(good|bad|big|small|long|short|high|low|old|new|young|hot|cold|warm|cool|fast|slow|easy|hard|difficult|simple|important|interesting|boring|beautiful|ugly|happy|sad|angry|tired|hungry|thirsty|rich|poor|free|busy|quiet|loud|clean|dirty|safe|dangerous|healthy|sick|strong|weak|smart|stupid|funny|serious|polite|rude|kind|mean|friendly|unfriendly|helpful|unhelpful|careful|careless|patient|impatient|honest|dishonest|brave|cowardly|confident|shy|popular|unpopular|famous|unknown|successful|unsuccessful|lucky|unlucky|comfortable|uncomfortable|convenient|inconvenient|possible|impossible|necessary|unnecessary|normal|abnormal|regular|irregular|similar|different|same|opposite|correct|incorrect|right|wrong|true|false|real|fake|natural|artificial|public|private|personal|professional|formal|informal|official|unofficial|legal|illegal|local|national|international|global|modern|traditional|ancient|recent|future|past|present|current|former|next|last|first|final|main|major|minor|primary|secondary|basic|advanced|simple|complex|general|specific|particular|special|common|rare|usual|unusual|typical|atypical|standard|non-standard|perfect|imperfect|complete|incomplete|full|empty|whole|partial|total|exact|approximate|accurate|inaccurate|precise|imprecise|clear|unclear|obvious|hidden|visible|invisible|available|unavailable|ready|unready|finished|unfinished|open|closed|active|inactive|alive|dead|awake|asleep|single|married|divorced|engaged|pregnant|born|educated|uneducated|experienced|inexperienced|qualified|unqualified|skilled|unskilled|trained|untrained|employed|unemployed|retired|working|studying|traveling|living|dead|dying).*"],
            
            # Adverb patterns
            "adverb": [r".*ly$", r"^(very|quite|really|actually|probably|maybe|perhaps|certainly|definitely|absolutely|completely|totally|exactly|almost|nearly|hardly|barely|just|only|even|still|already|yet|soon|late|early|now|then|here|there|everywhere|nowhere|somewhere|anywhere|always|never|sometimes|often|usually|rarely|seldom|frequently|occasionally|daily|weekly|monthly|yearly|today|tomorrow|yesterday|tonight|morning|afternoon|evening|night|quickly|slowly|carefully|carelessly|quietly|loudly|clearly|obviously|suddenly|gradually|immediately|eventually|finally|firstly|secondly|thirdly|lastly|again|also|too|either|neither|both|all|none|some|any|many|much|few|little|more|most|less|least).*"]
        }

    def categorize_word(self, word: str, definition: str = "") -> List[str]:
        """Categorize word into topics based on word content and definition"""
        categories = []
        word_lower = word.lower()
        definition_lower = definition.lower()
        
        for topic, keywords in self.topic_categories.items():
            for keyword in keywords:
                if (keyword in word_lower or 
                    keyword in definition_lower or 
                    word_lower.startswith(keyword) or 
                    word_lower.endswith(keyword)):
                    categories.append(topic)
                    break
        
        return categories if categories else ["general"]

    def detect_part_of_speech(self, word: str) -> Optional[str]:
        """Detect part of speech based on word patterns"""
        word_lower = word.lower()
        
        for pos, patterns in self.pos_patterns.items():
            for pattern in patterns:
                if re.match(pattern, word_lower):
                    return pos
        
        return None

    def generate_definition_placeholder(self, word: str, level: str) -> str:
        """Generate a basic definition placeholder for words without definitions"""
        pos = self.detect_part_of_speech(word)
        if pos:
            return f"A {level}-level {pos}: {word}"
        return f"A {level}-level English word: {word}"

    def estimate_frequency_rank(self, word: str, level: str) -> int:
        """Estimate frequency rank based on CEFR level and word characteristics"""
        base_ranks = {
            "A1": 1000,
            "A2": 2000, 
            "B1": 4000,
            "B2": 6000,
            "C1": 8000,
            "C2": 10000
        }
        
        base_rank = base_ranks.get(level, 5000)
        
        # Adjust based on word length (shorter words are often more frequent)
        length_adjustment = max(0, len(word) - 5) * 100
        
        # Adjust based on word complexity
        complexity_adjustment = 0
        if any(char in word for char in ['-', '/', '.']):
            complexity_adjustment += 500
        
        return base_rank + length_adjustment + complexity_adjustment

    def is_core_vocabulary(self, word: str, level: str) -> bool:
        """Determine if a word is core vocabulary for its level"""
        # A1 and A2 words are generally core
        if level in ["A1", "A2"]:
            return True
        
        # Common function words and high-frequency content words
        core_words = {
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", 
            "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", 
            "by", "from", "they", "she", "or", "an", "will", "my", "one", "all", "would", 
            "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", 
            "which", "go", "me", "when", "make", "can", "like", "time", "no", "just", 
            "him", "know", "take", "people", "into", "year", "your", "good", "some", 
            "could", "them", "see", "other", "than", "then", "now", "look", "only", 
            "come", "its", "over", "think", "also", "back", "after", "use", "two", 
            "how", "our", "work", "first", "well", "way", "even", "new", "want", 
            "because", "any", "these", "give", "day", "most", "us"
        }
        
        return word.lower() in core_words

    async def process_csv_file(self) -> List[VocabularyCreate]:
        """Process the CSV file and return vocabulary items"""
        vocabulary_items = []
        
        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_file_path}")
        
        logger.info(f"Processing CSV file: {self.csv_file_path}")
        
        with open(self.csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                try:
                    word = row['headword'].strip()
                    cefr_level = row['CEFR'].strip()
                    
                    if not word or not cefr_level:
                        continue
                    
                    # Skip invalid CEFR levels
                    if cefr_level not in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
                        continue
                    
                    # Handle compound words and phrases
                    clean_word = word.split('/')[0].strip()  # Take first variant
                    
                    # Generate enhanced vocabulary data
                    categories = self.categorize_word(clean_word)
                    pos = self.detect_part_of_speech(clean_word)
                    frequency_rank = self.estimate_frequency_rank(clean_word, cefr_level)
                    is_core = self.is_core_vocabulary(clean_word, cefr_level)
                    
                    vocabulary_item = VocabularyCreate(
                        word=clean_word,
                        definition=self.generate_definition_placeholder(clean_word, cefr_level),
                        difficulty_level=DifficultyLevel(cefr_level),
                        part_of_speech=pos,
                        frequency_rank=frequency_rank,
                        cefr_source="official_list",
                        is_core_vocabulary=is_core,
                        topic_categories=categories,
                        is_active=True
                    )
                    
                    vocabulary_items.append(vocabulary_item)
                    self.stats["total_processed"] += 1
                    
                    # Update level statistics
                    if cefr_level not in self.stats["by_level"]:
                        self.stats["by_level"][cefr_level] = 0
                    self.stats["by_level"][cefr_level] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    self.stats["errors"] += 1
        
        logger.info(f"Processed {len(vocabulary_items)} vocabulary items")
        logger.info(f"Distribution by level: {self.stats['by_level']}")
        
        return vocabulary_items

    async def import_to_database(self, vocabulary_items: List[VocabularyCreate]) -> Dict:
        """Import vocabulary items to database"""
        logger.info("Starting database import...")
        
        async with AsyncSessionLocal() as db:
            result = await vocabulary_crud.bulk_create(
                db,
                vocabulary_items=vocabulary_items,
                overwrite_existing=False
            )
            
            self.stats.update(result)
            
            logger.info(f"Import completed:")
            logger.info(f"  Total processed: {result['total_processed']}")
            logger.info(f"  Successful imports: {result['successful_imports']}")
            logger.info(f"  Skipped duplicates: {result['skipped_duplicates']}")
            logger.info(f"  Errors: {len(result['errors'])}")
            
            if result['errors']:
                logger.warning("Errors encountered:")
                for error in result['errors'][:10]:  # Show first 10 errors
                    logger.warning(f"  {error}")
                if len(result['errors']) > 10:
                    logger.warning(f"  ... and {len(result['errors']) - 10} more errors")
            
            return result

    async def run_import(self) -> Dict:
        """Run the complete import process"""
        try:
            # Process CSV file
            vocabulary_items = await self.process_csv_file()
            
            if not vocabulary_items:
                logger.warning("No vocabulary items to import")
                return {"error": "No vocabulary items found"}
            
            # Import to database
            result = await self.import_to_database(vocabulary_items)
            
            return result
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return {"error": str(e)}

async def main():
    """Main function to run the import"""
    # Path to the CEFR vocabulary CSV file
    csv_file_path = Path(__file__).parent.parent.parent / "resources" / "vocabulary" / "ENGLISH_CERF_WORDS.csv"
    
    if not csv_file_path.exists():
        logger.error(f"CSV file not found: {csv_file_path}")
        logger.error("Please ensure the ENGLISH_CERF_WORDS.csv file is in the resources/vocabulary/ directory")
        return
    
    logger.info("Starting CEFR Vocabulary Import")
    logger.info("=" * 50)
    
    importer = CEFRVocabularyImporter(str(csv_file_path))
    result = await importer.run_import()
    
    if "error" in result:
        logger.error(f"Import failed: {result['error']}")
        return
    
    logger.info("=" * 50)
    logger.info("Import Summary:")
    logger.info(f"Total words processed: {result['total_processed']}")
    logger.info(f"Successfully imported: {result['successful_imports']}")
    logger.info(f"Skipped (duplicates): {result['skipped_duplicates']}")
    logger.info(f"Errors: {len(result.get('errors', []))}")
    
    # Show distribution by level
    logger.info("\nDistribution by CEFR level:")
    for level, count in importer.stats["by_level"].items():
        logger.info(f"  {level}: {count} words")
    
    logger.info("\nCEFR Vocabulary Import completed successfully!")

if __name__ == "__main__":
    asyncio.run(main()) 