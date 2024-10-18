from datetime import date


class PhysicianManager:
    def __init__(self):
        self.unavailability_periods = {
            "Emmanuelle Duceppe": [
                (date(2025, 1, 20), date(2025, 1, 26)),
            ],
            "Sophie Grandmaison": [
                (date(2025, 1, 1), date(2025, 1, 5)),
            ],
            "Michel Bertrand": [
                (date(2025, 1, 6), date(2025, 1, 12)),
            ],
        }

    def is_unavailable(self, name: str, check_date: date) -> bool:
        if name not in self.unavailability_periods:
            return False

        for period in self.unavailability_periods[name]:
            if isinstance(period, tuple) and len(period) == 2:
                start_date, end_date = period
                if start_date <= check_date <= end_date:
                    return True
            elif isinstance(period, date):
                if period == check_date:
                    return True
        return False


def test_is_unavailable():
    manager = PhysicianManager()

    # Test case for Emmanuelle Duceppe
    print("Emmanuelle Duceppe:")
    for day in range(19, 28):
        date_to_check = date(2025, 1, day)
        print(f"  {date_to_check}: {manager.is_unavailable('Emmanuelle Duceppe', date_to_check)}")

    # Test case for Sophie Grandmaison
    print("\nSophie Grandmaison:")
    for day in range(1, 7):
        date_to_check = date(2025, 1, day)
        print(f"  {date_to_check}: {manager.is_unavailable('Sophie Grandmaison', date_to_check)}")

    # Test case for Michel Bertrand
    print("\nMichel Bertrand:")
    for day in range(5, 14):
        date_to_check = date(2025, 1, day)
        print(f"  {date_to_check}: {manager.is_unavailable('Michel Bertrand', date_to_check)}")

    # Test case for CONSULT_2 task
    print("\nCONSULT_2 task (2025-01-20 to 2025-01-24):")
    task_start = date(2025, 1, 20)
    task_end = date(2025, 1, 24)
    for name in ["Emmanuelle Duceppe", "Sophie Grandmaison", "Michel Bertrand"]:
        is_unavailable = any(manager.is_unavailable(name, date_to_check)
                             for date_to_check in [task_start, task_end])
        print(f"  {name}: {is_unavailable}")


if __name__ == "__main__":
    test_is_unavailable()