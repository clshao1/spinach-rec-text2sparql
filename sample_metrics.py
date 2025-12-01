#!/usr/bin/env python3
"""
Calculate row-major F1 and row-major EM scores from evaluation JSON file.
"""

import json
import sys

def calculate_metrics(json_file):
    """
    Calculate row-major F1 and row-major EM from evaluation results.
    
    Args:
        json_file: Path to JSON file with evaluation results
        
    Returns:
        tuple: (row_major_f1, row_major_em, total_count)
    """
    with open(json_file, 'r') as f:
        results = json.load(f)
    
    if not results:
        print("No results found in file.")
        return 0.0, 0.0, 0
    
    # Extract F1 scores
    f1_scores = []
    em_count = 0
    total_count = len(results)
    
    for entry in results:
        f1 = entry.get("f1", 0.0)
        f1_scores.append(f1)
        if f1 == 1.0:
            em_count += 1
    
    # Calculate row-major F1 (average of all F1 scores)
    row_major_f1 = sum(f1_scores) / total_count if total_count > 0 else 0.0
    
    # Calculate row-major EM (percentage with F1 == 1.0)
    row_major_em = (em_count / total_count) * 100 if total_count > 0 else 0.0
    
    return row_major_f1, row_major_em, total_count

def main():
    if len(sys.argv) != 2:
        print("Usage: python calculate_metrics.py <json_file>")
        print("Example: python calculate_metrics.py sample_log.json")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        row_major_f1, row_major_em, total_count = calculate_metrics(json_file)
        
        print(f"\nEvaluation Metrics for {json_file}")
        print("=" * 50)
        print(f"Total number of examples: {total_count}")
        print(f"Row-major F1: {row_major_f1 * 100:.2f}%")
        print(f"Row-major EM: {row_major_em:.2f}%")
        print("=" * 50)
        
    except FileNotFoundError:
        print(f"Error: File '{json_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file '{json_file}': {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()