import json
import csv
from collections import defaultdict

def check_category_diversity(calendar_data):
    """
    Check the diversity of task categories assigned to each physician.
    """
    results = []
    total_diversity_index = 0
    total_consecutive_sequences = 0
    max_consecutive_sequences = 0
    
    for physician, assignments in calendar_data.items():
        # Count categories
        category_counts = defaultdict(int)
        consecutive_same = []
        current_sequence = []
        
        # Sort assignments by date
        sorted_assignments = sorted(assignments, key=lambda x: x['start_date'])
        
        for i, assignment in enumerate(sorted_assignments):
            category = assignment['task'].split('_')[0]
            category_counts[category] += 1
            
            if i > 0:
                prev_category = sorted_assignments[i-1]['task'].split('_')[0]
                if category == prev_category:
                    if not current_sequence:
                        current_sequence.extend([sorted_assignments[i-1], assignment])
                    else:
                        current_sequence.append(assignment)
                else:
                    if current_sequence:
                        consecutive_same.append({
                            'category': prev_category,
                            'sequence': [a['task'] for a in current_sequence],
                            'dates': [a['start_date'] for a in current_sequence]
                        })
                        current_sequence = []
        
        if current_sequence:
            consecutive_same.append({
                'category': current_sequence[0]['task'].split('_')[0],
                'sequence': [a['task'] for a in current_sequence],
                'dates': [a['start_date'] for a in current_sequence]
            })
        
        # Calculate metrics
        total_assignments = len(assignments)
        unique_categories = len(category_counts)
        diversity_index = unique_categories / total_assignments if total_assignments > 0 else 0
        
        result = {
            'physician': physician,
            'category_distribution': dict(category_counts),
            'unique_categories': unique_categories,
            'diversity_index': diversity_index,
            'consecutive_same_category': consecutive_same,
            'total_consecutive_sequences': len(consecutive_same)
        }
        results.append(result)
        
        total_diversity_index += diversity_index
        total_consecutive_sequences += len(consecutive_same)
        max_consecutive_sequences = max(max_consecutive_sequences, len(consecutive_same))
    
    # Calculate aggregated metrics
    num_physicians = len(results)
    aggregated_metrics = {
        'average_diversity_index': total_diversity_index / num_physicians if num_physicians > 0 else 0,
        'total_consecutive_sequences': total_consecutive_sequences,
        'average_consecutive_sequences': total_consecutive_sequences / num_physicians if num_physicians > 0 else 0,
        'max_consecutive_sequences': max_consecutive_sequences,
        'total_physicians': num_physicians
    }
    
    # Export to CSV
    with open('../output/analysis/category_diversity_analysis.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Physician', 'Unique Categories', 'Diversity Index', 'Consecutive Sequences'])
        for r in results:
            writer.writerow([
                r['physician'],
                r['unique_categories'],
                f"{r['diversity_index']:.3f}",
                r['total_consecutive_sequences']
            ])
        
        writer.writerow([])
        writer.writerow(['Aggregated Metrics'])
        for metric, value in aggregated_metrics.items():
            writer.writerow([metric, value])
    
    return results, aggregated_metrics

# Example usage
file_path = '../output/schedule/alternative_generated_schedule.json'

with open(file_path, 'r') as file:
    calendar = json.load(file)

results, metrics = check_category_diversity(calendar)
print("Aggregated Metrics:")
print(json.dumps(metrics, indent=2)) 