import json
from datetime import datetime, timedelta
import pandas as pd

def calculate_weeks_worked(start_date, end_date, calendar_data):
    # Convert start_date and end_date to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    # Calculate total weeks in the period
    total_weeks = ((end_date - start_date).days + 1) // 7

    # Initialize dictionaries to store weeks worked and task counts for each physician
    weeks_worked = {physician: 0 for physician in calendar_data}
    task_counts = {physician: {} for physician in calendar_data}

    # Generate a list of week start dates
    current_week_start = start_date - timedelta(days=start_date.weekday())
    week_starts = []
    while current_week_start <= end_date:
        week_starts.append(current_week_start)
        current_week_start += timedelta(days=7)

    # Calculate weeks worked and task counts for each physician
    for physician, assignments in calendar_data.items():
        for week_start in week_starts:
            week_end = week_start + timedelta(days=6)
            worked_this_week = False

            for assignment in assignments:
                for day in assignment['days']:
                    work_date = datetime.strptime(day, "%Y-%m-%d")
                    if week_start <= work_date <= week_end and start_date <= work_date <= end_date:
                        worked_this_week = True
                        task_counts[physician][assignment['task']] = task_counts[physician].get(assignment['task'],
                                                                                                0) + 1
                        break

                if worked_this_week:
                    weeks_worked[physician] += 1
                    break

    # Create a dataframe from the results
    df = pd.DataFrame({
        'Physician': weeks_worked.keys(),
        'Weeks_Worked': weeks_worked.values(),
        'Percentage': [round(weeks / total_weeks * 100, 2) for weeks in weeks_worked.values()],
        'Task_Count': [json.dumps(counts) for counts in task_counts.values()]
    })

    return df

# Example usage
start_date = "2025-01-01"
end_date = "2025-06-30"

file_path = 'output/schedule/math_generated_schedule.json'
with open(file_path, 'r') as file:
    calendar = json.load(file)

result_df = calculate_weeks_worked(start_date, end_date, calendar)
print(result)