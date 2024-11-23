from datetime import date, timedelta
from typing import Dict, List, Any, Set, Optional, Tuple
import logging
from collections import defaultdict
import json
from ics import Calendar as IcsCalendar, Event

from ortools.sat.python import cp_model

from models.task import TaskType, TaskDaysParameter, Task
from models.physician import Physician

class ConstraintSchedule:
    """
    Implements scheduling logic using constraint programming with OR-Tools.
    """
    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        self.scheduling_period = None
        self.schedule = defaultdict(list)
        self.initial_schedule = None
        self.unassigned_tasks = defaultdict(list)
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def set_scheduling_period(self, start_date: date, end_date: date):
        """Set the scheduling period."""
        self.scheduling_period = (start_date, end_date)
        self.logger.info(f"Scheduling period set: {start_date} to {end_date}")

    def load_initial_schedule(self, filename: str):
        """Load initial schedule from JSON file."""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                
                # Convert date strings to date objects
                self.initial_schedule = {}
                for physician, assignments in data.items():
                    self.initial_schedule[physician] = []
                    for assignment in assignments:
                        self.initial_schedule[physician].append({
                            'task': assignment['task'],
                            'start_date': assignment['start_date'],
                            'end_date': assignment['end_date']
                        })
                
                self.logger.info(
                    f"Initial schedule loaded from {filename} with "
                    f"{len(self.initial_schedule)} physicians"
                )
        except FileNotFoundError:
            self.logger.warning(f"Initial schedule file not found: {filename}")
            self.initial_schedule = None
        except json.JSONDecodeError:
            self.logger.error(f"Error parsing initial schedule file: {filename}")
            raise

    def generate_schedule(self):
        """Generate schedule using constraint programming."""
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        try:
            periods = self.calendar.determine_periods()
            model = cp_model.CpModel()
            
            # Initialize variables and constraints
            assignments = self._create_variables(model, periods)
            
            # Debug constraints before solving
            self._debug_constraints(model, assignments, periods)
            
            # Add constraints with relaxation
            self._add_relaxed_constraints(model, assignments, periods)
            objective = self._create_objective_function(model, assignments, periods)
            
            # Set objective
            model.Maximize(objective)
            
            # Export model for debugging
            model.ExportToFile("debug_model.txt")
            
            # Create solver and solve
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 600
            solver.parameters.num_search_workers = 8
            solver.parameters.log_search_progress = True
            
            # Add solution callback to track partial solutions
            class SolutionCallback(cp_model.CpSolverSolutionCallback):
                def __init__(self, assignments):
                    cp_model.CpSolverSolutionCallback.__init__(self)
                    self._assignments = assignments
                    self.last_solution = None
                    self.solutions_count = 0
                    
                def on_solution_callback(self):
                    self.solutions_count += 1
                    # Store the current solution
                    current_solution = {}
                    for key, physician_vars in self._assignments.items():
                        for physician_name, var in physician_vars.items():
                            if self.Value(var) == 1:
                                current_solution[key] = physician_name
                    self.last_solution = current_solution
            
            callback = SolutionCallback(assignments)
            self.logger.info("Starting to solve the constraint program...")
            status = solver.Solve(model, callback)
            
            if status == cp_model.OPTIMAL:
                self.logger.info("Optimal solution found")
                self._process_solution(solver, assignments, periods)
            elif status == cp_model.FEASIBLE:
                self.logger.warning("Feasible (non-optimal) solution found")
                self._process_solution(solver, assignments, periods)
            else:
                self.logger.error("No complete solution found")
                if callback.solutions_count > 0:
                    self.logger.info(f"Processing last partial solution (found {callback.solutions_count} partial solutions)")
                    self._process_partial_solution(callback.last_solution, periods)
                else:
                    self.logger.error("No feasible solution found. Trying with minimal constraints...")
                    # Try with minimal constraints
                    minimal_solution = self._solve_with_minimal_constraints(periods)
                    if minimal_solution:
                        self._process_partial_solution(minimal_solution, periods)
                    else:
                        raise ValueError("No feasible solution found, even with minimal constraints")
            
            # Save unassigned tasks
            self.save_unassigned_tasks("output/schedule/unassigned_tasks.json")
            
        except Exception as e:
            self.logger.error(f"Error generating schedule: {str(e)}", exc_info=True)
            raise

    def _create_variables(self, model: cp_model.CpModel, periods: Dict) -> Dict:
        """Create the CP-SAT variables."""
        assignments = {}
        physicians = [p.name for p in self.physician_manager.data['physicians']]
        
        for week_start, week_periods in periods.items():
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
                
            for period in week_periods:
                period_type = period['type']
                for task in self.task_manager.data['tasks']:
                    if ((period_type == 'MAIN' and task.type == TaskType.MAIN) or 
                        (period_type == 'CALL' and task.type == TaskType.CALL)):
                        
                        key = (task.name, week_start, period_type)
                        assignments[key] = {}
                        
                        # Binary variable for each physician
                        for physician in physicians:
                            var_name = f'assign_{task.name}_{physician}_{week_start}_{period_type}'
                            assignments[key][physician] = model.NewBoolVar(var_name)
                            
                            # If there's an initial schedule, enforce those assignments
                            if self.initial_schedule and physician in self.initial_schedule:
                                for initial_assignment in self.initial_schedule[physician]:
                                    if (initial_assignment['task'] == task.name and 
                                        initial_assignment['start_date'] == week_start):
                                        # Force this assignment to be 1
                                        model.Add(assignments[key][physician] == 1)
                                        self.logger.info(
                                            f"Enforcing initial assignment: {task.name} to {physician} "
                                            f"starting {week_start}"
                                        )
        
        return assignments

    def _add_relaxed_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Add constraints with relaxation variables."""
        # First handle initial schedule constraints (these are hard constraints)
        if self.initial_schedule:
            self._add_initial_schedule_constraints(model, assignments, periods)
        
        # Add relaxed single assignment constraints
        for key in assignments:
            # Allow tasks to be unassigned by using <= 1 instead of == 1
            model.Add(sum(assignments[key].values()) <= 1)
        
        # Add no-overlap constraints (these are hard constraints)
        self._add_no_overlap_constraints(model, assignments, periods)
        
        # Add relaxed availability constraints
        self._add_relaxed_availability_constraints(model, assignments, periods)
        
        # Add relaxed eligibility constraints
        self._add_relaxed_eligibility_constraints(model, assignments)
        
        # Add linked task constraints with relaxation
        self._add_relaxed_linked_task_constraints(model, assignments, periods)
        
        # Add multi-week constraints with relaxation
        self._add_relaxed_multi_week_constraints(model, assignments, periods)
        
        # Add call spacing constraints with relaxation
        self._add_relaxed_call_spacing_constraints(model, assignments, periods)

    def _add_no_overlap_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """No physician can be assigned overlapping tasks."""
        for physician in self.physician_manager.data['physicians']:
            for week_start, week_periods in periods.items():
                overlapping_assignments = []
                for period in week_periods:
                    period_assignments = [
                        assignments[(task.name, week_start, period['type'])][physician.name]
                        for task in self.task_manager.data['tasks']
                        if (task.name, week_start, period['type']) in assignments
                    ]
                    if period_assignments:
                        model.Add(sum(period_assignments) <= 1)

    def _add_relaxed_availability_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Physicians must be available during assigned periods."""
        for key, physician_vars in assignments.items():
            task_name, week_start, period_type = key
            week_start_date = date.fromisoformat(week_start)
            
            for physician_name, var in physician_vars.items():
                period = next(p for p in periods[week_start] if p['type'] == period_type)
                
                # If physician is unavailable for any day in the period, they cannot be assigned
                if any(self.physician_manager.is_unavailable(physician_name, day) 
                      for day in period['days']):
                    model.Add(var == 0)

    def _add_relaxed_eligibility_constraints(self, model: cp_model.CpModel, assignments: Dict):
        """Add constraints for task eligibility based on exclusions and restrictions."""
        for key, physician_vars in assignments.items():
            task_name, _, _ = key
            task = self.task_manager.get_task(task_name)
            
            for physician_name, var in physician_vars.items():
                physician = self.physician_manager.get_physician_by_name(physician_name)
                
                # Exclusion constraints
                if task.category.name in physician.exclusion_tasks:
                    model.Add(var == 0)
                
                # Restriction constraints
                if task.is_restricted and task.category.name not in physician.preferred_tasks:
                    model.Add(var == 0)

    def _add_relaxed_linked_task_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Add constraints for linked main and call tasks."""
        for main_task in self.task_manager.data['tasks']:
            if main_task.type == TaskType.MAIN:
                linked_call = self.task_manager.data['linkage_manager'].get_linked_task(main_task)
                if linked_call:
                    call_task = self.task_manager.get_task(linked_call)
                    
                    for week_start in periods:
                        main_key = (main_task.name, week_start, 'MAIN')
                        call_key = (call_task.name, week_start, 'CALL')
                        
                        if main_key in assignments and call_key in assignments:
                            for physician_name in assignments[main_key]:
                                # The same physician should do linked main and call tasks
                                model.Add(assignments[main_key][physician_name] == 
                                        assignments[call_key][physician_name])

    def _add_relaxed_multi_week_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Add improved constraints for multi-week tasks."""
        for task in self.task_manager.data['tasks']:
            if (task.type == TaskType.MAIN and 
                task.category.days_parameter == TaskDaysParameter.MULTI_WEEK):
                
                week_starts = sorted(periods.keys())
                for i in range(len(week_starts) - task.category.number_of_weeks + 1):
                    if not self._is_valid_start_week(task, date.fromisoformat(week_starts[i])):
                        continue
                        
                    weeks = week_starts[i:i + task.category.number_of_weeks]
                    keys = []
                    all_periods_exist = True
                    
                    # Check if we have all required periods
                    for week in weeks:
                        key = (task.name, week, 'MAIN')
                        if key not in assignments:
                            all_periods_exist = False
                            break
                        keys.append(key)
                    
                    if all_periods_exist:
                        # Create assignment variable for this multi-week block
                        for physician_name in self._get_all_physicians():
                            # Check if physician is available for all weeks
                            all_periods = [
                                next(p for p in periods[week] if p['type'] == 'MAIN')
                                for week in weeks
                            ]
                            all_days = [day for period in all_periods for day in period['days']]
                            
                            if all(not self.physician_manager.is_unavailable(physician_name, day) 
                                  for day in all_days):
                                # Create constraints for consecutive weeks
                                for j in range(len(keys) - 1):
                                    model.Add(
                                        assignments[keys[j]][physician_name] == 
                                        assignments[keys[j + 1]][physician_name]
                                    )
                            else:
                                # If physician is not available for all weeks, they can't be assigned
                                for key in keys:
                                    model.Add(assignments[key][physician_name] == 0)

    def _is_valid_start_week(self, task: Task, week_start: date) -> bool:
        """Check if this is a valid starting week for this task."""
        days_since_start = (week_start - self.scheduling_period[0]).days
        week_number = days_since_start // 7
        return (week_number + task.week_offset) % task.category.number_of_weeks == 0

    def _add_relaxed_call_spacing_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Add constraints for minimum spacing between call assignments."""
        CALL_SPACING_DAYS = 21
        
        for physician in self.physician_manager.data['physicians']:
            for task in self.task_manager.data['tasks']:
                if task.type == TaskType.CALL:
                    # Get all call assignments for this physician and task
                    call_assignments = []
                    for week_start in periods:
                        key = (task.name, week_start, 'CALL')
                        if key in assignments and physician.name in assignments[key]:
                            call_assignments.append((
                                date.fromisoformat(week_start),
                                assignments[key][physician.name]
                            ))
                    
                    # Add spacing constraints between calls
                    for i, (date1, var1) in enumerate(call_assignments):
                        for j, (date2, var2) in enumerate(call_assignments):
                            if i < j and (date2 - date1).days < CALL_SPACING_DAYS:
                                # Cannot assign both calls to this physician
                                model.Add(var1 + var2 <= 1)

    def _create_objective_function(self, model: cp_model.CpModel, assignments: Dict, periods: Dict) -> cp_model.LinearExpr:
        """Create the objective function combining all soft constraints."""
        objective_terms = []
        
        # 1. Preferred task assignments (positive weight)
        objective_terms.extend(self._preferred_task_terms(assignments))
        
        # 2. Working weeks distribution (negative weight for deviation)
        objective_terms.extend(self._working_weeks_terms(model, assignments, periods))
        
        # 3. Task heaviness distribution (negative weight for consecutive heavy tasks)
        objective_terms.extend(self._heaviness_terms(model, assignments, periods))
        
        # 4. Category diversity (positive weight for different categories)
        objective_terms.extend(self._diversity_terms(model, assignments, periods))
        
        # 5. Revenue distribution (negative weight for large differences)
        objective_terms.extend(self._revenue_terms(model, assignments))
        
        # Sum all terms
        return sum(term for term in objective_terms)

    def _preferred_task_terms(self, assignments: Dict) -> List[cp_model.LinearExpr]:
        """Create terms for preferred task assignments."""
        terms = []
        WEIGHT = 100
        
        for key, physician_vars in assignments.items():
            task_name, _, _ = key
            task = self.task_manager.get_task(task_name)
            
            for physician_name, var in physician_vars.items():
                physician = self.physician_manager.get_physician_by_name(physician_name)
                if task.category.name in physician.preferred_tasks:
                    terms.append(WEIGHT * var)
        
        return terms

    def _working_weeks_terms(self, model: cp_model.CpModel, assignments: Dict, periods: Dict) -> List[cp_model.LinearExpr]:
        """Create terms for working weeks distribution."""
        terms = []
        WEIGHT = -50  # Negative weight to minimize deviation
        
        # Calculate target weeks for each physician
        for physician in self.physician_manager.data['physicians']:
            total_weeks = sum(1 for _ in periods)
            target_weeks = int(physician.desired_working_weeks * total_weeks)
            
            # Create variables for counting assigned weeks
            week_assignments = defaultdict(list)
            for week_start, week_periods in periods.items():
                week_vars = []
                for period in week_periods:
                    for task in self.task_manager.data['tasks']:
                        key = (task.name, week_start, period['type'])
                        if key in assignments and physician.name in assignments[key]:
                            week_vars.append(assignments[key][physician.name])
                if week_vars:
                    has_week = model.NewBoolVar(f'has_week_{physician.name}_{week_start}')
                    model.Add(sum(week_vars) >= 1).OnlyEnforceIf(has_week)
                    model.Add(sum(week_vars) == 0).OnlyEnforceIf(has_week.Not())
                    week_assignments[week_start].append(has_week)
            
            # Calculate total assigned weeks
            total_assigned = sum(sum(week_vars) for week_vars in week_assignments.values())
            
            # Add penalty for deviation from target
            deviation_plus = model.NewIntVar(0, total_weeks, f'deviation_plus_{physician.name}')
            deviation_minus = model.NewIntVar(0, total_weeks, f'deviation_minus_{physician.name}')
            
            model.Add(total_assigned - target_weeks == deviation_plus - deviation_minus)
            terms.append(WEIGHT * (deviation_plus + deviation_minus))
        
        return terms

    def _heaviness_terms(self, model: cp_model.CpModel, assignments: Dict, periods: Dict) -> List[cp_model.LinearExpr]:
        """Create terms for task heaviness distribution."""
        terms = []
        WEIGHT = -30  # Negative weight to minimize consecutive heavy tasks
        
        # For each physician, penalize consecutive heavy tasks
        for physician in self.physician_manager.data['physicians']:
            period_items = sorted(periods.items())
            for i in range(len(period_items) - 1):
                week_start1, periods1 = period_items[i]
                week_start2, periods2 = period_items[i + 1]
                
                # Create binary variables for having heavy tasks in each week
                has_heavy_week1 = model.NewBoolVar(f'has_heavy_{physician.name}_{week_start1}')
                has_heavy_week2 = model.NewBoolVar(f'has_heavy_{physician.name}_{week_start2}')
                
                # Get heavy task assignments for consecutive weeks
                heavy_tasks1 = [
                    assignments[(task.name, week_start1, period['type'])][physician.name]
                    for period in periods1
                    for task in self.task_manager.data['tasks']
                    if ((task.name, week_start1, period['type']) in assignments and 
                        task.is_heavy)
                ]
                
                heavy_tasks2 = [
                    assignments[(task.name, week_start2, period['type'])][physician.name]
                    for period in periods2
                    for task in self.task_manager.data['tasks']
                    if ((task.name, week_start2, period['type']) in assignments and 
                        task.is_heavy)
                ]
                
                # Add constraints to set the binary variables
                if heavy_tasks1:
                    model.Add(sum(heavy_tasks1) >= 1).OnlyEnforceIf(has_heavy_week1)
                    model.Add(sum(heavy_tasks1) == 0).OnlyEnforceIf(has_heavy_week1.Not())
                
                if heavy_tasks2:
                    model.Add(sum(heavy_tasks2) >= 1).OnlyEnforceIf(has_heavy_week2)
                    model.Add(sum(heavy_tasks2) == 0).OnlyEnforceIf(has_heavy_week2.Not())
                
                # Add penalty for consecutive heavy weeks
                consecutive_heavy = model.NewBoolVar(
                    f'consecutive_heavy_{physician.name}_{week_start1}_{week_start2}'
                )
                model.AddBoolAnd([has_heavy_week1, has_heavy_week2]).OnlyEnforceIf(consecutive_heavy)
                model.AddBoolOr([has_heavy_week1.Not(), has_heavy_week2.Not()]).OnlyEnforceIf(consecutive_heavy.Not())
                
                terms.append(WEIGHT * consecutive_heavy)
        
        return terms

    def _diversity_terms(self, model: cp_model.CpModel, assignments: Dict, periods: Dict) -> List[cp_model.LinearExpr]:
        """Create terms for category diversity."""
        terms = []
        WEIGHT = 40  # Positive weight to encourage diversity
        
        # Group assignments by category
        for physician in self.physician_manager.data['physicians']:
            category_assignments = defaultdict(list)
            
            for key, physician_vars in assignments.items():
                task_name, week_start, _ = key
                task = self.task_manager.get_task(task_name)
                category_assignments[task.category.name].append(physician_vars[physician.name])
            
            # Create binary variables for each category
            for category, vars in category_assignments.items():
                if len(vars) > 0:
                    has_category = model.NewBoolVar(f'has_category_{physician.name}_{category}')
                    model.Add(sum(vars) >= 1).OnlyEnforceIf(has_category)
                    model.Add(sum(vars) == 0).OnlyEnforceIf(has_category.Not())
                    terms.append(WEIGHT * has_category)
        
        return terms

    def _revenue_terms(self, model: cp_model.CpModel, assignments: Dict) -> List[cp_model.LinearExpr]:
        """Create terms for revenue distribution."""
        terms = []
        WEIGHT = -20  # Negative weight to minimize revenue differences
        MAX_REVENUE = int(1e6)  # Maximum possible revenue
        
        # Create revenue variables for each physician
        physician_revenues = {}
        for physician in self.physician_manager.data['physicians']:
            revenue_vars = []
            for (task_name, week_start, period_type) in assignments:
                task = self.task_manager.get_task(task_name)
                if physician.name in assignments[(task_name, week_start, period_type)]:
                    var = assignments[(task_name, week_start, period_type)][physician.name]
                    revenue_vars.append(task.revenue * var)
            
            if revenue_vars:
                total_revenue = model.NewIntVar(0, MAX_REVENUE, f'revenue_{physician.name}')
                model.Add(sum(revenue_vars) == total_revenue)
                physician_revenues[physician.name] = total_revenue
        
        # Create variables for revenue differences
        for p1 in physician_revenues:
            for p2 in physician_revenues:
                if p1 < p2:
                    difference = model.NewIntVar(0, MAX_REVENUE, f'revenue_diff_{p1}_{p2}')
                    model.Add(difference >= physician_revenues[p1] - physician_revenues[p2])
                    model.Add(difference >= physician_revenues[p2] - physician_revenues[p1])
                    terms.append(WEIGHT * difference)
        
        return terms

    def _process_solution(self, solver: cp_model.CpSolver, assignments: Dict, periods: Dict):
        """Process the solution and update the schedule."""
        self.schedule.clear()
        self.unassigned_tasks.clear()
        
        # Track all tasks that should be assigned
        expected_tasks = self._get_expected_tasks(periods)
        
        # Process assignments
        for key, physician_vars in assignments.items():
            task_name, week_start, period_type = key
            week_start_date = date.fromisoformat(week_start)
            
            # Find the assigned physician
            assigned_physician = None
            for physician_name, var in physician_vars.items():
                if solver.Value(var) == 1:
                    assigned_physician = physician_name
                    break
            
            if assigned_physician:
                task = self.task_manager.get_task(task_name)
                period = next(p for p in periods[week_start] if p['type'] == period_type)
                
                self.schedule[assigned_physician].append({
                    'task': task,
                    'days': period['days'],
                    'start_date': period['days'][0],
                    'end_date': period['days'][-1]
                })
                
                # Remove from expected tasks
                task_key = (task_name, week_start, period_type)
                if task_key in expected_tasks:
                    expected_tasks.remove(task_key)
            else:
                # Track unassigned task
                task = self.task_manager.get_task(task_name)
                self._track_unassigned_task(
                    task, 
                    week_start_date, 
                    period_type,
                    "No feasible assignment found"
                )
        
        # Track remaining expected tasks as unassigned
        for task_name, week_start, period_type in expected_tasks:
            task = self.task_manager.get_task(task_name)
            self._track_unassigned_task(
                task,
                date.fromisoformat(week_start),
                period_type,
                "Task not assigned in solution"
            )

    def _get_expected_tasks(self, periods: Dict) -> Set[Tuple[str, str, str]]:
        """Get all tasks that should be assigned in the scheduling period."""
        expected_tasks = set()
        
        for week_start, week_periods in periods.items():
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
            
            for period in week_periods:
                period_type = period['type']
                for task in self.task_manager.data['tasks']:
                    if ((period_type == 'MAIN' and task.type == TaskType.MAIN) or 
                        (period_type == 'CALL' and task.type == TaskType.CALL)):
                        if task.mandatory:  # Only track mandatory tasks
                            if (task.category.days_parameter != TaskDaysParameter.MULTI_WEEK or 
                                self._is_task_start_week(task, week_start_date)):
                                expected_tasks.add((task.name, week_start, period_type))
        
        return expected_tasks

    def _is_task_start_week(self, task: Task, week_start_date: date) -> bool:
        """Check if this is a valid starting week for this task based on its offset."""
        days_since_start = (week_start_date - self.scheduling_period[0]).days
        week_number = days_since_start // 7
        return (week_number + task.week_offset) % task.category.number_of_weeks == 0

    def _track_unassigned_task(self, task: Task, week_start: date, period_type: str, reason: str):
        """Track tasks that couldn't be assigned."""
        self.unassigned_tasks[week_start.isoformat()].append({
            'task': task.name,
            'category': task.category.name,
            'type': period_type,
            'period_type': period_type,
            'reason': reason
        })

    def save_unassigned_tasks(self, filename: str):
        """Save unassigned tasks to JSON file."""
        if not self.unassigned_tasks:
            self.logger.info("All tasks were successfully assigned")
            return
        
        # Calculate summary statistics
        summary = {
            'total_unassigned': sum(len(tasks) for tasks in self.unassigned_tasks.values()),
            'weeks_with_unassigned': len(self.unassigned_tasks),
            'categories_affected': list(set(
                task['category'] 
                for tasks in self.unassigned_tasks.values() 
                for task in tasks
            )),
            'types_affected': list(set(
                task['type']
                for tasks in self.unassigned_tasks.values() 
                for task in tasks
            )),
            'reasons': list(set(
                task['reason']
                for tasks in self.unassigned_tasks.values() 
                for task in tasks
            ))
        }
        
        output = {
            'unassigned_tasks': dict(self.unassigned_tasks),
            'summary': summary
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        self.logger.warning(
            f"Found {summary['total_unassigned']} unassigned tasks across "
            f"{summary['weeks_with_unassigned']} weeks. Details saved to {filename}"
        )

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

    def print_schedule(self):
        """Print the generated schedule."""
        for physician, tasks in self.schedule.items():
            print(f"\n{physician}:")
            for task in tasks:
                print(f"  {task['task'].name}: {task['start_date']} - {task['end_date']}") 

    def _add_initial_schedule_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Add constraints to respect the initial schedule."""
        if not self.initial_schedule:
            return
        
        for physician, initial_assignments in self.initial_schedule.items():
            for initial_assignment in initial_assignments:
                task_name = initial_assignment['task']
                start_date = initial_assignment['start_date']
                
                # Find the corresponding period type
                task = self.task_manager.get_task(task_name)
                if not task:
                    self.logger.warning(f"Task {task_name} from initial schedule not found in task manager")
                    continue
                
                period_type = 'CALL' if task.type == TaskType.CALL else 'MAIN'
                
                key = (task_name, start_date, period_type)
                if key in assignments and physician in assignments[key]:
                    # Force this assignment to be 1
                    model.Add(assignments[key][physician] == 1)
                    
                    # Ensure no other physician is assigned this task
                    for other_physician in assignments[key]:
                        if other_physician != physician:
                            model.Add(assignments[key][other_physician] == 0)
                    
                    self.logger.info(
                        f"Added constraint for initial assignment: {task_name} to {physician} "
                        f"starting {start_date}"
                    )
                else:
                    self.logger.warning(
                        f"Could not enforce initial assignment: {task_name} to {physician} "
                        f"starting {start_date} - assignment not in scope"
                    ) 

    def _process_partial_solution(self, solution: Dict, periods: Dict):
        """Process a partial solution and update the schedule."""
        self.schedule.clear()
        self.unassigned_tasks.clear()
        
        # Track all tasks that should be assigned
        expected_tasks = self._get_expected_tasks(periods)
        
        # Process assignments from partial solution
        for (task_name, week_start, period_type), physician_name in solution.items():
            week_start_date = date.fromisoformat(week_start)
            task = self.task_manager.get_task(task_name)
            period = next(p for p in periods[week_start] if p['type'] == period_type)
            
            self.schedule[physician_name].append({
                'task': task,
                'days': period['days'],
                'start_date': period['days'][0],
                'end_date': period['days'][-1]
            })
            
            # Remove from expected tasks
            task_key = (task_name, week_start, period_type)
            if task_key in expected_tasks:
                expected_tasks.remove(task_key)
        
        # Track unassigned tasks
        for task_name, week_start, period_type in expected_tasks:
            task = self.task_manager.get_task(task_name)
            self._track_unassigned_task(
                task,
                date.fromisoformat(week_start),
                period_type,
                "Task not assigned in partial solution"
            )
        
        self.logger.warning(
            f"Partial schedule created with {len(solution)} assignments and "
            f"{len(expected_tasks)} unassigned tasks"
        ) 

    def _solve_with_minimal_constraints(self, periods: Dict) -> Optional[Dict]:
        """Try to solve with minimal constraints to get at least a partial solution."""
        model = cp_model.CpModel()
        assignments = self._create_variables(model, periods)
        
        # Add only the most essential constraints
        # 1. No physician can work multiple tasks simultaneously
        self._add_no_overlap_constraints(model, assignments, periods)
        
        # 2. Respect physician availability (hard constraint)
        for key, physician_vars in assignments.items():
            task_name, week_start, period_type = key
            week_start_date = date.fromisoformat(week_start)
            
            for physician_name, var in physician_vars.items():
                period = next(p for p in periods[week_start] if p['type'] == period_type)
                if any(self.physician_manager.is_unavailable(physician_name, day) 
                      for day in period['days']):
                    model.Add(var == 0)
        
        # Simple objective: maximize number of assignments
        objective = sum(var for vars in assignments.values() for var in vars.values())
        model.Maximize(objective)
        
        # Solve with minimal constraints
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 300
        status = solver.Solve(model)
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            solution = {}
            for key, physician_vars in assignments.items():
                for physician_name, var in physician_vars.items():
                    if solver.Value(var) == 1:
                        solution[key] = physician_name
            return solution
        
        return None 

    def _debug_constraints(self, model: cp_model.CpModel, assignments: Dict, periods: Dict):
        """Debug constraints and print detailed information about the model."""
        self.logger.info("\nDebug Information:")
        
        # 1. Check physician availability
        self.logger.info("\nPhysician Availability:")
        for week_start, week_periods in periods.items():
            week_start_date = date.fromisoformat(week_start)
            if not (self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1]):
                continue
            
            for period in week_periods:
                available_physicians = self._get_available_physicians(period['days'])
                self.logger.info(f"\nWeek {week_start}, {period['type']} period:")
                self.logger.info(f"Available physicians: {len(available_physicians)}/{len(self.physician_manager.data['physicians'])}")
                
                if len(available_physicians) < 3:  # Warning if too few physicians available
                    self.logger.warning(f"Very few physicians available: {available_physicians}")
        
        # 2. Check multi-week task feasibility
        self.logger.info("\nMulti-week Task Analysis:")
        multi_week_tasks = [t for t in self.task_manager.data['tasks'] 
                           if t.category.days_parameter == TaskDaysParameter.MULTI_WEEK]
        
        for task in multi_week_tasks:
            self.logger.info(f"\nAnalyzing task: {task.name}")
            self._analyze_multi_week_task(task, periods)

    def _analyze_multi_week_task(self, task: Task, periods: Dict):
        """Analyze feasibility of a multi-week task."""
        week_starts = sorted(periods.keys())
        
        for i in range(len(week_starts) - task.category.number_of_weeks + 1):
            start_week = week_starts[i]
            weeks = week_starts[i:i + task.category.number_of_weeks]
            
            # Get all required periods
            all_periods = []
            for week in weeks:
                period = next((p for p in periods[week] if p['type'] == 'MAIN'), None)
                if period:
                    all_periods.append(period)
            
            if len(all_periods) == task.category.number_of_weeks:
                # Get physicians available for all weeks
                all_days = [day for period in all_periods for day in period['days']]
                available_physicians = [
                    p.name for p in self.physician_manager.data['physicians']
                    if all(not self.physician_manager.is_unavailable(p.name, day) 
                          for day in all_days)
                    and task.category.name not in p.exclusion_tasks
                ]
                
                self.logger.info(
                    f"Weeks {start_week} - {weeks[-1]}: "
                    f"{len(available_physicians)} physicians available for all weeks"
                )
                
                if len(available_physicians) == 0:
                    self.logger.warning(f"No physicians available for all weeks!") 

    def _get_available_physicians(self, days: List[date]) -> List[str]:
        """Get list of physicians available for given days."""
        return [
            physician.name
            for physician in self.physician_manager.data['physicians']
            if all(not self.physician_manager.is_unavailable(physician.name, day) 
                  for day in days)
        ]

    def _get_all_physicians(self) -> List[str]:
        """Get list of all physicians."""
        return [physician.name for physician in self.physician_manager.data['physicians']]

    def _get_eligible_physicians(self, physicians: List[str], task: Task) -> List[str]:
        """Get list of physicians eligible for a task."""
        return [
            physician for physician in physicians
            if task.category.name not in self.physician_manager.get_physician_by_name(physician).exclusion_tasks
        ]

    def _is_physician_available(self, physician: str, days: List[date]) -> bool:
        """Check if physician is available for all given days."""
        return all(not self.physician_manager.is_unavailable(physician, day) for day in days)

    def _is_physician_unavailable(self, physician: str, days: List[date]) -> bool:
        """Check if physician is unavailable for any of the given days."""
        return any(self.physician_manager.is_unavailable(physician, day) for day in days)

    def _is_week_in_period(self, week_start: str) -> bool:
        """Check if week is within scheduling period."""
        week_start_date = date.fromisoformat(week_start)
        return self.scheduling_period[0] <= week_start_date <= self.scheduling_period[1] 