from datetime import datetime, date
import json
def check_unavailability_respected(unavailability_periods, calendar):
    violations = []

    for person, periods in unavailability_periods.items():
        if person not in calendar:
            continue

        for start, end in periods:
            for task in calendar[person]:
                task_start = datetime.strptime(task['start_date'], '%Y-%m-%d').date()
                task_end = datetime.strptime(task['end_date'], '%Y-%m-%d').date()

                if (start <= task_start <= end) or (start <= task_end <= end) or (task_start <= start and task_end >= end):
                    violations.append(f"{person}: Assigned {task['task']} from {task_start} to {task_end}, but unavailable from {start} to {end}")

    return violations


unavailability_periods = {
    "Eric Yamga": [
        (date(2025, 2, 10), date(2025, 2, 23)),
        (date(2025, 5, 5), date(2025, 5, 11)),
    ],
    "Madeleine Durand": [
        (date(2025, 1, 13), date(2025, 1, 13)),
        (date(2025, 3, 17), date(2025, 3, 23)),
        (date(2025, 6, 9), date(2025, 6, 15)),
    ],
    "Emmanuelle Duceppe": [
        (date(2025, 2, 3), date(2025, 2, 9)),
        (date(2025, 4, 21), date(2025, 4, 21)),
        (date(2025, 6, 2), date(2025, 6, 15)),
    ],
    "Emmanuel Sirdar": [
        (date(2025, 1, 6), date(2025, 1, 12)),
        (date(2025, 3, 10), date(2025, 3, 16)),
        (date(2025, 5, 19), date(2025, 5, 25)),
    ],
    "Florence Weber": [
        (date(2025, 2, 17), date(2025, 2, 23)),
        (date(2025, 4, 14), date(2025, 4, 20)),
        (date(2025, 6, 23), date(2025, 6, 29)),
    ],
    "Sophie Grandmaison": [
        (date(2025, 1, 20), date(2025, 1, 26)),
        (date(2025, 3, 31), date(2025, 4, 6)),
    ],
    "Michèle Mahone": [
        (date(2025, 2, 24), date(2025, 3, 2)),
        (date(2025, 5, 12), date(2025, 5, 18)),
    ],
    "Nazila Bettache": [
        (date(2025, 1, 27), date(2025, 2, 2)),
        (date(2025, 4, 7), date(2025, 4, 13)),
        (date(2025, 6, 16), date(2025, 6, 22)),
    ],
    "Vincent Williams": [
        (date(2025, 3, 3), date(2025, 3, 9)),
        (date(2025, 5, 26), date(2025, 6, 1)),
    ],
    "Gabriel Dion": [
        (date(2025, 1, 30), date(2025, 1, 31)),
        (date(2025, 4, 28), date(2025, 5, 4)),
    ],
    "Justine Munger": [
        (date(2025, 1, 1), date(2025, 1, 5)),
        (date(2025, 3, 24), date(2025, 3, 30)),
        (date(2025, 6, 9), date(2025, 6, 15)),
    ],
    "Mikhael Laskine": [
        (date(2025, 2, 3), date(2025, 2, 9)),
        (date(2025, 5, 5), date(2025, 5, 11)),
    ],
    "Benoit Deligne": [
        (date(2025, 1, 13), date(2025, 1, 26)),
        (date(2025, 3, 31), date(2025, 4, 6)),
        (date(2025, 6, 2), date(2025, 6, 8)),
    ],
    "Maxime Lamarre-Cliche": [
        (date(2025, 3, 10), date(2025, 3, 16)),
        (date(2025, 5, 19), date(2025, 5, 25)),
    ],
    "Julien D'Astous": [
        (date(2025, 2, 10), date(2025, 2, 16)),
        (date(2025, 4, 21), date(2025, 4, 27)),
    ],
    "Jean-Pascal Costa": [
        (date(2025, 1, 27), date(2025, 2, 2)),
        (date(2025, 4, 7), date(2025, 4, 13)),
        (date(2025, 6, 16), date(2025, 6, 22)),
    ],
    "Camille Laflamme": [
        (date(2025, 3, 17), date(2025, 3, 23)),
        (date(2025, 5, 26), date(2025, 6, 1)),
    ],
    "Robert Wistaff": [
        (date(2025, 2, 17), date(2025, 2, 23)),
        (date(2025, 4, 28), date(2025, 5, 4)),
    ],
    "Rene Lecours": [
        (date(2025, 1, 6), date(2025, 1, 12)),
        (date(2025, 3, 24), date(2025, 3, 30)),
        (date(2025, 6, 9), date(2025, 6, 15)),
    ],
    "Diem-Quyen Nguyen": [
        (date(2025, 2, 24), date(2025, 3, 2)),
        (date(2025, 5, 12), date(2025, 5, 18)),
    ],
    "Michel Bertrand": [
        (date(2025, 1, 20), date(2025, 1, 26)),
        (date(2025, 4, 14), date(2025, 4, 20)),
    ],
    "J.Manuel Dominguez": [
        (date(2025, 3, 3), date(2025, 3, 9)),
        (date(2025, 5, 19), date(2025, 5, 25)),
    ],
    "Marie-Jose Miron": [
        (date(2025, 2, 3), date(2025, 2, 9)),
        (date(2025, 4, 21), date(2025, 4, 27)),
        (date(2025, 6, 23), date(2025, 6, 29)),
    ],
    "André Roussin": [
        (date(2025, 1, 13), date(2025, 1, 19)),
        (date(2025, 3, 31), date(2025, 4, 6)),
        (date(2025, 6, 2), date(2025, 6, 8)),
    ],
    "Martial Koenig": [
        (date(2025, 2, 10), date(2025, 2, 16)),
        (date(2025, 5, 5), date(2025, 5, 11)),
    ],
}

file_path = 'output/schedule/math_generated_schedule.json'
with open(file_path, 'r') as file:
    calendar = json.load(file)

violations = check_unavailability_respected(unavailability_periods, calendar)

# Print results
if violations:
    print("The following violations were found:")
    for violation in violations:
        print(violation)
else:
    print("No violations found. All unavailability periods were respected.")


