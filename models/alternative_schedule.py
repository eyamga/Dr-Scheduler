from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Set
import logging
from collections import defaultdict
import json
from ics import Calendar as IcsCalendar, Event

from models.task import TaskType, TaskDaysParameter, Task

class AlternativeSchedule:
    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        
        # Core scheduling data structures
        self.schedule = defaultdict(list)  # Stores final assignments
        self.scheduling_period = None
        self.task_splits = {}
        self.initial_schedule = None
        
        # Tracking assignments for constraints
        self.physician_assignments = defaultdict(list)  # Track all assignments per physician
        self.physician_calls = defaultdict(list)  # Track call assignments per physician
        self.physician_categories = defaultdict(list)  # Track category assignments per physician
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def set_scheduling_period(self, start_date: date, end_date: date):
        """Set the scheduling period."""
        self.scheduling_period = (start_date, end_date)
        self.logger.info(f"Scheduling period set: {start_date} to {end_date}")

    def set_task_splits(self, task_splits: Dict[str, Dict[str, str]]):
        """Set task split configurations."""
        self.task_splits = task_splits
        self.logger.info(f"Task splits configured: {task_splits}")

    def load_initial_schedule(self, filename: str):
        """Load initial schedule from JSON file."""
        with open(filename, 'r') as f:
            self.initial_schedule = json.load(f)
        self.logger.info(f"Initial schedule loaded from {filename}")

    def _is_physician_available(self, physician: str, period_days: List[date]) -> bool:
        """Check if physician is available for all days in a period."""
        return all(not self.physician_manager.is_unavailable(physician, day) 
                  for day in period_days)

    def _is_physician_eligible(self, physician: str, task: Task) -> bool:
        """Check if physician is eligible for task based on restrictions and exclusions."""
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        return task.category.name not in physician_obj.exclusion_tasks

    def _get_available_physicians(self, task: Task, period_days: List[date]) -> List[str]:
        """Get list of physicians available and eligible for a task in a period."""
        available_physicians = []
        for physician in self.physician_manager.data['physicians']:
            if (self._is_physician_available(physician.name, period_days) and 
                self._is_physician_eligible(physician.name, task)):
                available_physicians.append(physician.name)
        return available_physicians

    def _assign_task(self, task: Task, period: Dict[str, Any], physician: str):
        """Assign a task to a physician and update tracking structures."""
        assignment = {
            'task': task,
            'days': period['days'],
            'start_date': period['days'][0],
            'end_date': period['days'][-1]
        }
        
        self.schedule[physician].append(assignment)
        self.physician_assignments[physician].append(task)
        self.physician_categories[physician].append(task.category.name)
        
        if task.is_call_task:
            self.physician_calls[physician].append(assignment)

        self.logger.info(f"Assigned {task.name} to {physician} for period {period['days'][0]} - {period['days'][-1]}")

    def _handle_linked_tasks(self, main_task: Task, call_task: Task, 
                           main_period: Dict[str, Any], call_period: Dict[str, Any]) -> Optional[str]:
        """Handle assignment of linked main and call tasks."""
        available_physicians = self._get_available_physicians(main_task, 
                                                           main_period['days'] + call_period['days'])
        
        if not available_physicians:
            self.logger.warning(f"No physicians available for linked tasks {main_task.name} and {call_task.name}")
            return None

        # Select physician based on constraints and availability
        selected_physician = self._select_best_physician(available_physicians, main_task)
        
        if selected_physician:
            self._assign_task(main_task, main_period, selected_physician)
            self._assign_task(call_task, call_period, selected_physician)
            
        return selected_physician

    def _select_best_physician(self, available_physicians: List[str], task: Task) -> Optional[str]:
        """Select the best physician for a task based on constraints."""
        best_physician = None
        min_category_count = float('inf')
        
        for physician in available_physicians:
            category_count = self.physician_categories[physician].count(task.category.name)
            
            if category_count < min_category_count:
                min_category_count = category_count
                best_physician = physician
                
        return best_physician

    def _handle_initial_assignments(self, week_start: str, main_period: Dict[str, Any], 
                                  call_period: Dict[str, Any]) -> Set[str]:
        """
        Handle pre-assigned tasks from initial schedule for a given week.
        Returns set of task names that were pre-assigned.
        """
        if not self.initial_schedule:
            return set()

        handled_tasks = set()
        week_start_date = date.fromisoformat(week_start)
        
        for physician, assignments in self.initial_schedule.items():
            for assignment in assignments:
                task_name = assignment['task']
                start_date = date.fromisoformat(assignment['start_date'])
                
                # Check if assignment belongs to current week
                if start_date == week_start_date:
                    task = self.task_manager.get_task(task_name)
                    if not task:
                        self.logger.warning(f"Task {task_name} from initial schedule not found")
                        continue

                    if task.type == TaskType.MAIN:
                        self._assign_task(task, main_period, physician)
                        handled_tasks.add(task_name)
                        
                        # Handle linked call task if exists
                        linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
                        if linked_call:
                            call_task = self.task_manager.get_task(linked_call)
                            self._assign_task(call_task, call_period, physician)
                            handled_tasks.add(linked_call)
                    
                    elif task.type == TaskType.CALL:
                        self._assign_task(task, call_period, physician)
                        handled_tasks.add(task_name)

        return handled_tasks

    def generate_schedule(self, use_initial_schedule: bool = False):
        """Generate the schedule."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        # Get periods from calendar
        periods = self.calendar.determine_periods()
        
        # Process each week's periods
        for week_start, week_periods in sorted(periods.items()):
            if not (self.scheduling_period[0] <= date.fromisoformat(week_start) <= self.scheduling_period[1]):
                continue
                
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if not (main_period and call_period):
                continue

            # Handle pre-assigned tasks if using initial schedule
            pre_assigned_tasks = set()
            if use_initial_schedule and self.initial_schedule:
                pre_assigned_tasks = self._handle_initial_assignments(week_start, main_period, call_period)
                
            # Process remaining tasks for the week
            for task in self.task_manager.data['tasks']:
                # Skip pre-assigned tasks
                if task.name in pre_assigned_tasks:
                    continue
                    
                if task.type == TaskType.MAIN:
                    linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
                    if linked_call and linked_call not in pre_assigned_tasks:
                        call_task = self.task_manager.get_task(linked_call)
                        self._handle_linked_tasks(task, call_task, main_period, call_period)
                    elif not linked_call:
                        available_physicians = self._get_available_physicians(task, main_period['days'])
                        if available_physicians:
                            selected_physician = self._select_best_physician(available_physicians, task)
                            if selected_physician:
                                self._assign_task(task, main_period, selected_physician)

    def print_schedule(self):
        """Print the generated schedule."""
        for physician, tasks in self.schedule.items():
            print(f"\n{physician}:")
            for task in tasks:
                print(f"  {task['task'].name}: {task['start_date']} - {task['end_date']}")

    def save_schedule(self, filename: str):
        """Save schedule to JSON file."""
        serializable_schedule = {
            physician: [
                {**task, 'task': task['task'].name}
                for task in tasks
            ]
            for physician, tasks in self.schedule.items()
        }
        with open(filename, 'w') as f:
            json.dump(serializable_schedule, f, indent=2, default=str)

    def generate_ics_calendar(self, filename: str):
        """Generate ICS calendar file."""
        cal = IcsCalendar()
        for physician, tasks in self.schedule.items():
            for task in tasks:
                event = Event()
                event.name = f"{task['task'].name} - {physician}"
                event.begin = task['start_date'].isoformat()
                event.end = (task['end_date'] + timedelta(days=1)).isoformat()
                event.description = f"Task: {task['task'].name}\nPhysician: {physician}"
                cal.events.add(event)
        with open(filename, 'w') as f:
            f.writelines(cal)
