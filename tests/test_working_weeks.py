import json
import csv
from datetime import datetime
from collections import defaultdict

def check_working_weeks_distribution(start_date, end_date, calendar_data):
    """
    Check if physicians' working weeks match their desired percentage and are evenly distributed.
    """
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    
    with open('../output/config/physician_config.json', 'r') as f:
        physician_data = json.load(f)
    
    desired_percentages = {
        p['first_name'] + " " + p['last_name']: p['desired_working_weeks']
        for p in physician_data['physicians']
    }
    
    results = []
    total_deviation = 0
    max_deviation = 0
    total_std_dev = 0
    
    for physician, assignments in calendar_data.items():
        monthly_assignments = defaultdict(int)
        total_weeks = 0
        
        for assignment in assignments:
            start = datetime.strptime(assignment['start_date'], "%Y-%m-%d")
            end = datetime.strptime(assignment['end_date'], "%Y-%m-%d")
            
            if start_date <= start <= end_date:
                month_key = f"{start.year}-{start.month:02d}"
                weeks = (end - start).days / 7 + 1
                monthly_assignments[month_key] += weeks
                total_weeks += weeks
        
        total_available_weeks = (end_date - start_date).days / 7
        actual_percentage = total_weeks / total_available_weeks
        desired_percentage = desired_percentages.get(physician, 0)
        percentage_difference = abs(desired_percentage - actual_percentage)
        
        if monthly_assignments:
            mean_weeks = sum(monthly_assignments.values()) / len(monthly_assignments)
            variance = sum((weeks - mean_weeks) ** 2 for weeks in monthly_assignments.values()) / len(monthly_assignments)
            std_dev = variance ** 0.5
        else:
            std_dev = 0
        
        results.append({
            'physician': physician,
            'desired_percentage': desired_percentage,
            'actual_percentage': actual_percentage,
            'percentage_difference': percentage_difference,
            'distribution_evenness': std_dev,
            'monthly_breakdown': dict(monthly_assignments)
        })
        
        total_deviation += percentage_difference
        max_deviation = max(max_deviation, percentage_difference)
        total_std_dev += std_dev
    
    num_physicians = len(results)
    aggregated_metrics = {
        'average_deviation': total_deviation / num_physicians if num_physicians > 0 else 0,
        'max_deviation': max_deviation,
        'average_std_dev': total_std_dev / num_physicians if num_physicians > 0 else 0,
        'physicians_over_10_percent_off': sum(1 for r in results if r['percentage_difference'] > 0.1),
        'total_physicians': num_physicians
    }
    
    with open('../output/analysis/working_weeks_analysis.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Physician', 'Desired %', 'Actual %', 'Difference', 'Distribution StdDev'])
        for r in results:
            writer.writerow([
                r['physician'],
                f"{r['desired_percentage']:.2%}",
                f"{r['actual_percentage']:.2%}",
                f"{r['percentage_difference']:.2%}",
                f"{r['distribution_evenness']:.2f}"
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

results, metrics = check_working_weeks_distribution(start_date, end_date, calendar)
print("Aggregated Metrics:")
print(json.dumps(metrics, indent=2)) 