#!/usr/bin/env python3
"""
Calculate decomposition-specific metrics from evaluation logs.
"""

import json
from collections import defaultdict
from typing import Dict, List

def has_results(result_dict):
    """Check if a result dict has successful execution results."""
    if not result_dict or not isinstance(result_dict, dict):
        return False
    execution_result = result_dict.get("execution_result")
    if execution_result is None:
        return False
    # execution_result is a list - empty list means no results
    return len(execution_result) > 0

def get_sparql_string(sparql_obj):
    """Extract SPARQL string from various formats."""
    if sparql_obj is None:
        return ""
    if isinstance(sparql_obj, str):
        return sparql_obj
    if isinstance(sparql_obj, dict):
        return sparql_obj.get("sparql", "")
    if hasattr(sparql_obj, 'sparql'):
        return sparql_obj.sparql
    return str(sparql_obj)

def calculate_decomposition_metrics(log_file: str) -> Dict:
    """
    Calculate metrics for decomposition agent performance.
    
    Args:
        log_file: Path to the .log file from evaluation
        
    Returns:
        Dictionary of metrics
    """
    with open(log_file, 'r') as f:
        logs = json.load(f)
    
    metrics = {
        "total_questions": len(logs),
        "decomposition_usage": {
            "chose_decompose": 0,
            "never_decomposed": 0,
            "decomposed_once": 0,
            "decomposed_multiple": 0,
        },
        "decomposition_success": {
            "simple_subquery_success": 0,
            "complex_subquery_success": 0,
            "both_succeeded": 0,
            "both_failed": 0,
            "simple_failed_complex_succeeded": 0,
            "simple_succeeded_complex_failed": 0,
        },
        "merge_success": {
            "merge_attempted": 0,
            "merge_succeeded": 0,
            "merge_failed": 0,
            "merge_fallback_to_complex": 0,
            "merge_fallback_to_simple": 0,
            "merge_unknown": 0,  # Can't determine merge outcome
        },
        "action_efficiency": {
            "avg_actions_without_decompose": [],
            "avg_actions_with_decompose": [],
            "avg_simple_subquery_actions": [],
        },
        "merge_operations": defaultdict(int),
        "recursive_depth_distribution": defaultdict(int),
    }
    
    for log_entry in logs:
        actions = log_entry.get("actions", [])
        decomposition_count = sum(1 for a in actions if a.get("action_name") == "decompose")
        recursive_depth = log_entry.get("recursive_depth", 0)
        decomposition_result = log_entry.get("decomposition_result")
        simple_result = log_entry.get("simple_subquery_result")
        complex_result = log_entry.get("complex_subquery_result")
        merge_operation = log_entry.get("merge_operation")
        final_sparql = log_entry.get("final_sparql")
        generated_sparqls = log_entry.get("generated_sparqls", [])
        
        # Get merge_operation from decomposition_result if not separate field
        if not merge_operation and decomposition_result and isinstance(decomposition_result, dict):
            merge_operation = decomposition_result.get("merge_operation")
        
        # Decomposition usage
        if decomposition_count == 0:
            metrics["decomposition_usage"]["never_decomposed"] += 1
            metrics["action_efficiency"]["avg_actions_without_decompose"].append(len(actions))
        elif decomposition_count == 1:
            metrics["decomposition_usage"]["decomposed_once"] += 1
            metrics["action_efficiency"]["avg_actions_with_decompose"].append(len(actions))
        else:
            metrics["decomposition_usage"]["decomposed_multiple"] += 1
        
        if decomposition_count > 0:
            metrics["decomposition_usage"]["chose_decompose"] += 1
        
        # Recursive depth
        metrics["recursive_depth_distribution"][recursive_depth] += 1
        
        # Decomposition success
        if decomposition_result:
            simple_success = has_results(simple_result)
            complex_success = has_results(complex_result)
            
            if simple_success:
                metrics["decomposition_success"]["simple_subquery_success"] += 1
            if complex_success:
                metrics["decomposition_success"]["complex_subquery_success"] += 1
            if simple_success and complex_success:
                metrics["decomposition_success"]["both_succeeded"] += 1
            elif not simple_success and not complex_success:
                metrics["decomposition_success"]["both_failed"] += 1
            elif simple_success and not complex_success:
                metrics["decomposition_success"]["simple_succeeded_complex_failed"] += 1
            elif not simple_success and complex_success:
                metrics["decomposition_success"]["simple_failed_complex_succeeded"] += 1
            
            # Simple subquery actions
            simple_actions = log_entry.get("simple_subquery_actions", [])
            if simple_actions:
                metrics["action_efficiency"]["avg_simple_subquery_actions"].append(len(simple_actions))
        
        # Merge success
        if merge_operation:
            metrics["merge_success"]["merge_attempted"] += 1
            metrics["merge_operations"][merge_operation] += 1
            
            # Check if merge succeeded by comparing final_sparql with simple/complex SPARQLs
            final_sparql_str = get_sparql_string(final_sparql)
            
            # If no final_sparql, try to get from generated_sparqls (last one with results)
            if not final_sparql_str and generated_sparqls:
                # Get last SPARQL with results
                for sparql_dict in reversed(generated_sparqls):
                    if has_results(sparql_dict):
                        final_sparql_str = get_sparql_string(sparql_dict)
                        break
                # If still no results, use last generated SPARQL
                if not final_sparql_str and generated_sparqls:
                    final_sparql_str = get_sparql_string(generated_sparqls[-1])
            
            if final_sparql_str:
                simple_sparql_str = get_sparql_string(simple_result)
                complex_sparql_str = get_sparql_string(complex_result)
                
                # Normalize whitespace for comparison
                final_sparql_str = final_sparql_str.strip()
                simple_sparql_str = simple_sparql_str.strip()
                complex_sparql_str = complex_sparql_str.strip()
                
                if final_sparql_str and final_sparql_str != simple_sparql_str and final_sparql_str != complex_sparql_str:
                    metrics["merge_success"]["merge_succeeded"] += 1
                elif final_sparql_str == complex_sparql_str:
                    metrics["merge_success"]["merge_fallback_to_complex"] += 1
                elif final_sparql_str == simple_sparql_str:
                    metrics["merge_success"]["merge_fallback_to_simple"] += 1
                else:
                    metrics["merge_success"]["merge_failed"] += 1
            else:
                metrics["merge_success"]["merge_unknown"] += 1
    
    # Calculate averages
    for key in ["avg_actions_without_decompose", "avg_actions_with_decompose", 
                "avg_simple_subquery_actions"]:
        if metrics["action_efficiency"][key]:
            metrics["action_efficiency"][f"{key}_avg"] = sum(metrics["action_efficiency"][key]) / len(metrics["action_efficiency"][key])
        else:
            metrics["action_efficiency"][f"{key}_avg"] = 0
    
    # Convert defaultdicts to regular dicts for JSON serialization
    metrics["merge_operations"] = dict(metrics["merge_operations"])
    metrics["recursive_depth_distribution"] = dict(metrics["recursive_depth_distribution"])
    
    return metrics

def print_decomposition_metrics(metrics: Dict):
    """Print decomposition metrics in a readable format."""
    print("\n" + "="*60)
    print("DECOMPOSITION AGENT METRICS")
    print("="*60)
    
    print(f"\nTotal Questions: {metrics['total_questions']}")
    
    print("\n--- Decomposition Usage ---")
    usage = metrics["decomposition_usage"]
    total = metrics['total_questions']
    if total > 0:
        print(f"  Chose decompose: {usage['chose_decompose']} ({usage['chose_decompose']*100/total:.1f}%)")
        print(f"  Never decomposed: {usage['never_decomposed']} ({usage['never_decomposed']*100/total:.1f}%)")
        print(f"  Decomposed once: {usage['decomposed_once']} ({usage['decomposed_once']*100/total:.1f}%)")
        print(f"  Decomposed multiple times: {usage['decomposed_multiple']} ({usage['decomposed_multiple']*100/total:.1f}%)")
    
    print("\n--- Decomposition Success ---")
    success = metrics["decomposition_success"]
    total_decomposed = usage['chose_decompose']
    if total_decomposed > 0:
        print(f"  Simple subquery success: {success['simple_subquery_success']} ({success['simple_subquery_success']*100/total_decomposed:.1f}%)")
        print(f"  Complex subquery success: {success['complex_subquery_success']} ({success['complex_subquery_success']*100/total_decomposed:.1f}%)")
        print(f"  Both succeeded: {success['both_succeeded']} ({success['both_succeeded']*100/total_decomposed:.1f}%)")
        print(f"  Both failed: {success['both_failed']} ({success['both_failed']*100/total_decomposed:.1f}%)")
        print(f"  Simple succeeded, complex failed: {success['simple_succeeded_complex_failed']} ({success['simple_succeeded_complex_failed']*100/total_decomposed:.1f}%)")
        print(f"  Simple failed, complex succeeded: {success['simple_failed_complex_succeeded']} ({success['simple_failed_complex_succeeded']*100/total_decomposed:.1f}%)")
    else:
        print("  No decompositions occurred")
    
    print("\n--- Merge Success ---")
    merge = metrics["merge_success"]
    if merge["merge_attempted"] > 0:
        print(f"  Merge attempted: {merge['merge_attempted']}")
        print(f"  Merge succeeded: {merge['merge_succeeded']} ({merge['merge_succeeded']*100/merge['merge_attempted']:.1f}%)")
        print(f"  Merge failed: {merge['merge_failed']} ({merge['merge_failed']*100/merge['merge_attempted']:.1f}%)")
        print(f"  Fallback to complex: {merge['merge_fallback_to_complex']} ({merge['merge_fallback_to_complex']*100/merge['merge_attempted']:.1f}%)")
        print(f"  Fallback to simple: {merge['merge_fallback_to_simple']} ({merge['merge_fallback_to_simple']*100/merge['merge_attempted']:.1f}%)")
        if merge['merge_unknown'] > 0:
            print(f"  Unknown outcome: {merge['merge_unknown']} ({merge['merge_unknown']*100/merge['merge_attempted']:.1f}%)")
    else:
        print("  No merge operations attempted")
    
    print("\n--- Action Efficiency ---")
    eff = metrics["action_efficiency"]
    print(f"  Avg actions (no decompose): {eff.get('avg_actions_without_decompose_avg', 0):.2f}")
    print(f"  Avg actions (with decompose): {eff.get('avg_actions_with_decompose_avg', 0):.2f}")
    print(f"  Avg simple subquery actions: {eff.get('avg_simple_subquery_actions_avg', 0):.2f}")
    
    print("\n--- Merge Operations Distribution ---")
    if metrics["merge_operations"]:
        for op, count in sorted(metrics["merge_operations"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {op}: {count}")
    else:
        print("  No merge operations found")
    
    print("\n--- Recursive Depth Distribution ---")
    for depth, count in sorted(metrics["recursive_depth_distribution"].items()):
        print(f"  Depth {depth}: {count} ({count*100/metrics['total_questions']:.1f}%)")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python calculate_decomposition_metrics.py <log_file.json>")
        sys.exit(1)
    
    log_file = sys.argv[1]
    metrics = calculate_decomposition_metrics(log_file)
    print_decomposition_metrics(metrics)
    
    # Optionally save to JSON
    output_file = log_file.replace(".log", "_decomposition_metrics.json")
    with open(output_file, 'w') as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"Metrics saved to {output_file}")