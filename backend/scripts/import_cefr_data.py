import asyncio
import csv
import json
import sys
import os
from pathlib import Path

# Add the parent directory to the path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
# Import all models to ensure proper initialization
from app.models import *
from app.models.reading import ReadingText, ReadingTextType, DifficultyLevel
from app.models.content import Vocabulary
import re

async def count_words(text: str) -> int:
    """Count words in a text"""
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)

async def estimate_reading_time(word_count: int, wpm: int = 200) -> int:
    """Estimate reading time in minutes based on word count"""
    return max(1, round(word_count / wpm))

async def extract_keywords(text: str, max_keywords: int = 10) -> list:
    """Extract potential keywords from text (simple implementation)"""
    # Remove common stop words
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
        'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
        'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 
        'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her',
        'its', 'our', 'their'
    }
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Filter out stop words and count frequency
    word_freq = {}
    for word in words:
        if word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get most frequent words
    keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in keywords[:max_keywords]]

async def determine_text_type(text: str) -> ReadingTextType:
    """Determine text type based on content analysis"""
    text_lower = text.lower()
    
    # Simple heuristics for text type detection
    if any(phrase in text_lower for phrase in ['dear', 'sincerely', 'yours truly', 'best regards']):
        return ReadingTextType.LETTER
    elif any(phrase in text_lower for phrase in ['once upon a time', 'story', 'character']):
        return ReadingTextType.STORY
    elif any(phrase in text_lower for phrase in ['news', 'reported', 'according to']):
        return ReadingTextType.NEWS
    elif any(phrase in text_lower for phrase in ['in conclusion', 'thesis', 'argument']):
        return ReadingTextType.ESSAY
    elif any(phrase in text_lower for phrase in ['first', 'second', 'step', 'instruction']):
        return ReadingTextType.INSTRUCTION
    elif '"' in text and text.count('"') >= 4:  # Likely has dialogue
        return ReadingTextType.DIALOGUE
    else:
        return ReadingTextType.ARTICLE

async def import_cefr_texts(csv_file_path: str):
    """Import CEFR leveled texts from CSV file"""
    print(f"Starting import from {csv_file_path}")
    
    async with AsyncSessionLocal() as db:
        try:
            imported_count = 0
            
            with open(csv_file_path, 'r', encoding='utf-8') as file:
                # Try to detect if first row is header
                first_line = file.readline()
                file.seek(0)
                
                # Check if first line looks like a header
                if first_line.strip().lower().startswith(('text,label', 'content,level', 'text,cefr')):
                    reader = csv.DictReader(file)
                    text_col = 'text' if 'text' in reader.fieldnames else 'content'
                    label_col = 'label' if 'label' in reader.fieldnames else 'level'
                else:
                    # No header, assume first column is text, second is label
                    reader = csv.reader(file)
                    text_col = 0
                    label_col = 1
                
                for row_num, row in enumerate(reader, 1):
                    try:
                        if isinstance(row, dict):
                            text = row[text_col].strip()
                            cefr_level = row[label_col].strip().upper()
                        else:
                            text = row[0].strip() if len(row) > 0 else ""
                            cefr_level = row[1].strip().upper() if len(row) > 1 else "A1"
                        
                        if not text or len(text) < 50:  # Skip very short texts
                            continue
                            
                        # Validate CEFR level
                        if cefr_level not in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
                            print(f"Invalid CEFR level '{cefr_level}' at row {row_num}, defaulting to A1")
                            cefr_level = 'A1'
                        
                        # Process text
                        word_count = await count_words(text)
                        estimated_time = await estimate_reading_time(word_count)
                        keywords = await extract_keywords(text)
                        text_type = await determine_text_type(text)
                        
                        # Generate title (first 50 characters or first sentence)
                        sentences = text.split('.')
                        title = sentences[0][:50] + "..." if len(sentences[0]) > 50 else sentences[0]
                        if not title.strip():
                            title = f"Reading Text {imported_count + 1}"
                        
                        # Create reading text entry
                        reading_text = ReadingText(
                            title=title.strip(),
                            content=text,
                            text_type=text_type,
                            difficulty_level=DifficultyLevel(cefr_level),
                            word_count=word_count,
                            estimated_reading_time=estimated_time,
                            keywords=keywords,
                            source="CEFR Dataset",
                            is_active=True
                        )
                        
                        db.add(reading_text)
                        imported_count += 1
                        
                        # Commit in batches of 100
                        if imported_count % 100 == 0:
                            await db.commit()
                            print(f"Imported {imported_count} texts...")
                    
                    except Exception as e:
                        print(f"Error processing row {row_num}: {e}")
                        continue
            
            # Final commit
            await db.commit()
            print(f"Successfully imported {imported_count} reading texts!")
            
        except Exception as e:
            print(f"Error during import: {e}")
            await db.rollback()
        finally:
            await db.close()

async def import_vocabulary_from_json(json_file_path: str):
    """Import vocabulary from JSON file"""
    print(f"Starting vocabulary import from {json_file_path}")
    
    async with AsyncSessionLocal() as db:
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                vocab_data = json.load(file)
            
            imported_count = 0
            
            for item in vocab_data:
                try:
                    # Extract vocabulary information
                    word = item.get('word', '').strip()
                    definition = item.get('definition', item.get('meaning', '')).strip()
                    level = item.get('level', item.get('cefr', 'A1')).upper()
                    
                    if not word or not definition:
                        continue
                    
                    # Validate CEFR level
                    if level not in ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']:
                        level = 'A1'
                    
                    # Create vocabulary entry
                    vocabulary = Vocabulary(
                        word=word,
                        definition=definition,
                        difficulty_level=DifficultyLevel(level),
                        part_of_speech=item.get('pos', item.get('part_of_speech', '')),
                        phonetic=item.get('phonetic', item.get('pronunciation', '')),
                        example_sentence=item.get('example', ''),
                        is_active=True
                    )
                    
                    db.add(vocabulary)
                    imported_count += 1
                    
                    # Commit in batches
                    if imported_count % 500 == 0:
                        await db.commit()
                        print(f"Imported {imported_count} vocabulary words...")
                
                except Exception as e:
                    print(f"Error processing vocabulary item: {e}")
                    continue
            
            await db.commit()
            print(f"Successfully imported {imported_count} vocabulary words!")
            
        except Exception as e:
            print(f"Error during vocabulary import: {e}")
            await db.rollback()
        finally:
            await db.close()

async def main():
    """Main function to run imports"""
    base_path = Path(__file__).parent.parent.parent / "resources"
    
    # Import reading texts
    cefr_texts_path = base_path / "reading" / "cefr_leveled_texts.csv"
    if cefr_texts_path.exists():
        await import_cefr_texts(str(cefr_texts_path))
    else:
        print(f"CEFR texts file not found: {cefr_texts_path}")
    
    # Import vocabulary if available
    vocab_path = base_path / "vocabulary" / "word_frequency.json"
    if vocab_path.exists():
        print(f"Found vocabulary file: {vocab_path}")
        # await import_vocabulary_from_json(str(vocab_path))
    else:
        print(f"Vocabulary file not found: {vocab_path}")

if __name__ == "__main__":
    asyncio.run(main()) 