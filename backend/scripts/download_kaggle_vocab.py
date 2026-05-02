#!/usr/bin/env python3
"""
Script to download CEFR labeled vocabulary dataset from Kaggle
"""
import os
import sys
import requests
import zipfile
from pathlib import Path
import json

def download_with_requests(url, output_path):
    """Download file using requests with session handling"""
    session = requests.Session()
    
    try:
        # First, try to get the direct download link
        response = session.get(url, stream=True)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"Downloaded successfully to {output_path}")
        return True
    except Exception as e:
        print(f"Error downloading: {e}")
        return False

def setup_kaggle_api():
    """Try to set up Kaggle API if credentials are available"""
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi
        
        # Check if kaggle.json exists
        kaggle_dir = Path.home() / '.kaggle'
        kaggle_json = kaggle_dir / 'kaggle.json'
        
        if not kaggle_json.exists():
            print("Kaggle API credentials not found.")
            print("Please visit https://www.kaggle.com/settings/account")
            print("and download your kaggle.json file to ~/.kaggle/")
            return None
        
        api = KaggleApi()
        api.authenticate()
        return api
    except Exception as e:
        print(f"Error setting up Kaggle API: {e}")
        return None

def download_kaggle_dataset():
    """Download the CEFR vocabulary dataset"""
    dataset_name = "nezahatkk/10-000-english-words-cerf-labelled"
    
    # Try Kaggle API first
    api = setup_kaggle_api()
    if api:
        try:
            print(f"Downloading {dataset_name} using Kaggle API...")
            download_path = Path("../resources/vocabulary/kaggle_download")
            download_path.mkdir(parents=True, exist_ok=True)
            
            api.dataset_download_files(dataset_name, path=str(download_path), unzip=True)
            print(f"Dataset downloaded to {download_path}")
            return True
        except Exception as e:
            print(f"Kaggle API download failed: {e}")
    
    # Alternative: Try direct download (this might not work for private datasets)
    print("Trying alternative download method...")
    
    # Create download directory
    download_path = Path("../resources/vocabulary/kaggle_download")
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Note: Direct download from Kaggle typically requires authentication
    # The user will need to manually download or provide API credentials
    print("\nManual download required:")
    print("1. Go to: https://www.kaggle.com/datasets/nezahatkk/10-000-english-words-cerf-labelled")
    print("2. Click 'Download' button")
    print("3. Extract the files to: resources/vocabulary/kaggle_download/")
    print("4. Run this script again to process the files")
    
    return False

def process_downloaded_files():
    """Process the downloaded vocabulary files"""
    download_path = Path("../resources/vocabulary/kaggle_download")
    
    # Look for CSV files in the download directory
    csv_files = list(download_path.glob("*.csv"))
    
    if not csv_files:
        print(f"No CSV files found in {download_path}")
        return False
    
    print(f"Found {len(csv_files)} CSV files:")
    for csv_file in csv_files:
        print(f"  - {csv_file.name}")
    
    # Process the main vocabulary file
    vocab_file = None
    for csv_file in csv_files:
        if "english" in csv_file.name.lower() or "vocab" in csv_file.name.lower():
            vocab_file = csv_file
            break
    
    if not vocab_file:
        vocab_file = csv_files[0]  # Use the first CSV file
    
    print(f"Processing vocabulary file: {vocab_file.name}")
    
    try:
        import pandas as pd
        
        # Read the CSV file
        df = pd.read_csv(vocab_file)
        print(f"Loaded {len(df)} vocabulary entries")
        print(f"Columns: {list(df.columns)}")
        
        # Show sample data
        print("\nSample data:")
        print(df.head())
        
        # Convert to JSON format for easier processing
        output_file = Path("../resources/vocabulary/cefr_vocabulary.json")
        
        vocab_data = []
        for _, row in df.iterrows():
            # Adapt column names based on the actual dataset structure
            word_col = None
            level_col = None
            
            # Try to identify word and level columns
            for col in df.columns:
                if 'word' in col.lower() or 'term' in col.lower():
                    word_col = col
                if 'level' in col.lower() or 'cefr' in col.lower() or 'label' in col.lower():
                    level_col = col
            
            if word_col and level_col:
                vocab_entry = {
                    'word': str(row[word_col]).strip(),
                    'level': str(row[level_col]).strip().upper(),
                    'definition': '',  # Will be filled later if available
                    'part_of_speech': '',
                    'example': ''
                }
                vocab_data.append(vocab_entry)
        
        # Save as JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(vocab_data, f, indent=2, ensure_ascii=False)
        
        print(f"Processed vocabulary saved to: {output_file}")
        print(f"Total entries: {len(vocab_data)}")
        
        # Show level distribution
        level_counts = {}
        for entry in vocab_data:
            level = entry['level']
            level_counts[level] = level_counts.get(level, 0) + 1
        
        print("\nLevel distribution:")
        for level, count in sorted(level_counts.items()):
            print(f"  {level}: {count} words")
        
        return True
        
    except ImportError:
        print("pandas not installed. Installing...")
        os.system("../selmapp/bin/pip install pandas")
        return process_downloaded_files()
    except Exception as e:
        print(f"Error processing files: {e}")
        return False

def main():
    """Main function"""
    print("CEFR Vocabulary Dataset Downloader")
    print("=" * 40)
    
    # Check if files are already downloaded
    download_path = Path("../resources/vocabulary/kaggle_download")
    if download_path.exists() and list(download_path.glob("*.csv")):
        print("Files already downloaded. Processing...")
        if process_downloaded_files():
            print("Processing completed successfully!")
        else:
            print("Processing failed.")
    else:
        print("Downloading dataset...")
        if download_kaggle_dataset():
            print("Download completed. Processing files...")
            if process_downloaded_files():
                print("Processing completed successfully!")
            else:
                print("Processing failed.")
        else:
            print("Download failed. Please download manually.")

if __name__ == "__main__":
    main() 