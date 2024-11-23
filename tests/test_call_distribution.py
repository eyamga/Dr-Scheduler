import json
import csv
from datetime import datetime, timedelta
from collections import defaultdict

def check_call_distribution(start_date, end_date, calendar_data):
    """
    Enhanced check of call task distribution including spacing and patterns.
    """
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    
    results = []
    total_violations = 0
    total_calls = 0
    max_calls_per_month = 0
    
    for physician, assignments in calendar_data.items():
        # Collect all call assignments
        call_assignments = []
        for assignment in assignments:
            if 'CALL' in assignment['task']:
                start = datetime.strptime(assignment['start_date'], "%Y-%m-%d")
                end = datetime.strptime(assignment['end_date'], "%Y-%m-%d")
                if start_date <= start <= end_date:
                    call_assignments.append({
                        'task': assignment['task'],
                        'start': start,
                        'end': end
                    })
        
        if call_assignments:
            call_assignments.sort(key=lambda x: x['start'])
            
            # Calculate spacing between calls
            spacings = []
            for i in range(1, len(call_assignments)):
                days_between = (call_assignments[i]['start'] - call_assignments[i-1]['end']).days
                spacings.append(days_between)
            
            # Group by month
            monthly_calls = defaultdict(list)
            for call in call_assignments:
                month_key = f"{call['start'].year}-{call['start'].month:02d}"
                monthly_calls[month_key].append(call['task'])
            
            # Calculate metrics
            calls_per_month = {month: len(calls) for month, calls in monthly_calls.items()}
            max_month_calls = max(calls_per_month.values()) if calls_per_month else 0
            max_calls_per_month = max(max_calls_per_month, max_month_calls)
            
            spacing_violations = [
                {'index': i, 'days': spacing}
                for i, spacing in enumerate(spacings)
                if spacing < 21
            ]
            total_violations += len(spacing_violations)
            total_calls += len(call_assignments)
            
            results.append({
                'physician': physician,
                'total_calls': len(call_assignments),
                'monthly_distribution': dict(monthly_calls),
                'calls_per_month': calls_per_month,
                'average_spacing': sum(spacings) / len(spacings) if spacings else 0,
                'min_spacing': min(spacings) if spacings else None,
                'spacing_violations': spacing_violations
            })
    
    # Calculate aggregated metrics
    num_physicians = len(results)
    aggregated_metrics = {
        'total_calls': total_calls,
        'total_spacing_violations': total_violations,
        'average_calls_per_physician': total_calls / num_physicians if num_physicians > 0 else 0,
        'max_calls_per_month': max_calls_per_month,
        'physicians_with_violations': sum(1 for r in results if r['spacing_violations']),
        'total_physicians': num_physicians
    }
    
    # Export to CSV
    with open('../output/analysis/call_distribution_analysis.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Physician', 'Total Calls', 'Avg Spacing', 'Min Spacing', 'Violations'])
        for r in results:
            writer.writerow([
                r['physician'],
                r['total_calls'],
                f"{r['average_spacing']:.1f}",
                r['min_spacing'],
                len(r['spacing_violations'])
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

results, metrics = check_call_distribution(start_date, end_date, calendar)
print("Aggregated Metrics:")
print(json.dumps(metrics, indent=2)) 