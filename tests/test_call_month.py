import json
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import groupby


def check_call_tasks(start_date, end_date, calendar_data):

    # Convert start_date and end_date to datetime objects
    start_date = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    # Function to check if a task is a call task
    is_call_task = lambda task: 'call' in task.lower()

    # Initialize result list
    result = []

    # Iterate through each physician
    for physician, assignments in calendar_data.items():
        # Group assignments into four-week periods
        periods = defaultdict(lambda: defaultdict(list))

        # Group consecutive call tasks
        call_tasks = []
        for assignment in assignments:
            task = assignment['task']
            if is_call_task(task):
                call_tasks.extend((task, datetime.strptime(day, "%Y-%m-%d")) for day in assignment['days'])

        # Sort call tasks by date
        call_tasks.sort(key=lambda x: x[1])

        # Group consecutive dates
        grouped_tasks = []
        for _, group in groupby(call_tasks, key=lambda x: x[1].toordinal()):
            group_list = list(group)
            grouped_tasks.append((group_list[0][0], group_list[0][1], group_list[-1][1]))

        # Assign grouped tasks to periods
        for task, start, end in grouped_tasks:
            if start_date <= start <= end_date:
                period_start = start_date + timedelta(days=((start - start_date).days // 28) * 28)
                periods[period_start][task].append((start, end))

        # Check for periods with more than 1 call task
        for period_start, tasks in periods.items():
            if len(tasks) > 1:
                result.append({
                    'physician': physician,
                    'period': period_start.strftime("%Y-%m-%d"),
                    'tasks': {task: [(s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")) for s, e in dates] for task, dates
                              in tasks.items()}
                })

    return result


# Example usage
start_date = "2025-01-01"
end_date = "2025-06-30"
file_path = 'output/schedule/math_generated_schedule.json'
with open(file_path, 'r') as file:
    calendar = json.load(file)

result = check_call_tasks(start_date, end_date, calendar)
print(json.dumps(result, indent=2))