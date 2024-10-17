import datetime
from datetime import date, timedelta
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from ics import Calendar as IcsCalendar, Event
import json
import logging
from models.task import TaskType, TaskDaysParameter, Task

from ortools.sat.python import cp_model

logging.basicConfig(level=logging.DEBUG)

# models/math_schedule.py


class MathTask:
    """
    This class represents a mathematical task that is the basic unit in the mathematical model.

    A mathematical task is one contiguous time interval that corresponds to one `Task`. It can be
    spanning one day or several days, be contained in one week or overlapping over several weeks.
    As a contiguous time interval, i.e. there is no whole in it, it has a start_date and an
    end_date and all the dates in between. If a `Task` corresponds to several day intervals,
    we create several corresponding `MathTask`s.
    """

    def __init__(self, name, task_type, y_vars, index, week_start, days, start_date, end_date, number_of_weeks, heaviness, mandatory):
        self.name = name
        assert isinstance(task_type, TaskType)
        self.task_type = task_type,
        self.y_vars = y_vars
        self.index = index
        self.week_start = week_start
        self.days = days  # to keep the current code as is and retrieve all days, list of days
        assert start_date == days[0]
        self.start_date = start_date
        assert end_date == days[-1]
        self.end_date = end_date
        self.number_of_weeks = number_of_weeks
        self.heaviness = heaviness
        self.mandatory = mandatory

    def y_var(self, physician):
        """
        Return the variable for the given physician.

        Warnings:
            It does not matter if this physician is available or not.

        Args:
            physician (str):

        Returns:
            The corresponding mathematical variable.
        """
        return self.y_vars[(self.name, self.start_date, self.end_date, physician)]


    def __str__(self):
        return f"{self.name} [{self.start_date}, {self.end_date}]"

    def __repr__(self):
        return str(self)


class TaskMatcher:
    def __init__(self, physician_manager, task_manager):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.physician_task_counts = defaultdict(lambda: defaultdict(int))
        self.physician_task_days = defaultdict(lambda: defaultdict(list))
        self.physician_call_counts = defaultdict(lambda: defaultdict(int))
        self.last_heavy_task = {}
        self.revenue_distribution = defaultdict(float)

    def _is_physician_eligible(self, physician: str, task: Any, period: Dict[str, Any]) -> bool:
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        logging.debug(f"Checking eligibility for physician {physician} for task {task.name}")

        if task.name in physician_obj.restricted_tasks or task.name in physician_obj.exclusion_tasks:
            logging.debug(f"Physician {physician} is restricted or excluded from task {task.name}")
            return False

        if task.is_call_task and self.physician_call_counts[physician][period['month']] > 0:
            logging.debug(f"Physician {physician} has already been assigned a call task in month {period['month']}")
            return False

        if task.is_discontinuous and not physician_obj.discontinuity_preference:
            logging.debug(f"Physician {physician} does not prefer discontinuous tasks")
            return False

        logging.debug(f"Physician {physician} is eligible for task {task.name}")
        return True

    def _get_eligible_physicians(self, available_physicians: List[str], task: Any, period: Dict[str, Any]) -> List[str]:
        return [
            p for p in available_physicians
            if self._is_physician_eligible(p, task, period)
        ]
    def _get_available_physicians(self, days: List[date]) -> List[str]:
        available_physicians = []
        logging.debug(f"Checking availability for period: {days[0]} - {days[-1]}")
        
        for physician in self.physician_manager.data['physicians']:
            logging.debug(f"Checking availability for physician: {physician.name}")
            
            is_available = all(
                not self.physician_manager.is_unavailable(physician.name, day)
                for day in days
            )

            if is_available:
                available_physicians.append(physician.name)
                logging.debug(f"  {physician.name} is available for the entire period")
            else:
                logging.debug(f"  {physician.name} is unavailable for the period")

        #logging.debug(f"Available physicians for period {days[0]} - {days[-1]}: {available_physicians}")
        return available_physicians

    def find_best_match(self, available_physicians: List[str], task: Any, period: Dict[str, Any], month: int) -> Tuple[str, float]:
        logging.debug(f"Finding best match for task {task.name} in period {period} for month {month}")
        eligible_physicians = self._get_eligible_physicians(available_physicians, task, period)

        if not eligible_physicians:
            logging.debug(f"No eligible physicians found for task {task.name}")
            return None, 0

        scored_physicians = self._score_physicians(eligible_physicians, task, period, month)
        best_physician = max(scored_physicians, key=scored_physicians.get)
        logging.debug(f"Best match for task {task.name} is physician {best_physician} with score {scored_physicians[best_physician]}")
        return best_physician, scored_physicians[best_physician]

    def _score_physicians(self, eligible_physicians: List[str], task: Any, period: Dict[str, Any], month: int) -> Dict[
        str, float]:
        scores = {}
        for physician in eligible_physicians:
            physician_obj = self.physician_manager.get_physician_by_name(physician)
            score = 0
            score += self._score_preference(physician_obj, task)
            score += self._score_fairness(physician, task)
            score += self._score_call_distribution(physician, task, month)
            score += self._score_heavy_task_avoidance(physician, task, period)
            score += self._score_discontinuity_preference(physician_obj, task)
            score += self._score_desired_working_weeks(physician)
            score += self._score_revenue_distribution(physician)
            score += self._score_consecutive_category_avoidance(physician, task)
            scores[physician] = score
        return scores

    def _score_consecutive_category_avoidance(self, physician: str, task: Any) -> float:
        last_task = self.physician_task_counts[physician].get('last_task')
        if last_task and last_task.category == task.category and task.number_of_weeks <= 1:
            return -10
        return 0

    def _score_preference(self, physician_obj: Any, task: Any) -> float:
        return 10 if task.name in physician_obj.preferred_tasks else 0

    def _score_fairness(self, physician: str, task: Any) -> float:
        task_count = self.physician_task_counts[physician][task.name]
        return 5 / (task_count + 1)

    def _score_call_distribution(self, physician: str, task: Any, month: int) -> float:
        if task.is_call_task:
            call_count = self.physician_call_counts[physician][month]
            return 5 / (call_count + 1)
        return 0

    def _score_heavy_task_avoidance(self, physician: str, task: Any, period: Dict[str, Any]) -> float:
        if task.is_heavy:
            if physician not in self.last_heavy_task or \
                    (period['days'][0] - self.last_heavy_task[physician]).days > 7:
                return 5
        return 0

    def _score_discontinuity_preference(self, physician_obj: Any, task: Any) -> float:
        if task.is_discontinuous:
            return 10 if physician_obj.discontinuity_preference else -5
        return 0

    def _score_desired_working_weeks(self, physician: str) -> float:
        total_days = sum(len(days) for days in self.physician_task_days[physician].values())
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        if total_days / 7 < physician_obj.desired_working_weeks * 52:
            return 5
        return 0

    def _score_revenue_distribution(self, physician: str) -> float:
        if not self.revenue_distribution:
            return 0
        avg_revenue = sum(self.revenue_distribution.values()) / len(self.revenue_distribution)
        if self.revenue_distribution[physician] < avg_revenue:
            return 5
        return 0

    def update_physician_stats(self, physician: str, task: Any, period: Dict[str, Any]):
        self.physician_task_counts[physician][task] += 1
        self.physician_task_days[physician][task].extend(period['days'])

        if task.is_call_task:
            self.physician_call_counts[physician][period['days'][0].month] += 1

        if task.is_heavy:
            self.last_heavy_task[physician] = period['days'][-1]

        self.revenue_distribution[physician] += task.revenue

class MathSchedule:
    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        self.scheduling_period = None
        self.task_splits = {}
        self.schedule = defaultdict(list)  # unique solution
        self.task_matcher = TaskMatcher(physician_manager, task_manager)
        self.off_days = {}
        self.assigned_calls = defaultdict(lambda: defaultdict(int))
        self.constraints_info = []

        logging.debug("Schedule initialized with physician_manager, task_manager, and calendar")

    def _log_constraint_info(self, task_name, physician, reason, start_date, end_date):
        """
        Log information about a constraint that sets a variable to zero.

        Args:
            task_name (str): The name of the task.
            physician (str): The name of the physician.
            reason (str): The reason for the constraint.
            start_date (date): The start date of the task period.
            end_date (date): The end date of the task period.
        """
        self.constraints_info.append({
            'task': task_name,
            'physician': physician,
            'reason': reason,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        })

    def save_constraints_info_as_json(self, filename: str):
        """
        Save the constraints information to a JSON file.

        Args:
            filename (str): The name of the file to save the constraints information.
        """
        with open(filename, 'w') as f:
            json.dump(self.constraints_info, f, indent=2)

        logging.info(f"Constraints information saved to {filename}")

    def set_scheduling_period(self, start_date: date, end_date: date):
        self.scheduling_period = (start_date, end_date)
        logging.debug(f"Scheduling period set to {self.scheduling_period}")

    def set_task_splits(self, task_splits: Dict[str, Dict[str, str]]):
        self.task_splits = task_splits
        logging.debug(f"Task splits set to {self.task_splits}")

    def set_off_days(self, off_days: Dict[str, List[date]]):
        self.off_days = off_days
        logging.debug(f"Off days set to {self.off_days}")

    def _load_schedule_from_file(self, filename):
        """
        Load and test the schedule from a JSON file.

        Args:
            filename:

        Raises:
            AssertionError whenever there is a mistake in the schedule format.
        """
        with open(filename, 'r') as f:
            loaded_schedule = json.load(f)

        schedule = defaultdict(list, {
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

        # test loaded schedule
        all_physicians = self._get_all_physicians()
        for physician, task_list in schedule.items():
            assert physician in all_physicians, f"Physician {physician} is not recognized!"
            for task_index, task_dict in enumerate(task_list):
                task = task_dict['task']
                start_date = task_dict['start_date']
                end_date = task_dict['end_date']
                task_number_and_physician_str = f"task number {task_index + 1} and physician {physician}"
                assert isinstance(task, Task), f"Task ({task}) number {task_index + 1} is not recognized for physician {physician}!"
                assert isinstance(start_date, datetime.date), f"Start date {start_date} is not a date for {task_number_and_physician_str}!"
                assert isinstance(end_date,
                                  datetime.date), f"End date {end_date} is not a date for {task_number_and_physician_str}!"
                assert start_date <= end_date, f"Start ({start_date}) and end ({end_date}) date are not coherent for {task_number_and_physician_str}!"
                days = task_dict['days']
                assert date.fromisoformat(days[0]) == start_date, f"First date ({days[0]}) in 'days' is not the start date ({start_date}) for {task_number_and_physician_str}!"
                assert date.fromisoformat(days[-1]) == end_date, f"Last date ({days[-1]}) in 'days' is not the end date ({end_date}) for {task_number_and_physician_str}!"
                for i in range(len(days) - 1):
                    assert date.fromisoformat(days[i+1]) == date.fromisoformat(days[i]) + datetime.timedelta(days=1), f"Dates in 'days' are not continuous for {task_number_and_physician_str}!"

        return schedule

    def _math_load_initial_schedule(self):
        """
        Use loaded schedule as an initial solution.

        Notes:
            This schedule/solution can be partial or complete.

        Warnings:
            The schedule must be loaded in self.schedule before. You can use `load_schedule()` for instance.
        """
        assert self.schedule
        task_index = -1
        physician = None
        vars = []    # variables for the loaded schedule
        values = []  # values from the loaded schedule
        try:
            for physician, task_list in self.schedule.items():
                for task_index, task_dict in enumerate(task_list):
                    task = task_dict['task']
                    vars.append(self.y[(task.name, task_dict['start_date'], task_dict['end_date'], physician)].Index())
                    values.append(1)

            self.math_model._CpModel__model.solution_hint.vars.extend(vars)
            self.math_model._CpModel__model.solution_hint.values.extend(values)

        except Exception as e:
            raise RuntimeError(f"The initial schedule does not correspond to the problem \n"
                  f" physician {physician} at task number {task_index + 1}: {e}")

    def generate_schedule(self, use_initial_schedule=False):
        """
        Generate a schedule given all the instance information.

        Args:
            use_initial_schedule (bool): If `True`, use the loaded schedule as a start point to solve this
                instance.
        """
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        if use_initial_schedule:
            assert self.schedule, f"No initial schedule was provided to start the search!"

        logging.info("Starting schedule generation...")
        extended_end_date = self._extend_scheduling_period()
        logging.debug(f"Scheduling period extended to {extended_end_date}")

        periods = self.calendar.determine_periods()

        relevant_periods = self._filter_relevant_periods(periods, self.scheduling_period[0], extended_end_date)
        logging.debug(f"Filtered relevant periods: {relevant_periods}")

        # create mathematical model
        self.math_model = cp_model.CpModel()

        # create variables, constraints and objective function
        logging.info("Creating variables...")
        self._math_create_variables(periods=relevant_periods)
        logging.info("Saving MathTasks to file...")
        self.serialize_math_tasks("math_tasks.json")

        logging.info("Creating constraints...")
        self._math_create_constraints(periods=relevant_periods)
        logging.info("Saving constraints...")
        self.save_constraints_info_as_json("constraints_info.json")

        logging.info("Creating objective function...")
        # self._math_create_objective_function()

        if use_initial_schedule:
            logging.info("Loading initial schedule...")
            self._math_load_initial_schedule()

        logging.info("Model creation completed.")


        # Creates the solver and solve
        logging.info("Starting solver...")
        self.math_solver = cp_model.CpSolver()
        status = self.math_solver.solve(self.math_model)
        
        # test the solution/schedule
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logging.info("Solution found.")
            logging.info(f"Objective value: {self.math_solver.ObjectiveValue()}")
            self._math_set_solution(periods=relevant_periods)
        else:
            logging.info(f"Schedule infeasible")

        logging.debug("Schedule generated")

    def _get_periods_days(self, week_periods):
        """
        Get all MAIN and CALL days.

        Args:
            week_periods:

        Returns:
            (A, B) with A (MAIN) and B (MAIN) list of list of continuous days.
        """
        main_periods_days = []
        call_periods_days = []
        for period in week_periods:
            if period['type'] == 'MAIN':
                main_periods_days.append(period['days'])
            elif period['type'] == 'CALL':
                call_periods_days.append(period['days'])
            else:
                raise NotImplementedError(f"Period type {period['type']} not recognized!")

        return main_periods_days, call_periods_days

    def _get_all_math_tasks_per_task(self, week_starts):
        """
        Create a dict with all `MathTask` for the given periods.

        Args:
            week_starts:

        Returns:
            A dict with entries [task.name] = [MathTask1, MathTask2, MathTask3, ...]. All task are non overlapping and
            ordered sequentially following the date.
        """
        # create output dict
        math_tasks_dict = {}
        for task in self.task_manager.data['tasks']:
            math_tasks_dict[task.name] = []

        # populate if in sequential order (granted because self.math_tasks is already ordered)
        for week_start in week_starts:
            for task in self.task_manager.data['tasks']:
                if week_start not in self.math_tasks[task.name]:
                    continue
                math_tasks_dict[task.name].extend(self.math_tasks[task.name][week_start])

        return math_tasks_dict

    def _math_create_variables(self, periods):
        self.y = {}
        self.math_tasks = {task.name: {} for task in self.task_manager.data['tasks']}
        all_physicians = self._get_all_physicians()

        week_starts = sorted(periods.keys())

        for task in self.task_manager.data['tasks']:
            task_category = task.category
            self.math_tasks[task.name] = {}

            if task.type == TaskType.MAIN:
                week_offset = task.week_offset
                number_of_weeks = task.number_of_weeks
                week_nbr = week_offset  # Start from the offset week
            else:
                week_nbr = 0
            while week_nbr < len(week_starts):
                week_start = week_starts[week_nbr]

                if task.type == TaskType.MAIN:
                    if task_category.days_parameter == TaskDaysParameter.MULTI_WEEK:
                        for w in range(number_of_weeks):
                            wk_nbr = week_nbr + w
                            if wk_nbr >= len(week_starts):
                                break
                            wk_start = week_starts[wk_nbr]
                            wk_periods = periods[wk_start]
                            main_periods_days, _ = self._get_periods_days(week_periods=wk_periods)
                            if main_periods_days:
                                for main_days in main_periods_days:
                                    start_date = main_days[0]
                                    end_date = main_days[-1]
                                    math_task = MathTask(
                                        name=task.name,
                                        task_type=task.type,
                                        y_vars=self.y,
                                        index=wk_nbr,
                                        week_start=wk_start,
                                        days=main_days,
                                        start_date=start_date,
                                        end_date=end_date,
                                        number_of_weeks=1,
                                        heaviness=task.heaviness,
                                        mandatory=task.mandatory
                                    )
                                    if wk_start not in self.math_tasks[task.name]:
                                        self.math_tasks[task.name][wk_start] = []
                                    self.math_tasks[task.name][wk_start].append(math_task)
                                    for physician in all_physicians:
                                        self.y[(task.name, start_date, end_date, physician)] = self.math_model.NewBoolVar(
                                            f"{task.name}_{start_date}_{end_date}_{physician}")
                        week_nbr += number_of_weeks
                    else: #task_category.days_parameter == TaskDaysParameter.CONTINUOUS:
                        # Handle continuous tasks week by week
                        wk_periods = periods[week_start]
                        main_periods_days, _ = self._get_periods_days(week_periods=wk_periods)
                        if main_periods_days:
                            for main_days in main_periods_days:
                                start_date = main_days[0]
                                end_date = main_days[-1]
                                math_task = MathTask(
                                    name=task.name,
                                    task_type=task.type,
                                    y_vars=self.y,
                                    index=week_nbr,
                                    week_start=week_start,
                                    days=main_days,
                                    start_date=start_date,
                                    end_date=end_date,
                                    number_of_weeks=1,
                                    heaviness=task.heaviness,
                                    mandatory=task.mandatory
                                )
                                if week_start not in self.math_tasks[task.name]:
                                    self.math_tasks[task.name][week_start] = []
                                self.math_tasks[task.name][week_start].append(math_task)
                                for physician in all_physicians:
                                    self.y[(task.name, start_date, end_date, physician)] = self.math_model.NewBoolVar(
                                        f"{task.name}_{start_date}_{end_date}_{physician}")
                                #logging.debug(f"Created MathTask for {task.name} from {start_date} to {end_date}")
                        else:
                            logging.warning(f"No main periods found for {task.name} on week {week_start}")

                        # Move to the next week
                        week_nbr += 1
                elif task.type == TaskType.CALL:
                    week_nbr = 0
                    while week_nbr < len(week_starts):
                        week_start = week_starts[week_nbr]
                        wk_periods = periods[week_start]
                        _, call_periods_days = self._get_periods_days(week_periods=wk_periods)
                        if call_periods_days:
                            for call_days in call_periods_days:
                                start_date = call_days[0]
                                end_date = call_days[-1]
                                math_task = MathTask(
                                    name=task.name,
                                    task_type=task.type,
                                    y_vars=self.y,
                                    index=week_nbr,
                                    week_start=week_start,
                                    days=call_days,
                                    start_date=start_date,
                                    end_date=end_date,
                                    number_of_weeks=1,
                                    heaviness=task.heaviness,
                                    mandatory=task.mandatory
                                )
                                if week_start not in self.math_tasks[task.name]:
                                    self.math_tasks[task.name][week_start] = []
                                self.math_tasks[task.name][week_start].append(math_task)
                                for physician in all_physicians:
                                    self.y[(task.name, start_date, end_date, physician)] = self.math_model.NewBoolVar(
                                        f"{task.name}_{start_date}_{end_date}_{physician}")
                        week_nbr += 1

                else:
                    week_nbr += 1

        logging.debug("Finished creating variables")
    
    def serialize_math_tasks(self, filename: str):
        """
        Serialize all MathTasks to a JSON file.

        Args:
            filename (str): The name of the file to save the MathTasks.
        """
        math_tasks_data = {}
        for task_name, week_tasks in self.math_tasks.items():
            math_tasks_data[task_name] = []
            for week_start, tasks in week_tasks.items():
                for math_task in tasks:
                    task_data = {
                        'name': math_task.name,
                        'task_type': str(math_task.task_type ),
                        'start_date': math_task.start_date.isoformat(),
                        'end_date': math_task.end_date.isoformat(),
                        'days': [day.isoformat() for day in math_task.days],
                        'heaviness': math_task.heaviness,
                        'mandatory': math_task.mandatory
                    }
                    math_tasks_data[task_name].append(task_data)

        with open(filename, 'w') as f:
            json.dump(math_tasks_data, f, indent=2)

        logging.info(f"Serialized MathTasks to {filename}")

    def _math_create_constraints(self, periods):
        """
        Create all constraints for the scheduling problem.

        Notes:
            You can comment one family of constraints to see what happens.

        Args:
            periods:

        """
        # gather sorted week starts
        week_starts = sorted(periods.keys())

        self._math_create_physician_availability_constraints(week_starts=week_starts)
        self._math_create_physician_eligibility_constraints(week_starts=week_starts)
        self._math_create_assignment_constraints(week_starts=week_starts, periods=periods)
        # self._math_create_workload_constraints()
        # self._math_create_desired_working_weeks_constraints()

    def _math_create_physician_availability_constraints(self, week_starts):
        """
        Forbid assigning tasks to physicians who are unavailable during the task period.
        """
        constraints_added = 0
        for week_start in week_starts:
            for task in self.task_manager.data['tasks']:
                if week_start not in self.math_tasks[task.name]:
                    continue
                for math_task in self.math_tasks[task.name][week_start]:
                    for physician in self._get_all_physicians():
                        task_days = math_task.days
                        is_available = all(
                            not self.physician_manager.is_unavailable(physician, day)
                            for day in task_days
                        )
                        if not is_available:
                            self.math_model.Add(
                                self.y[(task.name, math_task.start_date, math_task.end_date, physician)] == 0
                            ).WithName(f"Unavailable_{physician}_{task.name}_{math_task.start_date}")
                            self._log_constraint_info(task.name, physician, "Unavailable", math_task.start_date, math_task.end_date)
                            constraints_added += 1
        logging.info(f"Added {constraints_added} physician availability constraints")
        
    def _math_create_physician_eligibility_constraints(self, week_starts):
        """
        Forbid assigning tasks to physicians who are not eligible to perform them.
        """
        constraints_added = 0
        for week_start in week_starts:
            for task in self.task_manager.data['tasks']:
                if week_start not in self.math_tasks[task.name]:
                    continue
                for math_task in self.math_tasks[task.name][week_start]:
                    for physician in self._get_all_physicians():
                        physician_obj = self.physician_manager.get_physician_by_name(physician)
                        if task.category.name in physician_obj.exclusion_tasks: #task.category.name not in physician_obj.restricted_tasks or
                            self.math_model.Add(
                                self.y[(task.name, math_task.start_date, math_task.end_date, physician)] == 0
                            ).WithName(f"Ineligible_{physician}_{task.name}_{math_task.start_date}")
                            self._log_constraint_info(task.name, physician, "Ineligible", math_task.start_date, math_task.end_date)
                            constraints_added += 1
        logging.info(f"Added {constraints_added} physician eligibility constraints")
 
    def _math_create_assignment_constraints(self, week_starts, periods):
        all_physicians = self._get_all_physicians()
        constraints_added = 0

        all_math_tasks_dict = self._get_all_math_tasks_per_task(week_starts)
        physician_task_intervals = {physician: [] for physician in all_physicians}

        for task in self.task_manager.data['tasks']:
            task_category_name = task.category.name
            linked_call_task_name = self.task_manager.data['linkage_manager'].get_linked_call(task)
            task_math_tasks = []

            for week_start in self.math_tasks[task.name]:
                task_math_tasks.extend(self.math_tasks[task.name][week_start])

            # Handle tasks (both multi-week and single-week)
            task_blocks = self._group_math_tasks_into_blocks(task, task_math_tasks)

            for block in task_blocks:
                logging.debug(f"Processing task block for {task.name} starting on {block[0].start_date}")

                # Get eligible physicians
                eligible_physicians = self._get_eligible_physicians_for_block(block, task)

                if not eligible_physicians:
                    if task.mandatory:
                        logging.warning(f"No eligible physicians for mandatory task {task.name} starting on {block[0].start_date}")
                        self._log_constraint_info(task.name, None, "NoEligiblePhysicians", block[0].start_date, block[-1].end_date)
                    continue

                # Enforce that the same physician is assigned across the block
                vars_per_physician = {
                    physician: [self.y[(task.name, mt.start_date, mt.end_date, physician)] for mt in block]
                    for physician in eligible_physicians
                }

                # Single assignment per block
                total_vars = [vars[0] for vars in vars_per_physician.values()]
                if task.mandatory:
                    constraint = self.math_model.Add(sum(total_vars) == 1)
                    logging.debug(f"Added constraint: {constraint.Name()} for mandatory task {task.name}")
                else:
                    constraint = self.math_model.Add(sum(total_vars) <= 1)
                    logging.debug(f"Added constraint: {constraint.Name()} for optional task {task.name}")
                constraints_added += 1

                for physician, vars in vars_per_physician.items():
                    # Enforce the same physician across weeks
                    for j in range(len(vars) - 1):
                        constraint = self.math_model.Add(vars[j] == vars[j + 1])
                        constraints_added += 1
                        logging.debug(f"Added constraint: {constraint.Name()} to enforce same physician for {task.name}")
                    # Prevent overlapping assignments
                    self._prevent_overlapping_assignments(physician, block, vars, physician_task_intervals)
                    # Add to physician intervals
                    physician_task_intervals[physician].append((block[0].start_date, block[-1].end_date, task.name))
                    

                    # Handle linked call tasks
                    if linked_call_task_name:
                        self._handle_linked_call_tasks(physician, task, block, linked_call_task_name, all_math_tasks_dict, vars)

        logging.info(f"Added {constraints_added} assignment constraints")
    
    def _group_math_tasks_into_blocks(self, task, task_math_tasks):
        """
        Group MathTasks into blocks based on task duration.

        Args:
            task: The Task object.
            task_math_tasks: List of MathTask objects for the task.

        Returns:
            List of blocks, where each block is a list of MathTask objects.
        """
        blocks = []
        if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK and task.number_of_weeks > 1:
            task_math_tasks.sort(key=lambda x: x.start_date)
            i = 0
            while i <= len(task_math_tasks) - task.number_of_weeks:
                block = task_math_tasks[i:i + task.number_of_weeks]
                # Verify consecutive weeks
                is_consecutive = all(
                    (block[j + 1].start_date - block[j].start_date).days == 7
                    for j in range(len(block) - 1)
                )
                if is_consecutive:
                    blocks.append(block)
                    i += task.number_of_weeks
                else:
                    i += 1
        else:
            # Each MathTask is its own block
            for mt in task_math_tasks:
                blocks.append([mt])
        return blocks
    
    def _get_eligible_physicians_for_block(self, block, task):
        """
        Get physicians who are available and eligible for all MathTasks in the block.

        Args:
            block: List of MathTask objects.
            task: The Task object.

        Returns:
            List of eligible physician names.
        """
        all_physicians = self._get_all_physicians()
        eligible_physicians = []
        for physician in all_physicians:
            is_available = all(
                not self.physician_manager.is_unavailable(physician, day)
                for mt in block for day in mt.days
            )
            is_eligible = self._is_physician_eligible(physician, task)
            if is_available and is_eligible:
                eligible_physicians.append(physician)
        return eligible_physicians
    
    def _prevent_overlapping_assignments(self, physician, block, vars_for_physician, physician_task_intervals):
        """
        Prevent overlapping assignments for a physician.

        Args:
            physician: Physician name.
            block: List of MathTask objects.
            vars_for_physician: List of variables corresponding to the block for the physician.
            physician_task_intervals: Dict mapping physician to their task intervals.
        """
        if isinstance(vars_for_physician, list):
            # If it's a list (for multi-week tasks), use the first variable
            y_var = vars_for_physician[0]
        else:
            # If it's a single variable (for single-week tasks), use it directly
            y_var = vars_for_physician
    
        for math_task in enumerate(block):
            start_date = math_task[1].start_date
            end_date = math_task[1].end_date
            for other_task_period in physician_task_intervals[physician]:
                if self._intervals_overlap((start_date, end_date), other_task_period):
                    other_y_var = self.y.get((other_task_period[2], other_task_period[0], other_task_period[1], physician))
                    if other_y_var is not None:  # Check if the variable exists
                        self.math_model.Add(y_var + other_y_var <= 1)
                        logging.debug(f"Added constraint to prevent overlapping assignments for {physician}")
        
            physician_task_intervals[physician].append((block[0].start_date, block[-1].end_date, block[0].name))

    def _handle_linked_call_tasks(self, physician, task, block, linked_call_task_name, all_math_tasks_dict, vars_for_physician):
        """
        Handle the linkage of main and call tasks.

        Args:
            physician: Physician name.
            task: The main Task object.
            block: List of MathTask objects (main tasks).
            linked_call_task_name: Name of the linked call task.
            all_math_tasks_dict: Dictionary of all MathTasks per task name.
            y_var: The assignment variable for the physician and the main task block.
        """
        if task.category.days_parameter == TaskDaysParameter.MULTI_WEEK and task.number_of_weeks > 1:
            # For multi-week tasks, use the multiweek method
            call_math_tasks = self._get_linked_call_math_tasks_multiweek(block, linked_call_task_name, all_math_tasks_dict, task.category.name)
        else:
            # For single-week tasks, use the existing method
            call_math_tasks = self._get_linked_call_math_tasks(block[0], linked_call_task_name, all_math_tasks_dict, task.category.name)

        for call_mt in call_math_tasks:
            call_var = self.y[(call_mt.name, call_mt.start_date, call_mt.end_date, physician)]
            for main_var in vars_for_physician:
                constraint = self.math_model.Add(call_var == main_var)
                logging.debug(f"Added constraint: {constraint.Name()} to link call task {call_mt.name} to main task {task.name} for {physician}")

    def _get_linked_call_math_tasks_multiweek(self, math_task_block, call_task_name, all_math_tasks_dict, task_category_name):
        """
        Get the linked call MathTasks appropriate to a multi-week main task.

        Args:
            math_task_block: List of MathTask objects representing the multi-week main task.
            call_task_name: Name of the linked call task.
            all_math_tasks_dict: Dictionary of all MathTasks per task name.
            task_category_name: Name of the task category.

        Returns:
            List of appropriate linked call MathTasks.
        """
        call_math_tasks = []
        main_start_date = math_task_block[0].start_date
        main_end_date = math_task_block[-1].end_date

        if task_category_name == 'CTU':
            # For CTU, call can be before or between the two weeks
            for call_math_task in all_math_tasks_dict[call_task_name]:
                if (abs((call_math_task.start_date - main_start_date).days) <= 7 or
                        0 <= (call_math_task.start_date - main_end_date).days <= 7):
                    call_math_tasks.append(call_math_task)
        else:
            # For other tasks, call must follow the main task
            for call_math_task in all_math_tasks_dict[call_task_name]:
                if 0 <= (call_math_task.start_date - main_end_date).days <= 2:
                    call_math_tasks.append(call_math_task)

        return call_math_tasks


    def _calculate_max_total_workload(self):
        """
        Calculate the maximum total workload for a physician.
        This could be based on the total number of tasks, their heaviness, and the scheduling period.
        """
        total_weeks = (self.scheduling_period[1] - self.scheduling_period[0]).days // 7
        max_heaviness = max(task.heaviness for task in self.task_manager.data['tasks'])
        max_workload = total_weeks * max_heaviness * 1.2  # Adding 20% buffer

        logging.info(f"Calculated max total workload: {max_workload}")
        return int(max_workload)

    def _math_create_workload_constraints(self):
        """
        Add constraints to limit the total workload assigned to each physician.
        """
        all_physicians = self._get_all_physicians()
        max_total_workload = self._calculate_max_total_workload()

        for physician in all_physicians:
            total_workload = []
            for task in self.task_manager.data['tasks']:
                for week_start in self.math_tasks[task.name]:
                    for math_task in self.math_tasks[task.name][week_start]:
                        total_workload.append(
                            self.y[(task.name, math_task.start_date, math_task.end_date, physician)] * math_task.heaviness
                        )

            self.math_model.Add(
                sum(total_workload) <= max_total_workload
            ).WithName(f"WorkloadLimit_{physician}")

    def _math_create_desired_working_weeks_constraints(self):
        """
        Add constraints to ensure physicians' desired working weeks are considered.
        """
        total_weeks = int((self.scheduling_period[1] - self.scheduling_period[0]).days / 7)
        all_physicians = self._get_all_physicians()

        for physician in all_physicians:
            physician_obj = self.physician_manager.get_physician_by_name(physician)
            desired_weeks = int(physician_obj.desired_working_weeks * total_weeks)
            total_assigned_weeks = []

            for task in self.task_manager.data['tasks']:
                for week_start in self.math_tasks[task.name]:
                    for math_task in self.math_tasks[task.name][week_start]:
                        weeks_in_task = int((math_task.end_date - math_task.start_date).days / 7)
                        total_assigned_weeks.append(
                            self.y[(task.name, math_task.start_date, math_task.end_date, physician)] * weeks_in_task
                        )

            # Allow a small deviation (e.g., 1 week) for flexibility
            self.math_model.Add(
                sum(total_assigned_weeks) <= desired_weeks + 1
            ).WithName(f"MaxWorkingWeeks_{physician}")

            self.math_model.Add(
                sum(total_assigned_weeks) >= desired_weeks - 1
            ).WithName(f"MinWorkingWeeks_{physician}")

    def _get_main_math_tasks(self, call_math_task, main_main_task_names, tasks_dict, call_follows_main):
        """
        Collect the MAIN math tasks from a given dict that are appropriate to one CALL math task.

        Args:
            call_math_task (MathTask): The call task for which to find main tasks.
            main_main_task_names (List[str]): List of linked MAIN task names.
            tasks_dict (Dict): Dictionary of all MathTasks.
            call_follows_main (bool): If True, consider only main tasks that precede the call task.

        Returns:
            List[MathTask]: A list of MAIN MathTasks that are appropriate for the CALL MathTask.
        """
        main_math_tasks_set = set()

        call_start_date = call_math_task.start_date
        call_end_date = call_math_task.end_date

        for main_task_name in main_main_task_names:
            main_math_tasks = tasks_dict[main_task_name]
            for main_math_task in main_math_tasks:
                main_start_date = main_math_task.start_date
                main_end_date = main_math_task.end_date

                if call_follows_main:
                    # Call must follow main task
                    # Check if main task ends just before call task starts (within 0 to 1 days)
                    if 0 <= (call_start_date - main_end_date).days <= 1:
                        main_math_tasks_set.add(main_math_task)
                else:
                    # For 'CTU', call can precede or follow main task
                    # Check if main task is within 2 days before or after call task
                    if abs((main_start_date - call_end_date).days) <= 2 or abs((main_end_date - call_start_date).days) <= 2:
                        main_math_tasks_set.add(main_math_task)

        return list(main_math_tasks_set)

    def _get_call_math_tasks(self, main_math_tasks_list, call_task_name, tasks_dict):
        """
        Collect the CALL math tasks from a given dict that are "close" to some MAIN math task given in a list.

        Warnings:
            The dict with the `MathTasks` is supposed to be ordered by start dates.

        Args:
            main_math_tasks_list:
            call_task_name (str): The name of the CALL `MathTask`.
            tasks_dict:

        Returns:
            A list of CALL `MathTask` that are "close" to the MAIN `MathTasks`.
        """
        call_math_tasks_set = set()
        all_call_math_tasks_list = tasks_dict[call_task_name]

        # TODO: optimize the loops so to not look further a given date and reduce the test for the first dates
        for main_math_task in main_math_tasks_list:
            start_date = main_math_task.start_date
            end_date = main_math_task.end_date
            for call_math_task in all_call_math_tasks_list:
                if abs((call_math_task.start_date - end_date).days) <= 2 or abs((call_math_task.end_date - start_date).days) <= 2:
                    call_math_tasks_set.add(call_math_task)

        return list(call_math_tasks_set)

    def _intervals_overlap(self, interval1, interval2):
        """
        Check if two intervals overlap.

        Args:
            interval1: Tuple (start_date1, end_date1).
            interval2: Tuple (start_date2, end_date2).

        Returns:
            True if intervals overlap, False otherwise.
        """
        return interval1[0] <= interval2[1] and interval2[0] <= interval1[1]

    def _get_linked_call_math_tasks(self, main_math_task, call_task_name, all_math_tasks_dict, task_category_name):
        """
        Get the linked call MathTasks appropriate to the main MathTask.

        Args:
            main_math_task: MathTask object of the main task.
            call_task_name: Name of the linked call task.
            all_math_tasks_dict: Dictionary of all MathTasks per task name.
            task_category_name: Name of the task category.

        Returns:
            List of appropriate linked call MathTasks.
        """
        call_math_tasks = []
        if task_category_name == 'CTU':
            # For CTU, call can be before or between the two weeks
            for call_math_task in all_math_tasks_dict[call_task_name]:
                if abs((call_math_task.start_date - main_math_task.start_date).days) <= 7 or \
                0 <= (call_math_task.start_date - main_math_task.end_date).days <= 7:
                    call_math_tasks.append(call_math_task)
        else:
            # For other tasks, call must follow the main task
            for call_math_task in all_math_tasks_dict[call_task_name]:
                if 0 <= (call_math_task.start_date - main_math_task.end_date).days <= 2:
                    call_math_tasks.append(call_math_task)
        return call_math_tasks

    def _create_mutually_exclusive_math_tasks_constraints(self, A, B):
        """
        Add mutually exclusive constraints between two ordered lists of `MathTask`s.

        Warnings:
            This is done for all physicians, whether they participate in a `MathTask` or not.
            This is done in O(len(A) + len(B)).

        Args:
            A (List[MathTask]):
            B (List[MathTask]):
        """
        all_physicians = self._get_all_physicians()
        i = j = 0
        while i < len(A) and j < len(B):
            # Let's check if A[i] intersects B[j].
            # lo - the startpoint of the intersection
            # hi - the endpoint of the intersection
            lo = max(A[i].start_date, B[j].start_date)
            hi = min(A[i].end_date, B[j].end_date)
            if lo <= hi:
                # both interval intersect => add a mutually exclusive constraint for all physicians
                for physician in all_physicians:
                    self.math_model.add(A[i].y_var(physician) + B[j].y_var(physician) <= 1).with_name("zizo")

            # Remove the interval with the smallest endpoint
            if A[i].end_date < B[j].end_date:
                i += 1
            else:
                j += 1

    def _get_preference_score(self, physician_obj, task):
        # Base score
        score = 1

        # Increase score if task is in physician's preferred tasks
        if task.category.name in physician_obj.preferred_tasks:
            score += 5

        # Decrease score if task is heavy and physician has recently had heavy tasks
        # Implement logic as needed

        return score

    def _math_create_objective_function(self):
        """
        Create an objective function that maximizes total weighted preferences.
        """
        
        #available_physicians = self._get_available_physicians(call_math_task.days)
        #eligible_physicians = self._get_eligible_physicians(available_physicians, all_tasks_dict[call_task_name])
        all_physicians = self._get_all_physicians()
        total_score = []

        for physician in all_physicians:
            physician_obj = self.physician_manager.get_physician_by_name(physician)
            for task in self.task_manager.data['tasks']:
                preference_score = self._get_preference_score(physician_obj, task)
                for week_start in self.math_tasks[task.name]:
                    for math_task in self.math_tasks[task.name][week_start]:
                        total_score.append(
                            self.y[(task.name, math_task.start_date, math_task.end_date, physician)] * preference_score
                        )
        objective = sum(total_score)
        self.math_model.Maximize(sum(total_score))
        logging.info(f"Created objective function with {len(total_score)} terms")

    def export_model(self, filename):
        self.math_model.export_to_file(filename)

    def _math_set_solution(self, periods):
        """
        Translate the mathematical solution into a schedule.

        Args:
            periods:
        """
        solver = self.math_solver

        # init solution schedule
        self.schedule = defaultdict(list)

        for week_start, week_periods in periods.items():
            for task in self.task_manager.data['tasks']:
                task_category = task.category  # for later
                if week_start not in self.math_tasks[task.name]:
                    continue
                for index, math_task in enumerate(self.math_tasks[task.name][week_start]):
                    available_physicians = self._get_all_physicians()
                    for physician in available_physicians:
                        if solver.value(self.y[(task.name, math_task.start_date, math_task.end_date, physician)]) > 0:
                            self._add_to_schedule(
                                physician=physician,
                                task=task,
                                period={"days": math_task.days},
                                score=0  # TODO: add right score
                            )

    def _handle_extended_tasks(self, extended_end_date: date):
        for task in self.task_manager.data['tasks']:
            if task.number_of_weeks > 1:
                last_assigned = max(
                    (t['end_date'] for t in self.schedule.values() for t in t if t['task'].name == task),
                    default=None)
                if last_assigned and last_assigned < extended_end_date:
                    remaining_weeks = (extended_end_date - last_assigned).days // 7
                    for week in range(remaining_weeks):
                        start_date = last_assigned + timedelta(weeks=week + 1)
                        end_date = start_date + timedelta(days=6)
                        period = {'days': [start_date + timedelta(days=i) for i in range(7)], 'month': start_date.month}
                        available_physicians = self._get_available_physicians(period['days'])
                        self._assign_main_task(start_date, period, available_physicians, task)

    def _extend_scheduling_period(self) -> date:
        """
        Extends the scheduling period based on the maximum task duration.
        
        Returns:
            date: The extended end date for the scheduling period.
        """
        max_task_duration = max(task.number_of_weeks for task in self.task_manager.data['tasks'])
        extended_end_date = self.scheduling_period[1] + timedelta(weeks=max_task_duration)
        return extended_end_date

    def _filter_relevant_periods(self, periods: Dict[str, List[Dict[str, Any]]], start_date: date, end_date: date) -> \
    Dict[str, List[Dict[str, Any]]]:
        """
        Filter periods based on the given start and end dates using date.fromisoformat().

        Args:
            periods (Dict[str, List[Dict[str, Any]]]): Dictionary of periods with week start dates as keys.
            start_date (date): The start date for filtering.
            end_date (date): The end date for filtering.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Filtered periods dictionary.

        Raises:
            ValueError: If an invalid date format is encountered in the periods dictionary.
        """
        filtered_periods = {}

        for week_start, week_periods in periods.items():
            try:
                week_date = date.fromisoformat(week_start)
                if start_date <= week_date <= end_date:
                    filtered_periods[week_start] = week_periods
            except ValueError:
                raise ValueError(f"Invalid ISO format date in periods dictionary: {week_start}")

        return filtered_periods

    def _assign_tasks_for_period(self, week_start: date, periods: List[Dict[str, Any]]):
        for task in self.task_manager.data['tasks']:
            if task.type == TaskType.MAIN:
                if main_period := self._get_main_candidate(periods):
                    available_physicians = self._get_available_physicians(main_period['days'])
                    assigned_physician = self._assign_main_task(week_start, main_period, available_physicians, task)

                    if assigned_physician:
                        # Assign linked call task immediately after main task
                        linked_call_task_name = self.task_manager.data['linkage_manager'].get_linked_call(task)
                        linked_call_task = next(
                            (t for t in self.task_manager.data['tasks'] if t.name == linked_call_task_name), None)

                        if linked_call_task:
                            call_period = self._get_call_candidate(periods)
                            if call_period:
                                self._assign_linked_call_task(week_start, call_period, assigned_physician,
                                                              linked_call_task)

        # Handle remaining unassigned call tasks
        for task in self.task_manager.data['tasks']:
            if task.type == TaskType.CALL and task.name not in self.task_manager.data['linkage_manager'].links.values():
                if call_period := self._get_call_candidate(periods):
                    available_physicians = self._get_available_physicians(call_period['days'])
                    self._assign_call_task(week_start, call_period, available_physicians, task)

    def _assign_main_task(self, week_start: date, period: Dict[str, Any], available_physicians: List[str], task):
        period['month'] = week_start.month
        physician, score = self.task_matcher.find_best_match(available_physicians, task, period, week_start.month)
        if physician:
            for week in range(task.number_of_weeks):
                current_period = self._get_period_for_date(week_start + timedelta(weeks=week), 'MAIN')
                if current_period is None:
                    logging.debug(f"Only CALL periods found for {week_start + timedelta(weeks=week)}")
                else:
                    if not self._is_task_already_assigned(task, current_period) and not self._is_physician_already_assigned(physician, current_period):
                        self._add_to_schedule(physician, task, current_period, score)
                        self.task_matcher.update_physician_stats(physician, task, current_period)
                    else:
                        logging.debug(f"Task {task.name} is already assigned during {current_period['days']} or physician {physician} is already assigned another task")
            if physician in available_physicians:
                available_physicians.remove(physician)
            logging.debug(f"Assigned main task {task.name} to {physician} for {task.number_of_weeks} weeks")
            return physician
        else:
            logging.debug(f"No eligible physician found for main task {task.name}")
            return None

    def _assign_linked_call_task(self, week_start: date, period: Dict[str, Any], physician: str, task):
        if not self._is_task_already_assigned(task, period) and not self._is_physician_already_assigned(physician, period):
            if 'month' not in period:
                period['month'] = period['days'][0].month
            if self.assigned_calls[physician][period['month']] == 0:
                self._add_to_schedule(physician, task, period, 0)
                self.task_matcher.update_physician_stats(physician, task, period)
                self.assigned_calls[physician][period['month']] += 1
                logging.debug(f"Assigned linked call task {task.name} to {physician}")
            else:
                logging.debug(f"Unable to assign linked call task {task.name} to {physician} due to monthly call limit")
        else:
            logging.debug(f"Unable to assign linked call task {task.name} to {physician} due to conflicts")

    def _assign_call_task(self, week_start: date, period: Dict[str, Any], available_physicians: List[str], task):
        period['month'] = week_start.month
        physician, score = self.task_matcher.find_best_match(available_physicians, task, period, week_start.month)
        if physician:
            if not self._is_task_already_assigned(task, period) and not self._is_physician_already_assigned(physician, period):
                if self.assigned_calls[physician][period['month']] == 0:
                    self._add_to_schedule(physician, task, period, score)
                    available_physicians.remove(physician)
                    self.task_matcher.update_physician_stats(physician, task, period)
                    self.assigned_calls[physician][period['month']] += 1
                    logging.debug(f"Assigned call task {task.name} to {physician}")
                else:
                    logging.debug(f"Unable to assign call task {task.name} to {physician} due to monthly call limit")
            else:
                logging.debug(f"Task {task.name} is already assigned during {period['days']} or physician {physician} is already assigned another task")
        else:
            logging.debug(f"No eligible physician found for call task {task.name}")

    def _is_physician_already_assigned(self, physician: str, period: Dict[str, Any]) -> bool:
        for assigned_task in self.schedule[physician]:
            if any(day in period['days'] for day in assigned_task['days']):
                return True
        return False

    def _is_task_already_assigned(self, task: Any, period: Dict[str, Any]) -> bool:
        for physician, tasks in self.schedule.items():
            for assigned_task in tasks:
                if assigned_task['task'].name == task.name and any(day in period['days'] for day in assigned_task['days']):
                    return True
        return False
    def _get_period_for_date(self, date: date, type = str) -> Dict[str, Any]:
        """
        Returns the period dictionary for a given date.
        """
        logging.debug(f"Getting period for date {date}")
        try:
            periods = self.calendar.determine_periods()
            date_string = date.strftime('%Y-%m-%d')
            candidates = periods[date_string]
            return self._get_call_candidate(candidates) if type == 'CALL' else self._get_main_candidate(candidates)
        except:
            raise ValueError(f"No period found for date: {date}")

    def _get_call_candidate(self, candidates):
        return next((candidate for candidate in candidates if candidate['type'] == 'CALL'), None)

    def _get_main_candidate(self, candidates):
        return next((candidate for candidate in candidates if candidate['type'] == 'MAIN'), None)

    def _get_other_constraints_physician(self):
        #TODO: implement
        # if task.is_call_task and self.physician_call_counts[physician][period['month']] > 0:
        # logging.debug(f"Physician {physician} has already been assigned a call task in month {period['month']}")
        # return False

        # if task.is_discontinuous and not physician_obj.discontinuity_preference:
        # logging.debug(f"Physician {physician} does not prefer discontinuous tasks")
        # return False
        pass

    def _get_available_physicians(self, days: List[date]) -> List[str]:
        available_physicians = []
        #logging.debug(f"Checking availability for period: {days[0]} - {days[-1]}")
        
        for physician in self.physician_manager.data['physicians']:
            #logging.debug(f"Checking availability for physician: {physician.name}")
            
            is_available = True
            for day in days:
                if self.physician_manager.is_unavailable(physician.name, day):
                    #logging.debug(f"  {physician.name} is unavailable on {day}")
                    is_available = False
                    break
            
            if is_available:
                available_physicians.append(physician.name)
                #logging.debug(f"  {physician.name} is available for the entire period")
            else:
                pass
                #logging.debug(f"  {physician.name} is unavailable for the period")

        #logging.debug(f"Available physicians for period {days[0]} - {days[-1]}: {available_physicians}")
        return available_physicians
    
    def _get_eligible_physicians(self, available_physicians: List[str], task: Any) -> List[str]:
        return [
            p for p in available_physicians
            if self._is_physician_eligible(p, task)
        ]
    def _is_physician_eligible(self, physician: str, task: Any) -> bool:
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        # if task.name in physician_obj.restricted_tasks or t
        if task.category.name in physician_obj.exclusion_tasks:
            return False
        return True

    def _get_all_physicians(self):
        return [
            physician.name
            for physician in self.physician_manager.data['physicians']
        ]

    def _get_all_tasks(self):
        return [t for t in self.task_manager.data['tasks']]
    def _add_to_schedule(self, physician: str, task: Any, period: Dict[str, Any], score: float):
        self.schedule[physician].append({
            'task': task,
            'days': period['days'],
            'start_date': period['days'][0],
            'end_date': period['days'][-1],
            'score': score
        })


    def get_schedule(self) -> Dict[str, List[Dict[str, Any]]]:
        return dict(self.schedule)

    def print_schedule(self):
        for physician, tasks in self.schedule.items():
            print(f"\n{physician}:")
            for task in tasks:
                print(f"  {task['task'].name}: {task['start_date']} - {task['end_date']} (Score: {task['score']:.2f})")

    def check_conflicts(self):
        conflicts = []
        for physician, tasks in self.schedule.items():
            sorted_tasks = sorted(tasks, key=lambda x: x['start_date'])
            for i in range(len(sorted_tasks) - 1):
                if sorted_tasks[i]['end_date'] >= sorted_tasks[i + 1]['start_date']:
                    conflicts.append(
                        f"Conflict for {physician}: {sorted_tasks[i]['task'].name} and {sorted_tasks[i + 1]['task'].name} overlap")
        return conflicts

    def save_schedule(self, filename):
        serializable_schedule = {
            physician: [
                {**task, 'task': task['task'].name}
                for task in tasks
            ]
            for physician, tasks in self.schedule.items()
        }

        with open(filename, 'w') as f:
            json.dump(serializable_schedule, f, indent=2, default=str)

    def load_schedule(self, filename):
        """
        Load schedule from a JSON file.

        Raises:
            AssertionError is the JSON format is not respected.

        Args:
            filename:
        """
        self.schedule = self._load_schedule_from_file(filename=filename)

    def get_statistics(self):
        stats = {}
        for physician, tasks in self.schedule.items():
            physician_stats = defaultdict(int)
            total_days = 0
            for task in tasks:
                physician_stats[task['task'].name] += 1
                total_days += (task['end_date'] - task['start_date']).days + 1

            working_weeks = total_days / 7
            physician_obj = self.physician_manager.get_physician_by_name(physician)
            desired_weeks_met = working_weeks >= physician_obj.desired_working_weeks * 52

            stats[physician] = {
                'task_counts': dict(physician_stats),
                'total_working_days': total_days,
                'working_weeks': working_weeks,
                'desired_weeks_met': desired_weeks_met
            }
        return stats

    def get_unassigned_tasks(self):
        all_tasks = set(task.name for task in self.task_manager.data['tasks'])
        assigned_tasks = set(task['task'].name for tasks in self.schedule.values() for task in tasks)
        return all_tasks - assigned_tasks

    def generate_ics_calendar(self, filename):
        cal = IcsCalendar()
        for physician, tasks in self.schedule.items():
            for task in tasks:
                event = Event()
                event.name = f"{task['task'].name} - {physician}"
                event.begin = task['start_date'].isoformat()
                event.end = (task['end_date'] + timedelta(days=1)).isoformat()  # End date should be exclusive
                event.description = f"Task: {task['task'].name}\nPhysician: {physician}\nScore: {task['score']}"
                cal.events.add(event)

        with open(filename, 'w') as f:
            f.writelines(cal)
