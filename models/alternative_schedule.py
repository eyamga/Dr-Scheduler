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
        self.schedule = defaultdict(list)
        self.scheduling_period = None
        self.initial_schedule = None
        
        # For tracking assignments
        self.physician_assignments = defaultdict(list)
        self.physician_calls = defaultdict(list)
        self.physician_categories = defaultdict(list)
        
        # For tracking unassigned tasks
        self.unassigned_tasks = defaultdict(list)
        
        self.logger = logging.getLogger(__name__)

    def set_scheduling_period(self, start_date: date, end_date: date):
        """Set the scheduling period."""
        self.scheduling_period = (start_date, end_date)
        self.logger.info(f"Scheduling period set: {start_date} to {end_date}")

    def load_initial_schedule(self, filename: str):
        """Load initial schedule from JSON file."""
        with open(filename, 'r') as f:
            self.initial_schedule = json.load(f)
        self.logger.info(f"Initial schedule loaded from {filename}")

    def _is_physician_eligible(self, physician: str, task: Task) -> bool:
        """Check if physician is eligible based on exclusions only."""
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        if task.category.name in physician_obj.exclusion_tasks:
            self.logger.debug(f"Physician {physician} has {task.category.name} in exclusion list")
            return False
        return True

    def _get_valid_physicians(self, task: Task, period_start: date, 
                            main_period: Dict[str, Any], call_period: Dict[str, Any]) -> List[str]:
        """Get list of valid physicians for a task."""
        valid_physicians = []
        for physician in self.physician_manager.data['physicians']:
            name = physician.name
            if not self._is_physician_eligible(name, task):
                continue
                
            period_days = main_period['days']
            if not all(not self.physician_manager.is_unavailable(name, day) for day in period_days):
                continue
                
            if task.is_call_task:
                if self._has_recent_call(name, period_start, period_start):
                    continue
                    
            valid_physicians.append(name)
            
        return valid_physicians

    def _has_recent_call(self, physician: str, period_start: date, period_end: date) -> bool:
        """Check if physician has had a call within 21 days."""
        CALL_SPACING_DAYS = 21
        for call in self.physician_calls[physician]:
            if abs((period_start - call['end_date']).days) <= CALL_SPACING_DAYS:
                return True
        return False

    def _try_multi_week_assignment(self, assignments: List, task: Task, physician: str, 
                                 current_period_idx: int, periods: List) -> bool:
        """Try to assign all weeks of a multi-week task."""
        num_weeks = task.category.number_of_weeks
        if current_period_idx + num_weeks > len(periods):
            return False
            
        # Check availability for all weeks
        for i in range(num_weeks):
            period_start, main_period, _ = periods[current_period_idx + i]
            if not self._is_valid_assignment(task, physician, period_start, 
                                           period_start + timedelta(days=len(main_period['days'])-1)):
                return False
                
        return True

    def _try_call_assignment(self, assignments: List, call_task: Task, physician: str,
                           current_period_idx: int, periods: List) -> bool:
        """Try to assign a call task."""
        _, _, call_period = periods[current_period_idx]
        period_start = call_period['days'][0]
        period_end = call_period['days'][-1]
        
        return self._is_valid_assignment(call_task, physician, period_start, period_end)

    def _build_schedule(self, assignments: List):
        """Build final schedule from assignments."""
        for task, physician, start_date in assignments:
            self._add_to_schedule(task, physician, start_date)

    def _add_to_schedule(self, task: Task, physician: str, start_date: date):
        """Add an assignment to the schedule."""
        self.schedule[physician].append({
            'task': task,
            'start_date': start_date,
            'end_date': start_date + timedelta(days=4)  # Assuming 5-day periods
        })

    def generate_schedule(self, use_initial_schedule: bool = False):
        """Generate schedule using backtracking search."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")
            
        # Get all periods that need assignments
        periods = self._get_assignment_periods()
        
        # Get tasks sorted by priority
        tasks = self._get_tasks_by_priority()
        
        # Handle initial schedule if provided
        if use_initial_schedule and self.initial_schedule:
            self._handle_initial_assignments()
            
        # Start backtracking search
        final_assignments = self._backtrack([], tasks, periods, 0)
        
        if final_assignments:
            self._build_schedule(final_assignments)
        else:
            self.logger.error("Could not find valid schedule")

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

    def save_unassigned_tasks(self, filename: str):
        """Save unassigned tasks to JSON file."""
        if not self.unassigned_tasks:
            self.logger.info("All tasks were successfully assigned")
            return
            
        with open(filename, 'w') as f:
            json.dump(
                {
                    'unassigned_tasks': dict(self.unassigned_tasks),
                    'summary': {
                        'total_unassigned': sum(len(tasks) for tasks in self.unassigned_tasks.values()),
                        'weeks_with_unassigned': len(self.unassigned_tasks),
                        'categories_affected': list(set(
                            task['category'] 
                            for tasks in self.unassigned_tasks.values() 
                            for task in tasks
                        ))
                    }
                }, 
                f, 
                indent=2
            )

    def _get_assignment_periods(self):
        """Get all periods that need assignments."""
        periods = self.calendar.determine_periods()
        assignment_periods = []
        
        for week_start, week_periods in sorted(periods.items()):
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
            
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if main_period and call_period:
                assignment_periods.append((week_start_date, main_period, call_period))
            
        return assignment_periods

    def _get_tasks_by_priority(self):
        """Sort tasks by priority for assignment."""
        tasks = []
        
        # First priority: Multi-week tasks
        multi_week = []
        for task in self.task_manager.data['tasks']:
            if (task.type == TaskType.MAIN and 
                task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                multi_week.append(task)
        
        # Second priority: Tasks with linked calls
        linked = []
        for task in self.task_manager.data['tasks']:
            if (task.type == TaskType.MAIN and 
                task not in multi_week and
                self.task_manager.data['linkage_manager'].get_linked_task(task)):
                linked.append(task)
        
        # Third priority: Other tasks
        other = []
        for task in self.task_manager.data['tasks']:
            if task.type == TaskType.MAIN and task not in multi_week and task not in linked:
                other.append(task)
        
        return multi_week + linked + other

    def _is_valid_assignment(self, task: Task, physician: str, period_start: date, period_end: date) -> bool:
        """Check if assignment is valid according to all constraints."""
        # Check eligibility
        if not self._is_physician_eligible(physician, task):
            return False
        
        # Check availability
        period_days = [period_start + timedelta(days=i) 
                      for i in range((period_end - period_start).days + 1)]
        if not all(not self.physician_manager.is_unavailable(physician, day) 
                  for day in period_days):
            return False
        
        # Check overlapping assignments
        for assignment in self.schedule[physician]:
            if not (assignment['end_date'] < period_start or 
                    assignment['start_date'] > period_end):
                return False
        
        # Check call spacing if this is a call task
        if task.is_call_task:
            if self._has_recent_call(physician, period_start, period_end):
                return False
        
        return True

    def _handle_initial_assignments(self):
        """Handle pre-assigned tasks from initial schedule."""
        if not self.initial_schedule:
            return
        
        for physician, assignments in self.initial_schedule.items():
            for assignment in assignments:
                task_name = assignment['task']
                start_date = date.fromisoformat(assignment['start_date'])
                end_date = date.fromisoformat(assignment['end_date'])
                
                task = self.task_manager.get_task(task_name)
                if not task:
                    self.logger.warning(f"Task {task_name} from initial schedule not found")
                    continue
                
                if self._is_valid_assignment(task, physician, start_date, end_date):
                    self._add_to_schedule(task, physician, start_date)
                else:
                    self.logger.warning(
                        f"Invalid initial assignment: {task_name} to {physician} "
                        f"from {start_date} to {end_date}"
                    )

    def _backtrack(self, assignments: List, remaining_tasks: List, 
                  periods: List, current_period_idx: int) -> Optional[List]:
        """
        Main backtracking function.
        
        Args:
            assignments: Current partial schedule
            remaining_tasks: Tasks still to be assigned
            periods: All periods that need assignments
            current_period_idx: Current period being processed
        """
        # Base case: all tasks assigned
        if not remaining_tasks:
            return assignments
        
        if current_period_idx >= len(periods):
            return None
        
        current_task = remaining_tasks[0]
        period_start, main_period, call_period = periods[current_period_idx]
        
        # Skip if this isn't a valid starting week for this task
        if (current_task.category.days_parameter == TaskDaysParameter.MULTI_WEEK and 
            (current_period_idx + current_task.week_offset) % current_task.category.number_of_weeks != 0):
            return self._backtrack(assignments, remaining_tasks, periods, current_period_idx + 1)
        
        # Get valid physicians for this task
        valid_physicians = self._get_valid_physicians(
            current_task, period_start, main_period, call_period
        )
        
        for physician in valid_physicians:
            # Try this assignment
            new_assignments = assignments.copy()
            new_assignments.append((current_task, physician, period_start))
            
            # If this is a multi-week task, ensure we can assign all weeks
            if current_task.category.days_parameter == TaskDaysParameter.MULTI_WEEK:
                if not self._try_multi_week_assignment(
                    new_assignments, current_task, physician, current_period_idx, periods
                ):
                    continue
            
            # Try to assign linked call if exists
            linked_call = self.task_manager.data['linkage_manager'].get_linked_task(current_task)
            if linked_call:
                call_task = self.task_manager.get_task(linked_call)
                if not self._try_call_assignment(
                    new_assignments, call_task, physician, current_period_idx, periods
                ):
                    continue
            
            # Recursive call with remaining tasks
            result = self._backtrack(
                new_assignments, remaining_tasks[1:], periods, current_period_idx + 1
            )
            if result is not None:
                return result
            
        # If we get here, no valid assignment was found
        self._track_unassigned_task(current_task, period_start)
        return None

    def _track_unassigned_task(self, task: Task, period_start: date):
        """Track tasks that couldn't be assigned."""
        self.unassigned_tasks[period_start.isoformat()].append({
            'task': task.name,
            'category': task.category.name,
            'type': 'MAIN' if task.type == TaskType.MAIN else 'CALL',
            'reason': "No available physicians"
        })
