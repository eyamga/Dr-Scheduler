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
        
        # Add new tracking for assigned call periods
        self.assigned_call_periods = set()  # Track which call periods have been assigned
        
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
        """
        Check if physician is eligible for task based on exclusions only.
        Preferred tasks will be handled in scoring/objective function later.
        """
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        
        # Only check exclusions
        if task.category.name in physician_obj.exclusion_tasks:
            self.logger.debug(f"Physician {physician} has {task.category.name} in exclusion list")
            return False
        
        return True

    def _has_overlapping_assignment(self, physician: str, period: Dict[str, Any]) -> bool:
        """
        Check if physician already has a task assigned during this period.
        """
        period_start = period['days'][0]
        period_end = period['days'][-1]
        
        for assignment in self.schedule[physician]:
            # Check if periods overlap
            if not (assignment['end_date'] < period_start or 
                    assignment['start_date'] > period_end):
                self.logger.debug(
                    f"Physician {physician} already has task {assignment['task'].name} "
                    f"during period {period_start} - {period_end}"
                )
                return True
        return False

    def _has_recent_call(self, physician: str, period_start: date, period_end: date) -> bool:
        """
        Check if physician has had a call within 21 days before or after the given period.
        This is a hard constraint to prevent too frequent call assignments.
        """
        CALL_SPACING_DAYS = 21  # Strict 21-day spacing between calls
        
        for call in self.physician_calls[physician]:
            # Check calls within 21 days before
            days_since_last_call = (period_start - call['end_date']).days
            if days_since_last_call <= CALL_SPACING_DAYS:
                self.logger.debug(
                    f"Physician {physician} has recent call {call['task'].name} "
                    f"ending on {call['end_date']} ({days_since_last_call} days ago)"
                )
                return True
            
            # Check calls within 21 days after
            days_until_next_call = (call['start_date'] - period_end).days
            if days_until_next_call <= CALL_SPACING_DAYS:
                self.logger.debug(
                    f"Physician {physician} has upcoming call {call['task'].name} "
                    f"starting on {call['start_date']} (in {days_until_next_call} days)"
                )
                return True
            
        return False

    def _get_available_physicians(self, task: Task, period_days: List[date]) -> List[str]:
        """Get list of physicians available and eligible for a task in a period."""
        available_physicians = []
        period = {'days': period_days}  # Create period dict for overlap check
        period_start = period_days[0]
        period_end = period_days[-1]
        
        for physician in self.physician_manager.data['physicians']:
            name = physician.name
            
            # First check eligibility (faster check)
            if not self._is_physician_eligible(name, task):
                self.logger.debug(f"Physician {name} not eligible for task {task.name}")
                continue
            
            # Check call spacing constraint for call tasks and multi-week tasks with calls
            if (task.is_call_task or 
                (task.category.days_parameter == TaskDaysParameter.MULTI_WEEK and 
                 self.task_manager.data['linkage_manager'].get_linked_task(task))):
                if self._has_recent_call(name, period_start, period_end):
                    self.logger.debug(
                        f"Physician {name} has another call too close to {period_start}"
                    )
                    continue
            
            # Then check availability and overlapping
            if (self._is_physician_available(name, period_days) and 
                not self._has_overlapping_assignment(name, period)):
                available_physicians.append(name)
            
        if not available_physicians:
            self.logger.warning(
                f"No physicians available for task {task.name}. "
                f"Period: {period_days[0]} - {period_days[-1]}"
            )
            
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

    def _get_linked_main_tasks(self, call_task: Task) -> List[Task]:
        """Get all main tasks linked to a call task."""
        linked_mains = []
        for task in self.task_manager.data['tasks']:
            if (task.type == TaskType.MAIN and 
                self.task_manager.data['linkage_manager'].get_linked_task(task) == call_task.name):
                linked_mains.append(task)
        return linked_mains

    def _get_physicians_doing_linked_mains(self, call_task: Task, week_start: date) -> List[str]:
        """Get all physicians assigned to main tasks linked to this call for the current week."""
        linked_physicians = []
        for physician, assignments in self.schedule.items():
            for assignment in assignments:
                if (assignment['start_date'] == week_start and 
                    self.task_manager.data['linkage_manager'].get_linked_task(assignment['task']) == call_task.name):
                    linked_physicians.append(physician)
        return linked_physicians

    def _handle_linked_tasks(self, main_task: Task, call_task: Task, 
                           main_period: Dict[str, Any], call_period: Dict[str, Any],
                           week_start: date) -> Set[str]:
        """
        Handle assignment of linked main and call tasks.
        Returns set of handled task names.
        """
        handled_tasks = set()
        
        # First assign the main task
        available_for_main = self._get_available_physicians(main_task, main_period['days'])
        if not available_for_main:
            self.logger.warning(f"No physicians available for main task {main_task.name}")
            return handled_tasks

        # Select and assign physician for main task
        main_physician = self._select_best_physician(available_for_main, main_task, main_period['days'][0])
        if main_physician:
            self._assign_task(main_task, main_period, main_physician)
            handled_tasks.add(main_task.name)
            
            # Get all linked main tasks for this call
            linked_mains = self._get_linked_main_tasks(call_task)
            all_main_tasks_assigned = True
            
            # Check if all linked main tasks for this week are already assigned
            for linked_main in linked_mains:
                if not any(a['task'].name == linked_main.name and 
                          a['start_date'] == week_start 
                          for assignments in self.schedule.values() 
                          for a in assignments):
                    all_main_tasks_assigned = False
                    break
            
            # Only handle call task if all linked main tasks are assigned
            if all_main_tasks_assigned:
                # Get all physicians doing linked main tasks this week who don't have overlapping assignments
                linked_physicians = []
                for physician, assignments in self.schedule.items():
                    for assignment in assignments:
                        if (assignment['start_date'] == week_start and 
                            assignment['task'].name in [t.name for t in linked_mains] and
                            not self._has_overlapping_assignment(physician, call_period)):
                            linked_physicians.append(physician)
                
                # Filter for physicians available for call period
                available_for_call = [
                    p for p in linked_physicians 
                    if self._is_physician_available(p, call_period['days'])
                ]
                
                if available_for_call:
                    call_physician = self._select_best_physician(
                        available_for_call, 
                        call_task,
                        call_period['days'][0]
                    )
                    if call_physician:
                        self._assign_task(call_task, call_period, call_physician)
                        handled_tasks.add(call_task.name)
                else:
                    self.logger.warning(
                        f"No physicians doing linked main tasks available for call {call_task.name}"
                    )
    
        return handled_tasks

    def _select_best_physician(self, available_physicians: List[str], task: Task, 
                              period_start: date = None) -> Optional[str]:
        """
        Select the best physician for a task based on constraints.
        
        Args:
            available_physicians: List of available physicians
            task: Task to be assigned
            period_start: Start date of the period for call spacing checks
        """
        best_physician = None
        min_score = float('inf')
        
        for physician in available_physicians:
            score = 0
            
            # Count category assignments
            category_count = self.physician_categories[physician].count(task.category.name)
            score += category_count * 10
            
            if score < min_score:
                min_score = score
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
        
        # First handle main tasks
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

        # Then handle call tasks (either from initial schedule or linked to main tasks)
        for physician, assignments in self.initial_schedule.items():
            for assignment in assignments:
                task_name = assignment['task']
                start_date = date.fromisoformat(assignment['start_date'])
                
                if start_date == week_start_date:
                    task = self.task_manager.get_task(task_name)
                    if task and task.type == TaskType.CALL:
                        if self._is_physician_available(physician, call_period['days']):
                            self._assign_task(task, call_period, physician)
                            handled_tasks.add(task_name)
                        else:
                            self.logger.warning(
                                f"Physician {physician} not available for call task {task_name}"
                            )

        # Handle linked calls for main tasks that were assigned but don't have their calls assigned yet
        for physician, assignments in self.schedule.items():
            for assignment in assignments:
                if (assignment['start_date'] == week_start_date and 
                    assignment['task'].type == TaskType.MAIN):
                    
                    linked_call = self.task_manager.data['linkage_manager'].get_linked_task(assignment['task'])
                    if linked_call and linked_call not in handled_tasks:
                        call_task = self.task_manager.get_task(linked_call)
                        
                        # Try to assign to same physician if available
                        if self._is_physician_available(physician, call_period['days']):
                            self._assign_task(call_task, call_period, physician)
                            handled_tasks.add(linked_call)
                        else:
                            # Find another available physician who did a linked main task
                            linked_mains = self._get_linked_main_tasks(call_task)
                            potential_physicians = []
                            for p, p_assignments in self.schedule.items():
                                for p_assignment in p_assignments:
                                    if (p_assignment['start_date'] == week_start_date and 
                                        p_assignment['task'].name in [t.name for t in linked_mains]):
                                        potential_physicians.append(p)
                            
                            available_physicians = [
                                p for p in potential_physicians 
                                if self._is_physician_available(p, call_period['days'])
                            ]
                            
                            if available_physicians:
                                call_physician = self._select_best_physician(
                                    available_physicians, 
                                    call_task,
                                    call_period['days'][0]
                                )
                                if call_physician:
                                    self._assign_task(call_task, call_period, call_physician)
                                    handled_tasks.add(linked_call)

        return handled_tasks

    def _is_task_start_week(self, task: Task, week_number: int) -> bool:
        """Check if this is a valid starting week for this task based on its offset."""
        return (week_number + task.week_offset) % task.category.number_of_weeks == 0

    def _handle_multi_week_task(self, task: Task, current_week: int, 
                               periods: List[Dict[str, Any]], pre_assigned_tasks: Set[str]) -> Set[str]:
        """
        Handle multi-week task assignment.
        Returns set of handled task names.
        """
        if not self._is_task_start_week(task, current_week):
            return set()

        handled_tasks = set()
        num_weeks = task.category.number_of_weeks
        
        # Get all required periods
        main_periods = []
        call_periods = []
        
        for i in range(num_weeks):
            week_periods = periods[i]
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if not (main_period and call_period):
                self.logger.warning(f"Missing periods for multi-week task {task.name}")
                return set()
            
            main_periods.append(main_period)
            call_periods.append(call_period)

        # Get all days for main periods only
        main_days = []
        for period in main_periods:
            main_days.extend(period['days'])

        # Get available physicians for main periods
        available_physicians = self._get_available_physicians(task, main_days)
        if not available_physicians:
            self.logger.warning(f"No physicians available for multi-week task {task.name}")
            return set()

        # Select best physician for main periods
        selected_physician = self._select_best_physician(available_physicians, task)
        if not selected_physician:
            return set()

        # Assign main tasks for all weeks
        for i, main_period in enumerate(main_periods):
            self._assign_task(task, main_period, selected_physician)
            handled_tasks.add(task.name)
            instance_key = f"{task.name}_{main_period['days'][0]}"
            handled_tasks.add(instance_key)

        # Handle linked call task if exists
        linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
        if linked_call and linked_call not in pre_assigned_tasks:
            call_task = self.task_manager.get_task(linked_call)
            
            # Create unique identifier for this multi-week task's call period
            multi_week_call_key = f"{call_task.name}_{main_periods[0]['days'][0]}_{main_periods[-1]['days'][-1]}"
            
            # Only proceed if this multi-week task's call hasn't been assigned yet
            if multi_week_call_key not in self.assigned_call_periods:
                # Choose call period (between weeks for 2-week tasks)
                call_period = call_periods[0]  # Weekend between weeks for 2-week tasks
                
                # Try to assign call to same physician if available
                if self._is_physician_available(selected_physician, call_period['days']):
                    self._assign_task(call_task, call_period, selected_physician)
                    self.assigned_call_periods.add(multi_week_call_key)
                    handled_tasks.add(call_task.name)
                    # Mark all potential call periods as handled
                    for other_call_period in call_periods:
                        instance_key = f"{call_task.name}_{other_call_period['days'][0]}"
                        handled_tasks.add(instance_key)
                else:
                    # Try to find another physician for the call
                    available_for_call = self._get_available_physicians(call_task, call_period['days'])
                    if available_for_call:
                        call_physician = self._select_best_physician(available_for_call, call_task)
                        if call_physician:
                            self._assign_task(call_task, call_period, call_physician)
                            self.assigned_call_periods.add(multi_week_call_key)
                            handled_tasks.add(call_task.name)
                            # Mark all potential call periods as handled
                            for other_call_period in call_periods:
                                instance_key = f"{call_task.name}_{other_call_period['days'][0]}"
                                handled_tasks.add(instance_key)

        return handled_tasks

    def generate_schedule(self, use_initial_schedule: bool = False):
        """Generate the schedule."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        # Get periods from calendar
        periods = self.calendar.determine_periods()
        period_items = sorted(periods.items())
        
        # Process each week's periods
        for week_number, (week_start, week_periods) in enumerate(period_items):
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
            
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if not (main_period and call_period):
                continue

            # Handle pre-assigned tasks
            pre_assigned_tasks = set()
            if use_initial_schedule and self.initial_schedule:
                pre_assigned_tasks = self._handle_initial_assignments(week_start, main_period, call_period)
            
            # First handle multi-week tasks
            for task in self.task_manager.data['tasks']:
                if task.name in pre_assigned_tasks or task.type != TaskType.MAIN:
                    continue
                    
                if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK:
                    # Check if we have enough weeks remaining
                    remaining_weeks = period_items[week_number:week_number + task.category.number_of_weeks]
                    if len(remaining_weeks) >= task.category.number_of_weeks:
                        handled_tasks = self._handle_multi_week_task(
                            task, 
                            week_number,
                            [periods[week] for week, _ in remaining_weeks],
                            pre_assigned_tasks
                        )
                        pre_assigned_tasks.update(handled_tasks)
            
            # Then handle single-week tasks without linked calls
            for task in self.task_manager.data['tasks']:
                if (task.name in pre_assigned_tasks or 
                    task.type != TaskType.MAIN or 
                    task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                    continue
                    
                if not self.task_manager.data['linkage_manager'].get_linked_task(task):
                    available_physicians = self._get_available_physicians(task, main_period['days'])
                    if available_physicians:
                        selected_physician = self._select_best_physician(available_physicians, task)
                        if selected_physician:
                            self._assign_task(task, main_period, selected_physician)
                            pre_assigned_tasks.add(task.name)
            
            # Finally handle single-week tasks with linked calls
            for task in self.task_manager.data['tasks']:
                if (task.name in pre_assigned_tasks or 
                    task.type != TaskType.MAIN or 
                    task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                    continue
                    
                linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
                if linked_call and linked_call not in pre_assigned_tasks:
                    call_task = self.task_manager.get_task(linked_call)
                    handled_tasks = self._handle_linked_tasks(
                        task, call_task, main_period, call_period, week_start_date
                    )
                    pre_assigned_tasks.update(handled_tasks)

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
