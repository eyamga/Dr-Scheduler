from typing import List, Dict, Any, Optional, Set
from collections import defaultdict
import logging
from datetime import date, timedelta
import json
from ics import Calendar as IcsCalendar, Event
from models.task import TaskType, TaskDaysParameter, Task
from models.constraints import (
    AvailabilityConstraint, ExclusionConstraint, 
    OverlapConstraint, CallSpacingConstraint, 
    MultiWeekContinuityConstraint
)

class ModularScheduler:
    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        
        # Core scheduling data
        self.schedule = defaultdict(list)
        self.scheduling_period = None
        self.initial_schedule = None
        
        # Assignment tracking
        self.physician_assignments = defaultdict(list)
        self.physician_calls = defaultdict(list)
        self.physician_categories = defaultdict(list)
        self.assigned_call_periods = set()
        self.unassigned_tasks = defaultdict(list)
        
        # Constraints
        self.constraints = [
            AvailabilityConstraint(),
            ExclusionConstraint(),
            OverlapConstraint(),
            CallSpacingConstraint(),
            MultiWeekContinuityConstraint()
        ]
        
        self.logger = logging.getLogger(__name__)

    def check_constraints(self, assignment: Dict[str, Any]) -> bool:
        """Check if assignment satisfies all constraints."""
        return all(constraint.check(assignment, self) for constraint in self.constraints)

    def _assign_task(self, task, period, physician):
        """Assign task and update tracking structures."""
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

    def _get_available_physicians(self, task, period_days) -> List[str]:
        """Get physicians that satisfy all constraints for this assignment."""
        available_physicians = []
        period = {'days': period_days}
        period_start = period_days[0]
        period_end = period_days[-1]
        
        for physician in self.physician_manager.data['physicians']:
            name = physician.name
            
            # Check exclusions first (faster)
            if not self._is_physician_eligible(name, task):
                continue
            
            # Check availability
            if not self._is_physician_available(name, period_days):
                continue
            
            # Check overlapping assignments
            if self._has_overlapping_assignment(name, period):
                continue
            
            # Check call spacing only for call tasks
            if task.is_call_task:
                if any(constraint.__class__.__name__ == 'CallSpacingConstraint' 
                      and not constraint.check({'task': task, 'period': period, 'physician': name}, self) 
                      for constraint in self.constraints):
                    continue
            
            available_physicians.append(name)
        
        if not available_physicians:
            self._track_unassigned_task(task, period_start, 'MAIN' if task.type == TaskType.MAIN else 'CALL')
        
        return available_physicians

    def _handle_initial_assignments(self, week_start: str, 
                                  main_period: Dict[str, Any],
                                  call_period: Dict[str, Any]) -> Set[str]:
        """Handle pre-assigned tasks from initial schedule."""
        if not self.initial_schedule:
            return set()
            
        handled_tasks = set()
        week_start_date = date.fromisoformat(week_start)
        
        # First handle main tasks
        for physician, assignments in self.initial_schedule.items():
            for assignment in assignments:
                if date.fromisoformat(assignment['start_date']) == week_start_date:
                    task = self.task_manager.get_task(assignment['task'])
                    if not task:
                        continue
                        
                    if task.type == TaskType.MAIN:
                        self._assign_task(task, main_period, physician)
                        handled_tasks.add(task.name)
        
        # Then handle calls
        self._handle_calls_for_week(week_start_date, call_period, handled_tasks)
        
        return handled_tasks

    def generate_schedule(self, use_initial_schedule: bool = False):
        """Generate complete schedule."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set")
            
        periods = self.calendar.determine_periods()
        period_items = sorted(periods.items())
        
        for week_number, (week_start, week_periods) in enumerate(period_items):
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
                
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if not (main_period and call_period):
                continue
                
            # Handle initial schedule
            handled_tasks = set()
            if use_initial_schedule:
                handled_tasks = self._handle_initial_assignments(
                    week_start, main_period, call_period
                )
                
            # Process remaining tasks in order
            self._process_week_tasks(
                week_number, week_start_date, 
                main_period, call_period, 
                handled_tasks, period_items
            ) 
            
            # Track unassigned tasks for this week
            for task in self.task_manager.data['tasks']:
                if task.name not in handled_tasks:
                    if task.type == TaskType.MAIN:
                        self._track_unassigned_task(task, week_start_date, 'MAIN')
                    elif task.type == TaskType.CALL:
                        # Only track unassigned call if its linked main task was assigned
                        linked_mains = self._get_linked_main_tasks(task)
                        if any(main.name in handled_tasks for main in linked_mains):
                            self._track_unassigned_task(task, week_start_date, 'CALL')
        
        # After generating schedule, save unassigned tasks
        self.save_unassigned_tasks("output/schedule/unassigned_tasks.json")

    def _process_week_tasks(self, week_number: int, week_start: date,
                           main_period: Dict[str, Any], 
                           call_period: Dict[str, Any],
                           handled_tasks: Set[str],
                           period_items: List[tuple]) -> None:
        """Process all tasks for a given week."""
        # First handle multi-week tasks
        for task in self.task_manager.data['tasks']:
            if task.name in handled_tasks or task.type != TaskType.MAIN:
                continue
                
            if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK:
                if self._is_task_start_week(task, week_number):
                    remaining_weeks = period_items[week_number:week_number + task.category.number_of_weeks]
                    if len(remaining_weeks) >= task.category.number_of_weeks:
                        new_handled = self._handle_multi_week_task(
                            task, 
                            week_number,
                            [week_periods for _, week_periods in remaining_weeks],
                            handled_tasks
                        )
                        handled_tasks.update(new_handled)
        
        # Then handle single-week tasks
        self._handle_single_week_tasks(
            week_start, main_period, call_period, handled_tasks
        )

    def _handle_single_week_tasks(self, week_start: date,
                                main_period: Dict[str, Any],
                                call_period: Dict[str, Any],
                                handled_tasks: Set[str]) -> None:
        """Handle all single-week tasks for the given week."""
        # First handle tasks without linked calls
        for task in self.task_manager.data['tasks']:
            if (task.name in handled_tasks or 
                task.type != TaskType.MAIN or 
                task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                continue
                
            if not self.task_manager.data['linkage_manager'].get_linked_task(task):
                self._assign_single_task(task, main_period, handled_tasks)
        
        # Then handle tasks with linked calls
        for task in self.task_manager.data['tasks']:
            if (task.name in handled_tasks or 
                task.type != TaskType.MAIN or 
                task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                continue
                
            linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
            if linked_call and linked_call not in handled_tasks:
                call_task = self.task_manager.get_task(linked_call)
                new_handled = self._handle_linked_tasks(
                    task, call_task, main_period, call_period, week_start
                )
                handled_tasks.update(new_handled)

    def _is_task_start_week(self, task: Task, week_number: int) -> bool:
        """Check if this is a valid starting week for this task."""
        return (week_number + task.week_offset) % task.category.number_of_weeks == 0

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
        """Save unassigned tasks to JSON file with detailed information."""
        if not self.unassigned_tasks:
            self.logger.info("All tasks were successfully assigned")
            return
            
        # Group unassigned tasks by category for better analysis
        category_summary = defaultdict(int)
        for tasks in self.unassigned_tasks.values():
            for task in tasks:
                category_summary[task['category']] += 1
            
        with open(filename, 'w') as f:
            json.dump(
                {
                    'unassigned_tasks': dict(self.unassigned_tasks),
                    'summary': {
                        'total_unassigned': sum(len(tasks) for tasks in self.unassigned_tasks.values()),
                        'weeks_with_unassigned': len(self.unassigned_tasks),
                        'categories_affected': dict(category_summary),
                        'period': {
                            'start': self.scheduling_period[0].isoformat(),
                            'end': self.scheduling_period[1].isoformat()
                        }
                    }
                }, 
                f, 
                indent=2
            )
            
            self.logger.warning(
                f"Found {sum(len(tasks) for tasks in self.unassigned_tasks.values())} "
                f"unassigned tasks. Details saved to {filename}"
            )

    def set_scheduling_period(self, start_date: date, end_date: date):
        """Set the scheduling period."""
        self.scheduling_period = (start_date, end_date)
        self.logger.info(f"Scheduling period set: {start_date} to {end_date}")

    def load_initial_schedule(self, filename: str):
        """Load initial schedule from JSON file."""
        with open(filename, 'r') as f:
            self.initial_schedule = json.load(f)
        self.logger.info(f"Initial schedule loaded from {filename}")

    def _assign_single_task(self, task: Task, period: Dict[str, Any], 
                           handled_tasks: Set[str]) -> None:
        """Assign a single task without linked calls."""
        available_physicians = self._get_available_physicians(task, period['days'])
        if available_physicians:
            selected_physician = self._select_best_physician(
                available_physicians, task, period['days'][0]
            )
            if selected_physician:
                self._assign_task(task, period, selected_physician)
                handled_tasks.add(task.name)
            else:
                self._track_unassigned_task(task, period['days'][0], 'MAIN')
        else:
            self._track_unassigned_task(task, period['days'][0], 'MAIN')

    def _handle_calls_for_week(self, week_start: date, 
                              call_period: Dict[str, Any], 
                              handled_tasks: Set[str]) -> None:
        """Handle call assignments for a given week."""
        for task in self.task_manager.data['tasks']:
            if task.type != TaskType.CALL or task.name in handled_tasks:
                continue

            # Get linked main tasks
            linked_mains = self._get_linked_main_tasks(task)
            if not linked_mains:
                continue

            # Check if any linked main tasks are assigned this week
            main_physicians = self._get_physicians_doing_linked_mains(task, week_start)
            if not main_physicians:
                continue

            # Try to assign call to one of the main task physicians
            available_physicians = [
                p for p in main_physicians 
                if self._is_physician_available(p, call_period['days'])
            ]

            if available_physicians:
                selected_physician = self._select_best_physician(
                    available_physicians, task, call_period['days'][0]
                )
                if selected_physician:
                    self._assign_task(task, call_period, selected_physician)
                    handled_tasks.add(task.name)

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

    def _track_unassigned_task(self, task: Task, week_start: date, period_type: str):
        """Track tasks that couldn't be assigned."""
        self.unassigned_tasks[week_start.isoformat()].append({
            'task': task.name,
            'category': task.category.name,
            'type': period_type,
            'reason': "No available physicians",
            'constraints_failed': self._get_failed_constraints(task, week_start)
        })

    def _get_failed_constraints(self, task: Task, week_start: date) -> List[str]:
        """Get list of constraints that failed for this task."""
        failed_constraints = []
        
        # Check each constraint type
        for physician in self.physician_manager.data['physicians']:
            assignment = {
                'task': task,
                'period': {'days': [week_start]},  # Simplified for checking
                'physician': physician.name
            }
            
            for constraint in self.constraints:
                if not constraint.check(assignment, self):
                    constraint_name = constraint.__class__.__name__
                    if constraint_name not in failed_constraints:
                        failed_constraints.append(constraint_name)
        
        return failed_constraints

    def _select_best_physician(self, available_physicians: List[str], task: Task, 
                             period_start: date = None) -> Optional[str]:
        """Select the best physician for a task based on constraints."""
        best_physician = None
        min_score = float('inf')
        
        for physician in available_physicians:
            score = 0
            
            # Count category assignments
            category_count = self.physician_categories[physician].count(task.category.name)
            score += category_count * 10
            
            # Count recent call assignments if this is a call task
            if task.is_call_task and period_start:
                recent_calls = sum(1 for call in self.physician_calls[physician]
                                 if (period_start - call['end_date']).days <= 28)
                score += recent_calls * 20
            
            if score < min_score:
                min_score = score
                best_physician = physician
                
        return best_physician

    def _is_physician_available(self, physician: str, period_days: List[date]) -> bool:
        """Check if physician is available for all days in a period."""
        return all(not self.physician_manager.is_unavailable(physician, day) 
                  for day in period_days)

    def _handle_multi_week_task(self, task: Task, week_number: int, 
                               periods: List[Dict[str, Any]], pre_assigned_tasks: Set[str]) -> Set[str]:
        """Handle multi-week task assignment."""
        if not self._is_task_start_week(task, week_number):
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

        # Get all days for main periods
        main_days = []
        for period in main_periods:
            main_days.extend(period['days'])

        # Get available physicians for all main periods
        available_physicians = []
        for physician in self.physician_manager.data['physicians']:
            name = physician.name
            if (self._is_physician_eligible(name, task) and
                self._is_physician_available(name, main_days) and
                not any(self._has_overlapping_assignment(name, {'days': period['days']}) 
                       for period in main_periods)):
                available_physicians.append(name)

        if not available_physicians:
            self.logger.warning(f"No physicians available for multi-week task {task.name}")
            return set()

        # Select best physician
        selected_physician = self._select_best_physician(available_physicians, task)
        if not selected_physician:
            return set()

        # Assign main tasks
        for main_period in main_periods:
            self._assign_task(task, main_period, selected_physician)
            handled_tasks.add(task.name)
            instance_key = f"{task.name}_{main_period['days'][0]}"
            handled_tasks.add(instance_key)

        # Handle linked call
        linked_call = self.task_manager.data['linkage_manager'].get_linked_task(task)
        if linked_call and linked_call not in pre_assigned_tasks:
            call_task = self.task_manager.get_task(linked_call)
            multi_week_call_key = f"{call_task.name}_{main_periods[0]['days'][0]}_{main_periods[-1]['days'][-1]}"
            
            if multi_week_call_key not in self.assigned_call_periods:
                call_period = call_periods[0]  # Use first call period
                
                # Try same physician first
                if self._is_physician_available(selected_physician, call_period['days']):
                    self._assign_task(call_task, call_period, selected_physician)
                    self.assigned_call_periods.add(multi_week_call_key)
                    handled_tasks.add(call_task.name)
                    for other_period in call_periods:
                        handled_tasks.add(f"{call_task.name}_{other_period['days'][0]}")
                else:
                    # Try other available physicians
                    available_for_call = self._get_available_physicians(call_task, call_period['days'])
                    if available_for_call:
                        call_physician = self._select_best_physician(available_for_call, call_task)
                        if call_physician:
                            self._assign_task(call_task, call_period, call_physician)
                            self.assigned_call_periods.add(multi_week_call_key)
                            handled_tasks.add(call_task.name)
                            for other_period in call_periods:
                                handled_tasks.add(f"{call_task.name}_{other_period['days'][0]}")

        return handled_tasks

    def _handle_linked_tasks(self, main_task: Task, call_task: Task, 
                           main_period: Dict[str, Any], call_period: Dict[str, Any],
                           week_start: date) -> Set[str]:
        """Handle assignment of linked main and call tasks."""
        handled_tasks = set()
        
        # First assign the main task
        available_for_main = self._get_available_physicians(main_task, main_period['days'])
        if not available_for_main:
            self.logger.warning(f"No physicians available for main task {main_task.name}")
            return handled_tasks

        # Select and assign physician for main task
        main_physician = self._select_best_physician(available_for_main, main_task)
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
                # Get all physicians doing linked main tasks this week
                linked_physicians = []
                for physician, assignments in self.schedule.items():
                    for assignment in assignments:
                        if (assignment['start_date'] == week_start and 
                            assignment['task'].name in [t.name for t in linked_mains]):
                            linked_physicians.append(physician)
                
                # Filter for physicians available for call period
                available_for_call = [
                    p for p in linked_physicians 
                    if self._is_physician_available(p, call_period['days'])
                ]
                
                if available_for_call:
                    call_physician = self._select_best_physician(available_for_call, call_task)
                    if call_physician:
                        self._assign_task(call_task, call_period, call_physician)
                        handled_tasks.add(call_task.name)
                else:
                    self.logger.warning(
                        f"No physicians doing linked main tasks available for call {call_task.name}"
                    )
        
        return handled_tasks

    def print_schedule(self):
        """Print the generated schedule."""
        for physician, tasks in sorted(self.schedule.items()):
            print(f"\n{physician}:")
            for task in sorted(tasks, key=lambda x: x['start_date']):
                print(f"  {task['task'].name}: {task['start_date']} - {task['end_date']}")
        
        # Print summary of unassigned tasks
        if self.unassigned_tasks:
            print("\nUnassigned Tasks Summary:")
            total_unassigned = sum(len(tasks) for tasks in self.unassigned_tasks.values())
            print(f"Total unassigned tasks: {total_unassigned}")
            print("Categories affected:", list(set(
                task['category'] 
                for tasks in self.unassigned_tasks.values() 
                for task in tasks
            )))

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