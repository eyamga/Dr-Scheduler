import json
import csv
from datetime import datetime, timedelta

def check_consecutive_heavy_tasks(start_date, end_date, calendar_data):
    """
    Check for consecutive heavy tasks and their distribution.
    """
    # Load task configuration
    with open('../output/config/task_config.json', 'r') as f:
        task_config = json.load(f)
    
    # Create mapping of task heaviness
    task_heaviness = {
        task['name']: task['heaviness']
        for task in task_config['tasks']
    }
    
    results = []
    total_heavy_sequences = 0
    max_sequence_length = 0
    total_heavy_tasks = 0
    
    for physician, assignments in calendar_data.items():
        # Sort assignments by date
        sorted_assignments = sorted(assignments, key=lambda x: x['start_date'])
        
        consecutive_heavy = []
        current_sequence = []
        physician_heavy_tasks = 0
        
        for i, assignment in enumerate(sorted_assignments):
            task_name = assignment['task']
            heaviness = task_heaviness.get(task_name, 0)
            
            if heaviness >= 3:  # Consider tasks with heaviness 3-5 as heavy
                physician_heavy_tasks += 1
                current_sequence.append({
                    'task': task_name,
                    'heaviness': heaviness,
                    'start_date': assignment['start_date'],
                    'end_date': assignment['end_date']
                })
            else:
                if len(current_sequence) > 1:
                    consecutive_heavy.append(current_sequence)
                    max_sequence_length = max(max_sequence_length, len(current_sequence))
                current_sequence = []
        
        if len(current_sequence) > 1:
            consecutive_heavy.append(current_sequence)
            max_sequence_length = max(max_sequence_length, len(current_sequence))
        
        if consecutive_heavy or physician_heavy_tasks > 0:
            result = {
                'physician': physician,
                'consecutive_heavy_sequences': consecutive_heavy,
                'total_sequences': len(consecutive_heavy),
                'total_heavy_tasks': physician_heavy_tasks,
                'max_sequence_length': max(len(seq) for seq in consecutive_heavy) if consecutive_heavy else 0
            }
            results.append(result)
            
            total_heavy_sequences += len(consecutive_heavy)
            total_heavy_tasks += physician_heavy_tasks
    
    # Calculate aggregated metrics
    num_physicians = len(results)
    aggregated_metrics = {
        'total_heavy_sequences': total_heavy_sequences,
        'average_sequences_per_physician': total_heavy_sequences / num_physicians if num_physicians > 0 else 0,
        'max_sequence_length': max_sequence_length,
        'total_heavy_tasks': total_heavy_tasks,
        'average_heavy_tasks_per_physician': total_heavy_tasks / num_physicians if num_physicians > 0 else 0,
        'physicians_with_consecutive_heavy': sum(1 for r in results if r['consecutive_heavy_sequences']),
        'total_physicians': num_physicians
    }
    
    # Export to CSV
    with open('../output/analysis/heaviness_analysis.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Physician', 'Total Heavy Tasks', 'Consecutive Sequences', 'Max Sequence Length'])
        for r in results:
            writer.writerow([
                r['physician'],
                r['total_heavy_tasks'],
                r['total_sequences'],
                r['max_sequence_length']
            ])
        
        writer.writerow([])
        writer.writerow(['Aggregated Metrics'])
        for metric, value in aggregated_metrics.items():
            writer.writerow([metric, value])
    
    return results, aggregated_metrics

# Example usage
start_date = "2025-01-13"
end_date = "2025-06-30"
file_path = '../output/schedule/alternative_generated_schedule.json'

with open(file_path, 'r') as file:
    calendar = json.load(file)

results, metrics = check_consecutive_heavy_tasks(start_date, end_date, calendar)
print("Aggregated Metrics:")
print(json.dumps(metrics, indent=2)) 