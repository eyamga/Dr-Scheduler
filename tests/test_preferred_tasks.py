import json
import csv
from collections import defaultdict

def check_preferred_tasks_assignment(calendar_data):
    """
    Check if physicians are assigned their preferred tasks and in what proportion.
    """
    with open('../output/config/physician_config.json', 'r') as f:
        physician_data = json.load(f)
    
    # Fix the mapping to use preferred_tasks
    preferred_tasks = {
        p['first_name'] + " " + p['last_name']: p['preferred_tasks']
        for p in physician_data['physicians']
    }
    
    results = []
    total_preferred_percentage = 0
    min_preferred_percentage = 1.0
    max_preferred_percentage = 0
    
    for physician, assignments in calendar_data.items():
        task_counts = defaultdict(int)
        preferred_counts = defaultdict(int)
        total_assignments = 0
        
        for assignment in assignments:
            task_category = assignment['task'].split('_')[0]
            task_counts[task_category] += 1
            total_assignments += 1
            
            if physician in preferred_tasks and task_category in preferred_tasks[physician]:
                preferred_counts[task_category] += 1
        
        if total_assignments > 0:
            preferred_percentage = sum(preferred_counts.values()) / total_assignments
            result = {
                'physician': physician,
                'preferred_tasks': preferred_tasks.get(physician, []),
                'total_assignments': total_assignments,
                'preferred_assignments': dict(preferred_counts),
                'preferred_percentage': preferred_percentage,
                'task_distribution': dict(task_counts)
            }
            results.append(result)
            
            total_preferred_percentage += preferred_percentage
            min_preferred_percentage = min(min_preferred_percentage, preferred_percentage)
            max_preferred_percentage = max(max_preferred_percentage, preferred_percentage)
    
    # Calculate aggregated metrics
    num_physicians = len(results)
    aggregated_metrics = {
        'average_preferred_percentage': total_preferred_percentage / num_physicians if num_physicians > 0 else 0,
        'min_preferred_percentage': min_preferred_percentage,
        'max_preferred_percentage': max_preferred_percentage,
        'physicians_below_30_percent': sum(1 for r in results if r['preferred_percentage'] < 0.3),
        'total_physicians': num_physicians
    }
    
    # Export detailed results to CSV
    with open('../output/analysis/preferred_tasks_analysis.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Physician', 'Preferred Tasks', 'Total Assignments', 'Preferred Assignments', 'Preferred %'])
        for r in results:
            writer.writerow([
                r['physician'],
                ', '.join(r['preferred_tasks']),
                r['total_assignments'],
                sum(r['preferred_assignments'].values()),
                f"{r['preferred_percentage']:.2%}"
            ])
        
        # Add aggregated metrics
        writer.writerow([])
        writer.writerow(['Aggregated Metrics'])
        for metric, value in aggregated_metrics.items():
            writer.writerow([metric, value])
    
    return results, aggregated_metrics

# Example usage
file_path = '../output/schedule/alternative_generated_schedule.json'

with open(file_path, 'r') as file:
    calendar = json.load(file)

results, metrics = check_preferred_tasks_assignment(calendar)
print("Aggregated Metrics:")
print(json.dumps(metrics, indent=2)) 