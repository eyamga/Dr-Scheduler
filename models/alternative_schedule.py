from datetime import date, timedelta
from typing import Dict, List, Any, Optional, Set
import logging
from collections import defaultdict
import json
from ics import Calendar as IcsCalendar, Event

from models.task import TaskType, TaskDaysParameter, Task

class AlternativeSchedule:
    # Add scoring weights as class constants that can be easily modified
    WEIGHTS = {
        'WORKING_WEEKS': 100,
        'HEAVINESS': 50,
        'PREFERRED_TASKS': 30,
        'CATEGORY_DIVERSITY': 100,
        'CALL_DISTRIBUTION': 60
    }

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
        
        # Add tracking for unassigned tasks
        self.unassigned_tasks = defaultdict(list)  # {week_start: [(task_name, period_type)]}
        
        # Add global task tracking
        self.assigned_tasks_by_period = defaultdict(set)  # {(task_name, start_date): physician}
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Add flags to toggle constraints
        self.constraints_enabled = {
            'working_weeks': True,
            'heaviness': True,
            'preferred_tasks': True,
            'category_diversity': True,
            'call_distribution': True
        }

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

    def _track_unassigned_task(self, task: Task, week_start: date, period_type: str):
        """Track tasks that couldn't be assigned."""
        self.unassigned_tasks[week_start.isoformat()].append({
            'task': task.name,
            'category': task.category.name,
            'type': period_type,
            'reason': "No available physicians"
        })

    def _get_available_physicians(self, task: Task, period_days: List[date]) -> List[str]:
        """Get list of physicians available and eligible for a task in a period."""
        available_physicians = []
        period = {'days': period_days}
        period_start = period_days[0]
        period_end = period_days[-1]
        
        for physician in self.physician_manager.data['physicians']:
            name = physician.name
            
            if not self._is_physician_eligible(name, task):
                continue
            
            if (task.is_call_task or 
                (task.category.days_parameter == TaskDaysParameter.MULTI_WEEK and 
                 self.task_manager.data['linkage_manager'].get_linked_task(task))):
                if self._has_recent_call(name, period_start, period_end):
                    continue
            
            if (self._is_physician_available(name, period_days) and 
                not self._has_overlapping_assignment(name, period)):
                available_physicians.append(name)
            
        if not available_physicians:
            self._track_unassigned_task(task, period_start, 'MAIN' if task.type == TaskType.MAIN else 'CALL')
            
        return available_physicians

    def _assign_task(self, task: Task, period: Dict[str, Any], physician: str):
        """Assign a task to a physician and update tracking structures."""
        assignment = {
            'task': task,
            'days': period['days'],
            'start_date': period['days'][0],
            'end_date': period['days'][-1]
        }
        
        # Check if task is already assigned for this period
        task_period_key = (task.name, assignment['start_date'])
        if task_period_key in self.assigned_tasks_by_period:
            existing_physician = self.assigned_tasks_by_period[task_period_key]
            self.logger.warning(
                f"Task {task.name} for period starting {assignment['start_date']} "
                f"is already assigned to {existing_physician}"
            )
            return False
        
        # Check for overlapping assignments for this physician
        for existing_assignment in self.schedule[physician]:
            if (max(existing_assignment['start_date'], assignment['start_date']) <= 
                min(existing_assignment['end_date'], assignment['end_date'])):
                self.logger.warning(
                    f"Overlapping assignment prevented: {task.name} for {physician} "
                    f"would overlap with {existing_assignment['task'].name}"
                )
                return False
        
        # Add to global task tracking
        self.assigned_tasks_by_period[task_period_key] = physician
        
        # Add to physician's schedule
        self.schedule[physician].append(assignment)
        self.physician_assignments[physician].append(task)
        self.physician_categories[physician].append(task.category.name)
        
        if task.is_call_task:
            self.physician_calls[physician].append(assignment)
        
        self.logger.info(
            f"Assigned {task.name} to {physician} for period "
            f"{period['days'][0]} - {period['days'][-1]}"
        )
        return True

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
        """Handle assignment of linked main and call tasks."""
        handled_tasks = set()
        
        # First assign the main task
        available_for_main = self._get_available_physicians(main_task, main_period['days'])
        if not available_for_main:
            self.logger.warning(f"No physicians available for main task {main_task.name}")
            return handled_tasks

        # Select and assign physician for main task
        main_physician = self._select_best_physician(available_for_main, main_task, main_period['days'][0])
        if main_physician:
            if self._assign_task(main_task, main_period, main_physician):
                handled_tasks.add(main_task.name)
                
                # Get all linked main tasks for this call
                linked_mains = self._get_linked_main_tasks(call_task)
                all_main_tasks_assigned = True
                
                for linked_main in linked_mains:
                    if not any(a['task'].name == linked_main.name and 
                              a['start_date'] == week_start 
                              for assignments in self.schedule.values() 
                              for a in assignments):
                        all_main_tasks_assigned = False
                        break
                
                if all_main_tasks_assigned:
                    linked_physicians = self._get_physicians_doing_linked_mains(call_task, week_start)
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
                            if self._assign_task(call_task, call_period, call_physician):
                                handled_tasks.add(call_task.name)
    
        return handled_tasks

    def _calculate_available_weeks(self, physician: str) -> int:
        """Calculate number of available weeks for a physician within scheduling period."""
        if not self.scheduling_period:
            return 0
            
        total_weeks = 0
        current_date = self.scheduling_period[0]
        while current_date <= self.scheduling_period[1]:
            week_available = False
            for i in range(7):
                check_date = current_date + timedelta(days=i)
                if not self.physician_manager.is_unavailable(physician, check_date):
                    week_available = True
                    break
            if week_available:
                total_weeks += 1
            current_date += timedelta(weeks=1)
        return total_weeks

    def _select_best_physician(self, available_physicians: List[str], task: Task, 
                             period_start: date = None) -> Optional[str]:
        """
        Select the best physician based on enabled soft constraints.
        """
        best_physician = None
        min_score = float('inf')  # Lower score is better
        
        for physician in available_physicians:
            score = 0
            
            # Working Weeks Percentage Constraint
            if self.constraints_enabled['working_weeks']:
                score += self._calculate_working_weeks_score(physician, task, period_start)
            
            # Task Heaviness Constraint
            if self.constraints_enabled['heaviness']:
                score += self._calculate_heaviness_score(physician, task)
            
            # Preferred Tasks Optimization
            if self.constraints_enabled['preferred_tasks']:
                score += self._calculate_preferred_tasks_score(physician, task)
            
            # Category Diversity
            if self.constraints_enabled['category_diversity']:
                score += self._calculate_category_diversity_score(physician, task)
            
            # Call Distribution
            if self.constraints_enabled['call_distribution'] and task.is_call_task:
                score += self._calculate_call_distribution_score(physician, period_start)
            
            if score < min_score:
                min_score = score
                best_physician = physician
                
        return best_physician

    def _calculate_working_weeks_score(self, physician: str, task: Task, period_start: date = None) -> float:
        """
        Calculate score based on working weeks percentage with focus on distribution.
        """
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        available_weeks = self._calculate_available_weeks(physician)
        target_weeks = int(physician_obj.desired_working_weeks * available_weeks)
        
        # Calculate current assigned weeks
        current_assignments = self.schedule[physician]
        if not current_assignments:
            return 0  # No penalty for first assignment
        
        # Calculate weeks per month distribution
        months_distribution = defaultdict(int)
        
        # Calculate number of months in scheduling period
        total_months = (self.scheduling_period[1].year - self.scheduling_period[0].year) * 12 + \
                       self.scheduling_period[1].month - self.scheduling_period[0].month + 1
        
        target_per_month = target_weeks / total_months
        
        # Add existing assignments to distribution
        for assignment in current_assignments:
            month_key = (assignment['start_date'].year, assignment['start_date'].month)
            weeks = (assignment['end_date'] - assignment['start_date']).days // 7 + 1
            months_distribution[month_key] += weeks
        
        # Add potential new assignment
        task_weeks = task.number_of_weeks if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK else 1
        if period_start:
            new_month_key = (period_start.year, period_start.month)
        else:
            new_month_key = (self.scheduling_period[0].year, self.scheduling_period[0].month)
        months_distribution[new_month_key] += task_weeks
        
        # Calculate distribution penalty
        distribution_penalty = 0
        
        # Get all months in scheduling period
        current_date = self.scheduling_period[0]
        end_date = self.scheduling_period[1]
        months_in_period = []
        
        while current_date <= end_date:
            month_key = (current_date.year, current_date.month)
            months_in_period.append(month_key)
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        # Calculate standard deviation of distribution
        values = [months_distribution[month_key] for month_key in months_in_period]
        if values:
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = variance ** 0.5
            distribution_penalty += std_dev * 15  # Penalize uneven distribution
        
        # Penalize months over target
        for month_key in months_distribution:
            if months_distribution[month_key] > target_per_month:
                distribution_penalty += (months_distribution[month_key] - target_per_month) * 20
        
        # Calculate overall workload penalty
        total_weeks = sum(months_distribution.values())
        if total_weeks > target_weeks:
            distribution_penalty += (total_weeks - target_weeks) * 30
        
        return distribution_penalty

    def _calculate_heaviness_score(self, physician: str, task: Task) -> float:
        """Calculate score based on task heaviness."""
        if not task.is_heavy:
            return 0
            
        recent_assignments = self.physician_assignments[physician]
        
        # For multi-week tasks, look beyond the task's duration
        if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK:
            look_back = -3  # Look at last 3 assignments
        else:
            look_back = -1  # Look at last assignment only
            
        recent_heavy_tasks = [
            t for t in recent_assignments[look_back:]
            if t.is_heavy
        ]
        
        return len(recent_heavy_tasks) * self.WEIGHTS['HEAVINESS']

    def _calculate_preferred_tasks_score(self, physician: str, task: Task) -> float:
        """Calculate score based on physician's task preferences."""
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        if task.category.name in physician_obj.preferred_tasks:
            # Better score (lower) for higher ranked preferences
            rank = physician_obj.preferred_tasks.index(task.category.name)
            return -self.WEIGHTS['PREFERRED_TASKS'] * (len(physician_obj.preferred_tasks) - rank)
        return 0

    def _calculate_category_diversity_score(self, physician: str, task: Task) -> float:
        """
        Calculate score based on category diversity and consecutive assignments.
        """
        recent_assignments = self.physician_assignments[physician]
        if not recent_assignments:
            return 0
        
        score = 0
        
        # Check recent categories (last 3 assignments)
        recent_categories = [
            t.category.name for t in recent_assignments[-3:]
        ]
        category_count = recent_categories.count(task.category.name)
        score += category_count * self.WEIGHTS['CATEGORY_DIVERSITY']
        
        # Add penalty for consecutive same-category tasks (excluding multi-week)
        if (recent_assignments and 
            task.category.days_parameter != TaskDaysParameter.MULTI_WEEK and
            recent_assignments[-1].category.name == task.category.name):
            score += self.WEIGHTS['CATEGORY_DIVERSITY'] * 3
        
        return score

    def _calculate_call_distribution_score(self, physician: str, period_start: date) -> float:
        """Calculate score based on call distribution."""
        if not period_start:
            return 0
            
        recent_calls = [
            call for call in self.physician_calls[physician]
            if (period_start - call['end_date']).days <= 28
        ]
        return len(recent_calls) * self.WEIGHTS['CALL_DISTRIBUTION']

    def set_constraint_enabled(self, constraint_name: str, enabled: bool):
        """Enable or disable specific constraints."""
        if constraint_name in self.constraints_enabled:
            self.constraints_enabled[constraint_name] = enabled
        else:
            raise ValueError(f"Unknown constraint: {constraint_name}")

    def set_weight(self, constraint_name: str, weight: float):
        """Adjust the weight of a specific constraint."""
        if constraint_name in self.WEIGHTS:
            self.WEIGHTS[constraint_name] = weight
        else:
            raise ValueError(f"Unknown weight parameter: {constraint_name}")

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

    def _is_task_start_week(self, task: Task, week_start_date: date) -> bool:
        """
        Check if this is a valid starting week for this task based on its offset.
        
        Args:
            task: The task to check
            week_start_date: The start date of the week
        
        Returns:
            bool: True if this is a valid starting week for this task
        """
        # Calculate week number since start of scheduling period
        days_since_start = (week_start_date - self.scheduling_period[0]).days
        week_number = days_since_start // 7
        
        # Check if this week is a valid start week for this task
        return (week_number + task.week_offset) % task.category.number_of_weeks == 0

    def _handle_multi_week_task(self, task: Task, week_number: int, 
                               periods: List[Dict[str, Any]], pre_assigned_tasks: Set[str]) -> Set[str]:
        """
        Handle multi-week task assignment.
        Returns set of handled task names.
        """
        # Get the start date of the first period
        first_period = periods[0]
        first_main_period = next((p for p in first_period if p['type'] == 'MAIN'), None)
        if not first_main_period:
            return set()
        
        week_start_date = first_main_period['days'][0]
        
        if not self._is_task_start_week(task, week_start_date):
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
        selected_physician = self._select_best_physician(available_physicians, task, week_start_date)
        if not selected_physician:
            return set()

        # Assign main tasks for all weeks
        for i, main_period in enumerate(main_periods):
            if self._assign_task(task, main_period, selected_physician):
                handled_tasks.add(task.name)
                instance_key = f"{task.name}_{main_period['days'][0]}"
                handled_tasks.add(instance_key)
            else:
                self.logger.warning(f"Failed to assign {task.name} to {selected_physician}")
                return set()  # If we can't assign one part, we shouldn't assign any

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
                    if self._assign_task(call_task, call_period, selected_physician):
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
                        call_physician = self._select_best_physician(available_for_call, call_task, call_period['days'][0])
                        if call_physician:
                            if self._assign_task(call_task, call_period, call_physician):
                                self.assigned_call_periods.add(multi_week_call_key)
                                handled_tasks.add(call_task.name)
                                # Mark all potential call periods as handled
                                for other_call_period in call_periods:
                                    instance_key = f"{call_task.name}_{other_call_period['days'][0]}"
                                    handled_tasks.add(instance_key)

        return handled_tasks

    def _handle_all_ctu_tasks(self, periods, period_items, pre_assigned_tasks):
        """Handle all CTU tasks across the entire scheduling period at once."""
        handled_tasks = set()
        
        # Get all CTU tasks
        ctu_tasks = [
            task for task in self.task_manager.data['tasks']
            if task.category.name == "CTU" and task.type == TaskType.MAIN
            and task.name not in pre_assigned_tasks
        ]
        
        # Group CTU tasks by their offset
        offset_groups = {}
        for task in ctu_tasks:
            if task.week_offset not in offset_groups:
                offset_groups[task.week_offset] = []
            offset_groups[task.week_offset].append(task)
        
        # Handle each offset group separately
        for week_offset, tasks in offset_groups.items():
            week_number = 0
            while week_number < len(period_items):
                if (week_number + week_offset) % 2 == 0:  # CTU tasks are 2-week tasks
                    week_start, week_periods = period_items[week_number]
                    if week_number + 1 < len(period_items):  # Ensure we have both weeks available
                        next_week_start, next_week_periods = period_items[week_number + 1]
                        
                        # Get periods for both weeks
                        main_period1 = next((p for p in week_periods if p['type'] == 'MAIN'), None)
                        main_period2 = next((p for p in next_week_periods if p['type'] == 'MAIN'), None)
                        call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
                        
                        if main_period1 and main_period2 and call_period:
                            for task in tasks:
                                if task.name not in handled_tasks and task.name not in pre_assigned_tasks:
                                    # Try to assign both weeks and the call
                                    handled = self._handle_multi_week_task(
                                        task, 
                                        week_number,
                                        [week_periods, next_week_periods],
                                        pre_assigned_tasks
                                    )
                                    handled_tasks.update(handled)
                
                week_number += 1
        
        return handled_tasks

    def generate_schedule(self, use_initial_schedule: bool = False):
        """Generate the schedule."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        # Get periods from calendar
        periods = self.calendar.determine_periods()
        period_items = sorted(periods.items())
        
        # Handle pre-assigned tasks first
        pre_assigned_tasks = set()
        if use_initial_schedule and self.initial_schedule:
            for week_start, week_periods in period_items:
                week_start_date = date.fromisoformat(week_start)
                if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                    continue
                
                main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
                call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
                
                if main_period and call_period:
                    pre_assigned_tasks.update(
                        self._handle_initial_assignments(week_start, main_period, call_period)
                    )

        # First handle all CTU tasks for the entire schedule
        handled_ctu_tasks = self._handle_all_ctu_tasks(periods, period_items, pre_assigned_tasks)
        pre_assigned_tasks.update(handled_ctu_tasks)

        # Then handle remaining tasks week by week as before
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

        # After generating schedule, save unassigned tasks
        self.save_unassigned_tasks("output/schedule/unassigned_tasks.json")

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
        
        # Get all tasks that should be assigned for each week
        all_tasks = defaultdict(list)
        periods = self.calendar.determine_periods()
        
        for week_start, week_periods in periods.items():
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
            
            # Get the MAIN and CALL periods for this week
            main_period = next((p for p in week_periods if p['type'] == 'MAIN'), None)
            call_period = next((p for p in week_periods if p['type'] == 'CALL'), None)
            
            if main_period and call_period:
                # Handle main tasks for MAIN period
                for task in self.task_manager.data['tasks']:
                    if task.type == TaskType.MAIN:
                        if (task.category.days_parameter != TaskDaysParameter.MULTI_WEEK or 
                            self._is_task_start_week(task, week_start_date)):
                            all_tasks[week_start].append({
                                'task': task.name,
                                'category': task.category.name,
                                'type': 'MAIN',
                                'period': main_period
                            })
                
                    # Handle call tasks only for CALL period
                    elif task.type == TaskType.CALL:
                        linked_mains = self._get_linked_main_tasks(task)
                        if any(self._is_task_start_week(main_task, week_start_date) 
                              for main_task in linked_mains):
                            all_tasks[week_start].append({
                                'task': task.name,
                                'category': task.category.name,
                                'type': 'CALL',
                                'period': call_period
                            })
        
        # Compare with actually assigned tasks
        unassigned = defaultdict(list)
        for week_start, expected_tasks in all_tasks.items():
            for task_info in expected_tasks:
                period_start = task_info['period']['days'][0]
                task_period_key = (task_info['task'], period_start)
                
                if task_period_key not in self.assigned_tasks_by_period:
                    unassigned[week_start].append({
                        'task': task_info['task'],
                        'category': task_info['category'],
                        'type': task_info['type'],
                        'period_type': task_info['period']['type'],
                        'period_days': [d.isoformat() for d in task_info['period']['days']],
                        'reason': "No available physicians"
                    })
        
        # Save to file
        with open(filename, 'w') as f:
            json.dump(
                {
                    'unassigned_tasks': dict(unassigned),
                    'summary': {
                        'total_unassigned': sum(len(tasks) for tasks in unassigned.values()),
                        'weeks_with_unassigned': len(unassigned),
                        'categories_affected': list(set(
                            task['category'] 
                            for tasks in unassigned.values() 
                            for task in tasks
                        )),
                        'types_affected': list(set(
                            task['type']
                            for tasks in unassigned.values() 
                            for task in tasks
                        )),
                        'period_types_affected': list(set(
                            task['period_type']
                            for tasks in unassigned.values() 
                            for task in tasks
                        ))
                    }
                }, 
                f, 
                indent=2,
                default=str
            )
        
        self.logger.warning(
            f"Found {sum(len(tasks) for tasks in unassigned.values())} "
            f"unassigned tasks. Details saved to {filename}"
        )
