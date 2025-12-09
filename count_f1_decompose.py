#!/usr/bin/env python3
"""
Count examples with F1 > 0 that used decomposition.
Also count decomposed questions with F1 = 0 in baseline.
"""

import json

def count_decomposed_baseline_f1_zero(baseline_file: str, log_file: str):
    """
    Count decomposed questions (where original_question is not null) that have F1 = 0 in baseline.
    
    Args:
        baseline_file: Path to the baseline JSON file with F1 scores
        log_file: Path to the log file with decomposition info
        
    Returns:
        Tuple of (count with F1=0, total decomposed, list of questions with F1=0, list of all decomposed with F1 scores)
    """
    # Load baseline JSON file - create a mapping from question to F1 score
    question_to_f1 = {}
    with open(baseline_file, 'r') as f:
        baseline_data = json.load(f)
    for entry in baseline_data:
        question = entry.get("question", "")
        f1 = entry.get("f1", 0.0)
        question_to_f1[question] = f1
    
    # Load log file - find entries where original_question is not null
    decomposed_original_questions = set()
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    for entry in log_data:
        original_question = entry.get("original_question")
        if original_question is not None and original_question.strip():
            decomposed_original_questions.add(original_question)
    
    # Match original questions with baseline file and count F1=0
    f1_zero_count = 0
    f1_zero_questions = []
    f1_positive_questions = []
    not_found_questions = []
    total_decomposed = len(decomposed_original_questions)
    all_decomposed_with_f1 = []
    
    for original_question in decomposed_original_questions:
        if original_question in question_to_f1:
            f1 = question_to_f1[original_question]
            all_decomposed_with_f1.append((original_question, f1))
            if f1 == 0.0:
                f1_zero_count += 1
                f1_zero_questions.append(original_question)
            else:
                f1_positive_questions.append((original_question, f1))
        else:
            not_found_questions.append(original_question)
    
    return f1_zero_count, total_decomposed, f1_zero_questions, f1_positive_questions, not_found_questions, all_decomposed_with_f1

def count_decomposed_f1_zero(json_file: str, log_file: str):
    """
    Count decomposed questions (where original_question is not null) that have F1 = 0.
    
    Args:
        json_file: Path to the JSON file with F1 scores
        log_file: Path to the log file with decomposition info
        
    Returns:
        Tuple of (count with F1=0, total decomposed, list of questions with F1=0)
    """
    # Load JSON file - create a mapping from question to F1 score
    question_to_f1 = {}
    with open(json_file, 'r') as f:
        json_data = json.load(f)
    for entry in json_data:
        question = entry.get("question", "")
        f1 = entry.get("f1", 0.0)
        question_to_f1[question] = f1
    
    # Load log file - find entries where original_question is not null
    decomposed_original_questions = set()
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    for entry in log_data:
        original_question = entry.get("original_question")
        if original_question is not None and original_question.strip():
            decomposed_original_questions.add(original_question)
    
    # Match original questions with JSON file and count F1=0
    f1_zero_count = 0
    f1_zero_questions = []
    total_decomposed = len(decomposed_original_questions)
    
    for original_question in decomposed_original_questions:
        if original_question in question_to_f1:
            f1 = question_to_f1[original_question]
            if f1 == 0.0:
                f1_zero_count += 1
                f1_zero_questions.append(original_question)
    
    return f1_zero_count, total_decomposed, f1_zero_questions

def count_f1_with_decompose(json_file: str, log_file: str):
    """
    Count examples that have F1 > 0 and used decomposition.
    
    Args:
        json_file: Path to the JSON file with F1 scores
        log_file: Path to the log file with decomposition info
        
    Returns:
        Count of matching examples
    """
    # Load JSON file
    with open(json_file, 'r') as f:
        json_data = json.load(f)
    
    # Load log file
    with open(log_file, 'r') as f:
        log_data = json.load(f)
    
    # Create sets of questions with F1 > 0
    f1_positive_questions = set()
    for entry in json_data:
        question = entry.get("question", "")
        f1 = entry.get("f1", 0.0)
        if f1 > 0:
            f1_positive_questions.add(question)
    
    # Create set of questions that used decomposition
    decompose_questions = set()
    for entry in log_data:
        question = entry.get("question", "")
        decomposition_result = entry.get("decomposition_result")
        if decomposition_result is not None:
            decompose_questions.add(question)
    
    # Find intersection
    matching_questions = f1_positive_questions & decompose_questions
    
    return len(matching_questions), len(f1_positive_questions), len(decompose_questions)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) >= 3:
        baseline_file = sys.argv[1]
        log_file = sys.argv[2]
    else:
        baseline_file = "spinach_dataset/spinach_output_test.json"
        log_file = "spinach_dataset/spinach_output_test_2.log"
    
    # Count decomposed questions with F1 = 0 in baseline
    f1_zero_count, total_decomposed, f1_zero_questions, f1_positive_questions, not_found_questions, all_decomposed_with_f1 = count_decomposed_baseline_f1_zero(baseline_file, log_file)
    
    print("="*60)
    print("BASELINE PERFORMANCE ON DECOMPOSED QUESTIONS")
    print("="*60)
    print(f"Total decomposed questions (original_question not null): {total_decomposed}")
    print(f"Found in baseline file: {len(all_decomposed_with_f1)}")
    if len(not_found_questions) > 0:
        print(f"Not found in baseline file: {len(not_found_questions)}")
    
    if len(all_decomposed_with_f1) > 0:
        print(f"\nBaseline F1 = 0: {f1_zero_count}")
        print(f"Baseline F1 > 0: {len(f1_positive_questions)}")
        print(f"Percentage with F1 = 0: {f1_zero_count * 100 / len(all_decomposed_with_f1):.2f}%")
        print(f"Percentage with F1 > 0: {len(f1_positive_questions) * 100 / len(all_decomposed_with_f1):.2f}%")
        
        # Calculate average F1 for decomposed questions in baseline
        avg_f1 = sum(f1 for _, f1 in all_decomposed_with_f1) / len(all_decomposed_with_f1)
        print(f"Average F1 for decomposed questions in baseline: {avg_f1:.4f}")
    
    if f1_zero_questions:
        print(f"\nDecomposed questions where baseline has F1 = 0 ({len(f1_zero_questions)}):")
        for i, q in enumerate(f1_zero_questions, 1):
            print(f"  {i}. {q}")
    
    if f1_positive_questions:
        print(f"\nDecomposed questions where baseline has F1 > 0 ({len(f1_positive_questions)}):")
        for i, (q, f1) in enumerate(sorted(f1_positive_questions, key=lambda x: x[1], reverse=True), 1):
            print(f"  {i}. F1={f1:.4f}: {q}")
    
    if not_found_questions:
        print(f"\nDecomposed questions not found in baseline ({len(not_found_questions)}):")
        for i, q in enumerate(not_found_questions, 1):
            print(f"  {i}. {q}")
