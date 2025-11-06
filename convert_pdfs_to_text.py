#!/usr/bin/env python3
"""
PDF to Text Converter
Converts all PDF files in the current directory to text files for easier processing.
"""

import os
import sys
import pdfplumber
from pathlib import Path


def convert_pdf_to_text(pdf_path, output_path=None):
    """
    Convert a PDF file to text format.

    Args:
        pdf_path: Path to the PDF file
        output_path: Optional path for the output text file.
                    If None, uses the same name with .txt extension

    Returns:
        The path to the created text file
    """
    if output_path is None:
        output_path = str(pdf_path).rsplit('.', 1)[0] + '.txt'

    try:
        print(f"Converting: {pdf_path}")

        with pdfplumber.open(pdf_path) as pdf:
            text_content = []

            for i, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"{'='*80}\n")
                    text_content.append(f"Page {i}\n")
                    text_content.append(f"{'='*80}\n\n")
                    text_content.append(page_text)
                    text_content.append("\n\n")

            # Write to text file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(''.join(text_content))

            print(f"  ✓ Created: {output_path}")
            print(f"  Pages processed: {len(pdf.pages)}")
            return output_path

    except Exception as e:
        print(f"  ✗ Error converting {pdf_path}: {str(e)}")
        return None


def convert_all_pdfs_in_directory(directory='.'):
    """
    Convert all PDF files in the specified directory to text files.

    Args:
        directory: Path to the directory containing PDFs (default: current directory)
    """
    directory = Path(directory)
    pdf_files = list(directory.glob('*.pdf'))

    if not pdf_files:
        print("No PDF files found in the directory.")
        return

    print(f"Found {len(pdf_files)} PDF file(s)\n")

    successful = 0
    failed = 0

    for pdf_file in sorted(pdf_files):
        result = convert_pdf_to_text(pdf_file)
        if result:
            successful += 1
        else:
            failed += 1
        print()

    print(f"\n{'='*80}")
    print(f"Conversion Summary:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(pdf_files)}")
    print(f"{'='*80}")


if __name__ == "__main__":
    # Get directory from command line argument or use current directory
    directory = sys.argv[1] if len(sys.argv) > 1 else '.'
    convert_all_pdfs_in_directory(directory)
