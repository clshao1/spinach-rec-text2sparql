#!/usr/bin/env python3
"""
Calculate how many decomposed questions have F1 > 0 in the new approach.
"""

import json

def count_decomposed_f1_positive(json_file: str, log_file: str):
    """
    Count decomposed questions (where decomposition_result is not null) that have F1 > 0.
    
    Args:
        json_file: Path to the JSON file with F1 scores (new approach)
        log_file: Path to the log file with decomposition info
        
    Returns:
        Tuple of (count with F1>0, total decomposed, list of questions with F1>0, list of questions with F1=0)
    """
    # Load JSON file - create a mapping from question to F1 score
    question_to_f1 = {}
    with open(json_file, 'r') as f:
        json_data = json.load(f)
    for entry in json_data:
        question = entry.get("question", "")
        f1 = entry.get("f1", 0.0)
        question_to_f1[question] = f1
    
    # Load log file - find entries where decomposition_result is not null
    decomposed_questions = set()
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    for entry in log_data:
        decomposition_result = entry.get("decomposition_result")
        # Check if decomposition_result is not null (meaning decomposition was used)
        if decomposition_result is not None:
            question = entry.get("question", "")
            if question.strip():
                decomposed_questions.add(question)
    
    # Match questions with JSON file and count F1>0
    f1_positive_count = 0
    f1_zero_count = 0
    f1_positive_questions = []
    f1_zero_questions = []
    not_found_questions = []
    total_decomposed = len(decomposed_questions)
    
    for question in decomposed_questions:
        if question in question_to_f1:
            f1 = question_to_f1[question]
            if f1 > 0.0:
                f1_positive_count += 1
                f1_positive_questions.append((question, f1))
            else:
                f1_zero_count += 1
                f1_zero_questions.append(question)
        else:
            not_found_questions.append(question)
    
    return f1_positive_count, f1_zero_count, total_decomposed, f1_positive_questions, f1_zero_questions, not_found_questions

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 3:
        json_file = sys.argv[1]
        log_file = sys.argv[2]
    else:
        json_file = "spinach_dataset/spinach_output_test_2.json"
        log_file = "spinach_dataset/spinach_output_test_2.log"
    
    # Count decomposed questions with F1 > 0
    f1_positive_count, f1_zero_count, total_decomposed, f1_positive_questions, f1_zero_questions, not_found_questions = count_decomposed_f1_positive(json_file, log_file)
    
    found_count = f1_positive_count + f1_zero_count
    
    print("="*60)
    print("NEW APPROACH PERFORMANCE ON DECOMPOSED QUESTIONS")
    print("="*60)
    print(f"Total decomposed questions (decomposition_result not null): {total_decomposed}")
    print(f"Found in JSON file: {found_count}")
    if len(not_found_questions) > 0:
        print(f"Not found in JSON file: {len(not_found_questions)}")
    
    print("\n" + "-"*60)
    print("F1 SCORE BREAKDOWN")
    print("-"*60)
    if found_count > 0:
        print(f"F1 > 0: {f1_positive_count} ({f1_positive_count * 100 / found_count:.2f}%)")
        print(f"F1 = 0: {f1_zero_count} ({f1_zero_count * 100 / found_count:.2f}%)")
        
        if f1_positive_questions:
            avg_f1 = sum(f1 for _, f1 in f1_positive_questions) / len(f1_positive_questions)
            max_f1 = max(f1 for _, f1 in f1_positive_questions)
            min_f1 = min(f1 for _, f1 in f1_positive_questions)
            print(f"\nFor questions with F1 > 0:")
            print(f"  Average F1: {avg_f1:.4f}")
            print(f"  Maximum F1: {max_f1:.4f}")
            print(f"  Minimum F1: {min_f1:.4f}")
    
    # Show questions with F1 > 0
    if f1_positive_questions:
        print(f"\n" + "="*60)
        print(f"QUESTIONS WITH F1 > 0 ({len(f1_positive_questions)})")
        print("="*60)
        for i, (q, f1) in enumerate(sorted(f1_positive_questions, key=lambda x: x[1], reverse=True), 1):
            print(f"  {i}. F1={f1:.4f}: {q}")
    
    # Show questions with F1 = 0
    if f1_zero_questions:
        print(f"\n" + "="*60)
        print(f"QUESTIONS WITH F1 = 0 ({len(f1_zero_questions)})")
        print("="*60)
        for i, q in enumerate(f1_zero_questions, 1):
            print(f"  {i}. {q}")
    
    # Show questions not found
    if not_found_questions:
        print(f"\n" + "="*60)
        print(f"QUESTIONS NOT FOUND IN JSON FILE ({len(not_found_questions)})")
        print("="*60)
        for i, q in enumerate(not_found_questions, 1):
            print(f"  {i}. {q}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Out of {total_decomposed} decomposed questions:")
    print(f"  - {f1_positive_count} have F1 > 0 ({f1_positive_count * 100 / total_decomposed:.2f}% of all decomposed)")
    print(f"  - {f1_zero_count} have F1 = 0 ({f1_zero_count * 100 / total_decomposed:.2f}% of all decomposed)")
    if len(not_found_questions) > 0:
        print(f"  - {len(not_found_questions)} not found in JSON file ({len(not_found_questions) * 100 / total_decomposed:.2f}% of all decomposed)")