#!/usr/bin/env python3
"""
Simple CEFR Vocabulary Import Script

This script imports vocabulary words from the ENGLISH_CERF_WORDS.csv file
directly into the database without complex model relationships.
"""

import asyncio
import csv
import logging
import sys
from pathlib import Path
from typing import List, Dict
import re
import asyncpg
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleVocabularyImporter:
    """Simple import CEFR vocabulary from CSV"""
    
    def __init__(self, csv_file_path: str, db_url: str):
        self.csv_file_path = Path(csv_file_path)
        self.db_url = db_url
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

    def categorize_word(self, word: str) -> List[str]:
        """Categorize word into topics based on word content"""
        categories = []
        word_lower = word.lower()
        
        for topic, keywords in self.topic_categories.items():
            for keyword in keywords:
                if (keyword in word_lower or 
                    word_lower.startswith(keyword) or 
                    word_lower.endswith(keyword)):
                    categories.append(topic)
                    break
        
        return categories if categories else ["general"]

    def detect_part_of_speech(self, word: str) -> str:
        """Detect part of speech based on word patterns"""
        word_lower = word.lower()
        
        # Verb patterns
        if re.match(r".*ing$|.*ed$|.*s$", word_lower) or word_lower in ["go", "come", "make", "take", "get", "give", "see", "know", "think", "say", "tell", "ask", "work", "play", "run", "walk", "eat", "drink", "sleep", "live", "die", "love", "like", "want", "need", "help", "try", "use", "find", "look", "feel", "seem", "become", "happen", "start", "stop", "finish", "continue", "remember", "forget", "learn", "teach", "understand", "speak", "listen", "read", "write", "buy", "sell", "pay", "cost", "spend", "save", "win", "lose", "open", "close", "begin", "end"]:
            return "verb"
        
        # Noun patterns
        if re.match(r".*tion$|.*sion$|.*ness$|.*ment$|.*ity$|.*er$|.*or$|.*ist$|.*ism$|.*age$|.*hood$|.*ship$|.*dom$", word_lower):
            return "noun"
        
        # Adjective patterns
        if re.match(r".*able$|.*ible$|.*ful$|.*less$|.*ous$|.*ive$|.*al$|.*ic$|.*ly$|.*y$", word_lower) or word_lower in ["good", "bad", "big", "small", "long", "short", "high", "low", "old", "new", "young", "hot", "cold", "warm", "cool", "fast", "slow", "easy", "hard", "difficult", "simple", "important", "interesting", "boring", "beautiful", "ugly", "happy", "sad", "angry", "tired", "hungry", "thirsty", "rich", "poor", "free", "busy", "quiet", "loud", "clean", "dirty", "safe", "dangerous", "healthy", "sick", "strong", "weak", "smart", "stupid", "funny", "serious", "polite", "rude", "kind", "mean", "friendly", "unfriendly", "helpful", "unhelpful", "careful", "careless", "patient", "impatient", "honest", "dishonest", "brave", "cowardly", "confident", "shy", "popular", "unpopular", "famous", "unknown", "successful", "unsuccessful", "lucky", "unlucky", "comfortable", "uncomfortable", "convenient", "inconvenient", "possible", "impossible", "necessary", "unnecessary", "normal", "abnormal", "regular", "irregular", "similar", "different", "same", "opposite", "correct", "incorrect", "right", "wrong", "true", "false", "real", "fake", "natural", "artificial", "public", "private", "personal", "professional", "formal", "informal", "official", "unofficial", "legal", "illegal", "local", "national", "international", "global", "modern", "traditional", "ancient", "recent", "future", "past", "present", "current", "former", "next", "last", "first", "final", "main", "major", "minor", "primary", "secondary", "basic", "advanced", "simple", "complex", "general", "specific", "particular", "special", "common", "rare", "usual", "unusual", "typical", "atypical", "standard", "non-standard", "perfect", "imperfect", "complete", "incomplete", "full", "empty", "whole", "partial", "total", "exact", "approximate", "accurate", "inaccurate", "precise", "imprecise", "clear", "unclear", "obvious", "hidden", "visible", "invisible", "available", "unavailable", "ready", "unready", "finished", "unfinished", "open", "closed", "active", "inactive", "alive", "dead", "awake", "asleep", "single", "married", "divorced", "engaged", "pregnant", "born", "educated", "uneducated", "experienced", "inexperienced", "qualified", "unqualified", "skilled", "unskilled", "trained", "untrained", "employed", "unemployed", "retired", "working", "studying", "traveling", "living", "dead", "dying"]:
            return "adjective"
        
        # Adverb patterns
        if re.match(r".*ly$", word_lower) or word_lower in ["very", "quite", "really", "actually", "probably", "maybe", "perhaps", "certainly", "definitely", "absolutely", "completely", "totally", "exactly", "almost", "nearly", "hardly", "barely", "just", "only", "even", "still", "already", "yet", "soon", "late", "early", "now", "then", "here", "there", "everywhere", "nowhere", "somewhere", "anywhere", "always", "never", "sometimes", "often", "usually", "rarely", "seldom", "frequently", "occasionally", "daily", "weekly", "monthly", "yearly", "today", "tomorrow", "yesterday", "tonight", "morning", "afternoon", "evening", "night", "quickly", "slowly", "carefully", "carelessly", "quietly", "loudly", "clearly", "obviously", "suddenly", "gradually", "immediately", "eventually", "finally", "firstly", "secondly", "thirdly", "lastly", "again", "also", "too", "either", "neither", "both", "all", "none", "some", "any", "many", "much", "few", "little", "more", "most", "less", "least"]:
            return "adverb"
        
        return "noun"  # default

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

    async def process_csv_and_import(self) -> Dict:
        """Process the CSV file and import directly to database"""
        if not self.csv_file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_file_path}")
        
        logger.info(f"Processing CSV file: {self.csv_file_path}")
        
        # Connect to database
        conn = await asyncpg.connect(self.db_url)
        
        try:
            # Prepare the insert statement
            insert_sql = """
                INSERT INTO vocabulary (
                    word, definition, difficulty_level, part_of_speech, frequency_rank,
                    cefr_source, is_core_vocabulary, topic_categories, is_active, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            """
            
            batch_size = 100
            batch_data = []
            
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
                        definition = f"A {cefr_level}-level {pos}: {clean_word}"
                        
                        batch_data.append((
                            clean_word,
                            definition,
                            cefr_level,
                            pos,
                            frequency_rank,
                            "official_list",
                            is_core,
                            json.dumps(categories),  # Convert list to JSON string
                            True
                        ))
                        
                        self.stats["total_processed"] += 1
                        
                        # Update level statistics
                        if cefr_level not in self.stats["by_level"]:
                            self.stats["by_level"][cefr_level] = 0
                        self.stats["by_level"][cefr_level] += 1
                        
                        # Insert in batches
                        if len(batch_data) >= batch_size:
                            try:
                                result = await conn.executemany(insert_sql, batch_data)
                                self.stats["successful_imports"] += len(batch_data)
                                logger.info(f"Imported batch of {len(batch_data)} words")
                                batch_data = []
                            except Exception as e:
                                logger.error(f"Error importing batch: {e}")
                                self.stats["errors"] += len(batch_data)
                                batch_data = []
                        
                    except Exception as e:
                        logger.error(f"Error processing row {row}: {e}")
                        self.stats["errors"] += 1
                
                # Insert remaining batch
                if batch_data:
                    try:
                        result = await conn.executemany(insert_sql, batch_data)
                        self.stats["successful_imports"] += len(batch_data)
                        logger.info(f"Imported final batch of {len(batch_data)} words")
                    except Exception as e:
                        logger.error(f"Error importing final batch: {e}")
                        self.stats["errors"] += len(batch_data)
        
        finally:
            await conn.close()
        
        logger.info(f"Import completed:")
        logger.info(f"  Total processed: {self.stats['total_processed']}")
        logger.info(f"  Successful imports: {self.stats['successful_imports']}")
        logger.info(f"  Errors: {self.stats['errors']}")
        
        return self.stats

async def main():
    """Main function to run the import"""
    # Path to the CEFR vocabulary CSV file
    csv_file_path = Path(__file__).parent.parent.parent / "resources" / "vocabulary" / "ENGLISH_CERF_WORDS.csv"
    
    if not csv_file_path.exists():
        logger.error(f"CSV file not found: {csv_file_path}")
        logger.error("Please ensure the ENGLISH_CERF_WORDS.csv file is in the resources/vocabulary/ directory")
        return
    
    # Database connection URL
    db_url = "postgresql://postgres:ali@localhost:5432/selmapp"
    
    logger.info("Starting Simple CEFR Vocabulary Import")
    logger.info("=" * 50)
    
    importer = SimpleVocabularyImporter(str(csv_file_path), db_url)
    
    try:
        result = await importer.process_csv_and_import()
        
        logger.info("=" * 50)
        logger.info("Import Summary:")
        logger.info(f"Total words processed: {result['total_processed']}")
        logger.info(f"Successfully imported: {result['successful_imports']}")
        logger.info(f"Errors: {result['errors']}")
        
        # Show distribution by level
        logger.info("\nDistribution by CEFR level:")
        for level, count in result["by_level"].items():
            logger.info(f"  {level}: {count} words")
        
        logger.info("\nSimple CEFR Vocabulary Import completed successfully!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 