import datetime
from datetime import date, timedelta
from typing import Dict, List, Any, Tuple, Optional
from collections import defaultdict
import json
from models.task import TaskType, TaskDaysParameter, Task
import logging
from ics import Calendar as IcsCalendar, Event
import random
from operator import attrgetter

logging.basicConfig(level=logging.DEBUG)

class OptimizedSchedule:
    """
    A new scheduler class implementing the scheduling algorithm as specified.
    """

    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        self.scheduling_period = None
        self.schedule = defaultdict(list)
        self.initial_schedule = {}
        self.task_splits = {}
        self.periods = {}
        self.tasks_by_period = {}
        self.all_physicians = self.physician_manager.data['physicians']
        self.physicians_by_discontinuity = {
            True: [p for p in self.all_physicians if p.discontinuity_preference],
            False: [p for p in self.all_physicians if not p.discontinuity_preference]
        }
    
    def set_scheduling_period(self, start_date: date, end_date: date):
        self.scheduling_period = (start_date, end_date)
        logging.debug(f"Scheduling period set to {self.scheduling_period}")

    def set_task_splits(self, task_splits: Dict[str, Dict[str, Optional[str]]]):
        self.task_splits = task_splits
        logging.debug(f"Task splits set to {self.task_splits}")

    def set_off_days(self, off_days: Dict[str, List[date]]):
        self.off_days = off_days
        logging.debug(f"Off days set to {self.off_days}")

    def load_schedule(self, filename: str):
        with open(filename, 'r') as f:
            loaded_schedule = json.load(f)
        self.initial_schedule = defaultdict(list, {
            k: [
                {
                    **t,
                    'start_date': date.fromisoformat(t['start_date']),
                    'end_date': date.fromisoformat(t['end_date']),
                    'task': self.task_manager.get_task(t['task'])
                }
                for t in v
            ]
            for k, v in loaded_schedule.items()
        })
        logging.debug(f"Initial schedule loaded from {filename}")

    def generate_schedule(self):
        """
        Generate a schedule given all the instance information.
        """
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        logging.info("Starting schedule generation...")
        self.periods = self.calendar.determine_periods()
        relevant_periods = self._filter_relevant_periods(self.periods, self.scheduling_period[0], self.scheduling_period[1])
        self.tasks_by_period = self._prepare_tasks_by_period(relevant_periods)
        self._apply_initial_schedule()
        self._assign_remaining_tasks()
        logging.info("Schedule generation completed")

    def _filter_relevant_periods(self, periods: Dict[str, List[Dict[str, Any]]], start_date: date, end_date: date) -> Dict[str, List[Dict[str, Any]]]:
        return {
            week_start: week_periods
            for week_start, week_periods in periods.items()
            if start_date <= date.fromisoformat(week_start) <= end_date
        }

    def _prepare_tasks_by_period(self, periods: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
        tasks_by_period = defaultdict(list)
        for week_start, week_periods in periods.items():
            for period in week_periods:
                if not period.get('days'):  # Check if days is empty or None
                    logging.warning(f"Period {period} has no days defined")
                    continue
                    
                tasks_by_period[week_start].append({
                    'type': period['type'],
                    'days': period['days'],
                    'tasks': []
                })

        # Assign tasks to periods based on their scheduling rules
        for task in self.task_manager.data['tasks']:
            scheduling_weeks = self._get_scheduling_weeks_for_task(task, periods)
            for week_start in scheduling_weeks:
                for period in tasks_by_period[week_start]:
                    if period['type'] == ('MAIN' if task.type == TaskType.MAIN else 'CALL'):
                        # Handle task splitting
                        split_periods = self._split_task_if_needed(task, period)
                        if split_periods:  # Check if split_periods is not empty
                            period['tasks'].extend(split_periods)
        return tasks_by_period

    def _get_scheduling_weeks_for_task(self, task: Task, periods: Dict[str, List[Dict[str, Any]]]) -> List[str]:
        week_starts = sorted(periods.keys())
        scheduling_weeks = []
        week_offset = task.week_offset
        number_of_weeks = task.category.number_of_weeks

        # For multi-week tasks, schedule them starting at the appropriate weeks
        if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK:
            for i, week_start in enumerate(week_starts):
                if (i + week_offset) % number_of_weeks == 0:
                    # Ensure we have enough weeks ahead
                    if i + number_of_weeks <= len(week_starts):
                        scheduling_weeks.append(week_start)
        else:
            # For single-week tasks, schedule them every week or according to their offset
            for i, week_start in enumerate(week_starts):
                if (i + week_offset) % number_of_weeks == 0:
                    scheduling_weeks.append(week_start)

        return scheduling_weeks

    def _split_task_if_needed(self, task: Task, period: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Handle task splitting according to discontinuity preferences and task_splits.
        Returns a list of task assignments to be added to the period's tasks.
        """
        if not period.get('days'):  # Check if days is empty or None
            logging.warning(f"Period has no days defined for task {task.name}")
            return []
        
        task_assignments = []
        # Check if task is linked by checking if it appears in any linkage
        linked = any(task.name in linked_tasks for linked_tasks in self.task_manager.data['linkage_manager'].to_dict().values())

        split_info = self.task_splits.get(task.category.name, {})
        split_pattern = split_info.get('linked' if linked else 'unlinked')

        if split_pattern:
            # Task should be split
            split_days = self._parse_split_pattern(split_pattern, period['days'])
            for split_days_range in split_days:
                if split_days_range:  # Check if split_days_range is not empty
                    task_assignments.append({
                        'task': task,
                        'days': split_days_range
                    })
        else:
            # Task is not split
            task_assignments.append({
                'task': task,
                'days': period['days']
            })
        return task_assignments

    def _parse_split_pattern(self, pattern: str, days: List[date]) -> List[List[date]]:
        """
        Parse the split pattern and divide the days accordingly.
        """
        if not days:  # Check if days is empty
            return []
        
        split_parts = pattern.split(':')
        split_lengths = [int(part) for part in split_parts]
        total_length = sum(split_lengths)
        
        if total_length > len(days):  # Check if split pattern is valid for days length
            logging.warning(f"Split pattern {pattern} requires {total_length} days but only {len(days)} days available")
            return [days]  # Return all days as single period if split is invalid
        
        split_days = []
        start_index = 0
        for length in split_lengths:
            if start_index < len(days):  # Check if we still have days to split
                end_index = min(start_index + length, len(days))
                split_days.append(days[start_index:end_index])
                start_index = end_index
        return split_days

    def _apply_initial_schedule(self):
        """
        Apply initial schedule assignments.
        """
        for physician, tasks in self.initial_schedule.items():
            for task_info in tasks:
                task = task_info['task']
                start_date = task_info['start_date']
                end_date = task_info['end_date']

                # Assign task to physician
                self.schedule[physician].append({
                    'task': task,
                    'days': [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)],
                    'start_date': start_date,
                    'end_date': end_date,
                    'score': 0  # Initial score is 0; will be updated later
                })
                
                logging.debug(f"Assigned initial task {task.name} to {physician} from {start_date} to {end_date}")

    def _assign_remaining_tasks(self):
        """
        Assign remaining tasks to physicians, following the scheduling rules.
        """
        # Prepare task lists
        unassigned_tasks = []
        for week_start, periods in self.tasks_by_period.items():
            for period in periods:
                for task_info in period['tasks']:
                    task = task_info['task']
                    days = task_info['days']
                    if not self._is_task_assigned(task, days):
                        unassigned_tasks.append({'task': task, 'days': days, 'period': period, 'week_start': week_start})

        # Assign multi-week tasks first
        multi_week_tasks = [item for item in unassigned_tasks if item['task'].category.days_parameter == TaskDaysParameter.MULTI_WEEK]
        single_week_tasks = [item for item in unassigned_tasks if item['task'].category.days_parameter != TaskDaysParameter.MULTI_WEEK]

        # Assign multi-week tasks
        for item in multi_week_tasks:
            self._assign_multi_week_task(item)

        # Assign remaining tasks
        for item in single_week_tasks:
            self._assign_single_week_task(item)

    def _assign_multi_week_task(self, item: Dict[str, Any]):
        """
        Assign multi-week tasks ensuring the same physician is assigned for consecutive periods.
        """
        task = item['task']
        days = item['days']
        week_start = item['week_start']

        # Gather all periods for the multi-week task
        number_of_weeks = task.category.number_of_weeks
        week_starts = sorted(self.tasks_by_period.keys())
        try:
            start_index = week_starts.index(week_start)
        except ValueError:
            logging.warning(f"Week start {week_start} not found in week_starts")
            return

        task_periods = []
        for i in range(number_of_weeks):
            try:
                current_week = week_starts[start_index + i]
            except IndexError:
                logging.warning(f"Not enough weeks to schedule multi-week task {task.name} starting at {week_start}")
                return
            for period in self.tasks_by_period[current_week]:
                if any(t['task'].name == task.name for t in period['tasks']):
                    task_info = next(t for t in period['tasks'] if t['task'].name == task.name)
                    task_periods.append(task_info)
                    break  # Avoid duplicates

        # Get the combined days
        combined_days = [day for tp in task_periods for day in tp['days']]
        # Find eligible physicians
        eligible_physicians = self._get_eligible_physicians(task, combined_days, self.all_physicians)
        if not eligible_physicians:
            logging.warning(f"No eligible physicians found for multi-week task {task.name} starting at {week_start}")
            return
        # Assign task to physician
        assigned_physician = self._select_physician_for_task(task, combined_days, eligible_physicians, multi_week=True)
        if assigned_physician:
            for tp in task_periods:
                self.schedule[assigned_physician.name].append({
                    'task': task,
                    'days': tp['days'],
                    'start_date': tp['days'][0],
                    'end_date': tp['days'][-1],
                    'score': 0  # Score will be calculated later
                })
                logging.debug(f"Assigned multi-week task {task.name} to {assigned_physician.name} for period starting {tp['days'][0]}")
            # Assign linked call tasks if any
            self._assign_linked_call_task(task, assigned_physician)
        else:
            logging.warning(f"Could not assign multi-week task {task.name} starting at {week_start}")

    def _assign_single_week_task(self, item: Dict[str, Any]):
        task = item['task']
        days = item['days']
        week_start = item['week_start']

        # Find eligible physicians
        eligible_physicians = self._get_eligible_physicians(task, days, self.all_physicians)
        if not eligible_physicians:
            logging.warning(f"No eligible physicians found for task {task.name} during week starting {week_start}")
            return

        # Handle task splitting and discontinuity preference
        discontinuity_physicians = self.physicians_by_discontinuity[True]
        continuity_physicians = self.physicians_by_discontinuity[False]

        if len(days) < 5:
            # Short tasks, assign to one physician
            assigned_physician = self._select_physician_for_task(task, days, eligible_physicians)
            if assigned_physician:
                self._assign_task_to_physician(task, days, assigned_physician)
                # Assign linked call tasks if any
                self._assign_linked_call_task(task, assigned_physician)
            else:
                logging.warning(f"Could not assign task {task.name} during week starting {week_start}")
        else:
            # Longer tasks, check for splitting
            split_info = self.task_splits.get(task.category.name, {})
            # Check if task is linked by checking if it appears in any linkage
            linked = any(task.name in linked_tasks for linked_tasks in self.task_manager.data['linkage_manager'].to_dict().values())
            split_pattern = split_info.get('linked' if linked else 'unlinked')
            
            if split_pattern:
                # Split task among physicians with discontinuity preference
                split_days_list = self._parse_split_pattern(split_pattern, days)
                if len(discontinuity_physicians) >= len(split_days_list):
                    for split_days in split_days_list:
                        eligible_physicians_split = [p for p in discontinuity_physicians if p in eligible_physicians]
                        assigned_physician = self._select_physician_for_task(task, split_days, eligible_physicians_split)
                        if assigned_physician:
                            self._assign_task_to_physician(task, split_days, assigned_physician)
                            if linked:
                                # For linked tasks, assign linked call task proportionally
                                self._assign_linked_call_task(task, assigned_physician, split_days)
                            discontinuity_physicians.remove(assigned_physician)
                        else:
                            logging.warning(f"Could not assign split task {task.name} during days {split_days[0]} to {split_days[-1]}")
                else:
                    # Not enough physicians with discontinuity preference, assign to one physician
                    assigned_physician = self._select_physician_for_task(task, days, eligible_physicians)
                    if assigned_physician:
                        self._assign_task_to_physician(task, days, assigned_physician)
                        # Assign linked call tasks if any
                        self._assign_linked_call_task(task, assigned_physician)
                    else:
                        logging.warning(f"Could not assign task {task.name} during week starting {week_start}")
            else:
                # No splitting, assign to one physician
                assigned_physician = self._select_physician_for_task(task, days, eligible_physicians)
                if assigned_physician:
                    self._assign_task_to_physician(task, days, assigned_physician)
                    # Assign linked call tasks if any
                    self._assign_linked_call_task(task, assigned_physician)
                else:
                    logging.warning(f"Could not assign task {task.name} during week starting {week_start}")

    def _assign_linked_call_task(self, task: Task, physician: Any, task_days: Optional[List[date]] = None):
        """
        Assign linked call task to the physician who did the main task.
        """
        # Get the linked call task from the linkage manager
        linked_call_task_name = None
        for main_task, call_task in self.task_manager.data['linkage_manager'].to_dict().items():
            if main_task == task.name:
                linked_call_task_name = call_task
                break

        if linked_call_task_name:
            linked_call_task = self.task_manager.get_task(linked_call_task_name)
            if not linked_call_task:
                logging.warning(f"Linked call task {linked_call_task_name} for main task {task.name} not found.")
                return
            # Find the period for the call task
            for week_start, periods in self.tasks_by_period.items():
                for period in periods:
                    if period['type'] == 'CALL':
                        for task_info in period['tasks']:
                            if task_info['task'].name == linked_call_task_name and not self._is_task_assigned(linked_call_task, task_info['days']):
                                # Assign call task to the physician
                                if not self._is_physician_unavailable(physician.name, task_info['days']):
                                    self.schedule[physician.name].append({
                                        'task': linked_call_task,
                                        'days': task_info['days'],
                                        'start_date': task_info['days'][0],
                                        'end_date': task_info['days'][-1],
                                        'score': 0
                                    })
                                    logging.debug(f"Assigned linked call task {linked_call_task_name} to {physician.name} for period starting {task_info['days'][0]}")
                                    return
                                else:
                                    logging.warning(f"Physician {physician.name} is unavailable for linked call task {linked_call_task_name}")
            logging.warning(f"Could not assign linked call task {linked_call_task_name} for main task {task.name}")

    def _assign_task_to_physician(self, task: Task, days: List[date], physician: Any):
        self.schedule[physician.name].append({
            'task': task,
            'days': days,
            'start_date': days[0],
            'end_date': days[-1],
            'score': 0  # Score will be calculated later
        })
        logging.debug(f"Assigned task {task.name} to {physician.name} during days {days[0]} to {days[-1]}")

    def _is_task_assigned(self, task: Task, days: List[date]) -> bool:
        """
        Check if a task has already been assigned during the specified days.
        """
        if not days:  # Check if days list is empty
            logging.warning(f"Empty days list for task {task.name}")
            return False
        
        for physician_tasks in self.schedule.values():
            for scheduled_task in physician_tasks:
                if scheduled_task['task'].name == task.name and scheduled_task['days'] and scheduled_task['start_date'] == days[0]:
                    return True
        return False

    def _get_eligible_physicians(self, task: Task, days: List[date], physicians: List[Any]) -> List[Any]:
        """
        Return a list of physicians eligible to perform the task during the given days.
        """
        eligible_physicians = []
        for physician in physicians:
            if not self._is_physician_unavailable(physician.name, days) and \
               task.category.name not in physician.exclusion_tasks and \
               (not task.category.restricted or task.category.name in physician.preferred_tasks):
                eligible_physicians.append(physician)
        return eligible_physicians

    def _is_physician_unavailable(self, physician_name: str, days: List[date]) -> bool:
        """
        Return True if the physician is unavailable on any of the given days.
        """
        return any(self.physician_manager.is_unavailable(physician_name, day) for day in days)

    def _select_physician_for_task(self, task: Task, days: List[date], physicians: List[Any], multi_week=False) -> Optional[Any]:
        """
        Select the best physician to assign the task to, based on preferences and diversification.
        """
        physician_scores = []
        total_weeks = self._calculate_total_weeks()
        max_calls_per_month = total_weeks / 4  # Max one call per month

        for physician in physicians:
            score = 0
            # Check if the task is among the physician's preferred tasks
            if task.category.name in physician.preferred_tasks:
                preference_rank = physician.preferred_tasks.index(task.category.name)
                score += (len(physician.preferred_tasks) - preference_rank) * 10
            else:
                score -= 10  # Penalty for unpreferred tasks
            # Diversify task categories
            assigned_categories = {t['task'].category.name for t in self.schedule[physician.name]}
            if task.category.name in assigned_categories:
                score -= 20  # Penalty for assigning same category again
            # Check desired working percentage
            assigned_weeks = self._calculate_physician_assigned_weeks(physician.name)
            desired_weeks = physician.desired_working_weeks * total_weeks
            if assigned_weeks < desired_weeks:
                score += 5  # Encourage assigning to meet desired working weeks
            else:
                score -= 15  # Penalty if exceeding desired working weeks
            # Check call distribution
            if task.type == TaskType.CALL:
                assigned_calls = self._calculate_physician_assigned_calls(physician.name)
                if assigned_calls >= max_calls_per_month:
                    score -= 50  # Penalty for exceeding call assignments
            # Ensure no more than one call per month
            if task.type == TaskType.CALL and self._has_recent_call(physician.name, days):
                score -= 40  # Penalty for recent calls
            # Check for consecutive heavy tasks
            last_task = self._get_last_assigned_task(physician.name)
            if last_task and last_task['task'].heaviness >= 4 and task.heaviness >=4:
                score -= 10  # Penalty for consecutive heavy tasks
            # Add revenue balancing (simplified)
            score += task.category.weekday_revenue * len(days) / 1000  # Normalize revenue

            physician_scores.append({'physician': physician, 'score': score})

        # Sort physicians by score
        physician_scores.sort(key=lambda x: x['score'], reverse=True)
        if physician_scores:
            return physician_scores[0]['physician']
        else:
            return None

    def _calculate_total_weeks(self) -> int:
        start_date, end_date = self.scheduling_period
        return ((end_date - start_date).days + 1) // 7

    def _calculate_physician_assigned_weeks(self, physician_name: str) -> int:
        assigned_days = set()
        for task in self.schedule[physician_name]:
            assigned_days.update(task['days'])
        return len(assigned_days) // 7

    def _calculate_physician_assigned_calls(self, physician_name: str) -> int:
        return sum(1 for task in self.schedule[physician_name] if task['task'].type == TaskType.CALL)

    def _has_recent_call(self, physician_name: str, days: List[date]) -> bool:
        """
        Check if the physician had a call task within the last 28 days.
        """
        for task in self.schedule[physician_name]:
            if task['task'].type == TaskType.CALL:
                if abs((task['start_date'] - days[0]).days) <= 28:
                    return True
        return False

    def _get_last_assigned_task(self, physician_name: str) -> Optional[Dict[str, Any]]:
        tasks = self.schedule[physician_name]
        if tasks:
            return tasks[-1]
        else:
            return None

    def get_schedule(self) -> Dict[str, List[Dict[str, Any]]]:
        return dict(self.schedule)

    def print_schedule(self):
        for physician, tasks in self.schedule.items():
            print(f"\n{physician}:")
            for task in tasks:
                print(f"  {task['task'].name}: {task['start_date']} - {task['end_date']} (Score: {task['score']})")

    def save_schedule(self, filename):
        serializable_schedule = {
            physician: [
                {
                    **task,
                    'task': task['task'].name,
                    'days': [day.isoformat() for day in task['days']],
                    'start_date': task['start_date'].isoformat(),
                    'end_date': task['end_date'].isoformat()
                }
                for task in tasks
            ]
            for physician, tasks in self.schedule.items()
        }
        with open(filename, 'w') as f:
            json.dump(serializable_schedule, f, indent=2)

    def generate_ics_calendar(self, filename):
        cal = IcsCalendar()
        for physician, tasks in self.schedule.items():
            for task in tasks:
                event = Event()
                event.name = f"{task['task'].name} - {physician}"
                event.begin = task['start_date'].isoformat()
                event.end = (task['end_date'] + timedelta(days=1)).isoformat()
                event.description = f"Task: {task['task'].name}\nPhysician: {physician}\nScore: {task['score']}"
                cal.events.add(event)
        with open(filename, 'w') as f:
            f.writelines(cal) 