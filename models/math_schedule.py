import datetime
from datetime import date, timedelta
from typing import Dict, List, Any, Tuple
from collections import defaultdict
from ics import Calendar as IcsCalendar, Event
import json
import logging
from models.task import TaskType, TaskDaysParameter, Task
import random
from ortools.sat.python import cp_model

logging.basicConfig(level=logging.DEBUG)

class MathTask:
    """
    Represents a mathematical task that is the basic unit in the mathematical model.
    """

    def __init__(self, name, task_type, y_vars, index, week_start, days, start_date, end_date, number_of_weeks, available_physicians, heaviness, mandatory):
        self.name = name
        assert isinstance(task_type, TaskType)
        self.task_type = task_type
        self.y_vars = y_vars
        self.index = index
        self.week_start = week_start
        self.days = days
        assert start_date == days[0]
        self.start_date = start_date
        assert end_date == days[-1]
        self.end_date = end_date
        self.number_of_weeks = number_of_weeks
        self.available_physicians = available_physicians
        self.heaviness = heaviness
        self.mandatory = mandatory

    def y_var(self, physician):
        """
        Return the variable for the given physician.
        """
        return self.y_vars[(self.name, self.start_date, self.end_date, physician)]

    def is_physician_available(self, physician):
        """
        Returns if physician is available or not.
        """
        return physician in self.available_physicians

    def __str__(self):
        return f"{self.name} [{self.start_date}, {self.end_date}]"

    def __repr__(self):
        return str(self)


class MathSchedule:
    # SCORING WEIGHTS
    PREFERENCE_SCORE = 10
    DESIRED_WEEKS_SCORE = 100
    REVENUE_BALANCE_SCORE = 5
    CONSECUTIVE_CATEGORY_PENALTY = -10
    CALL_DISTRIBUTION_PENALTY = -10
    HEAVY_TASK_PENALTY = -10

    def __init__(self, physician_manager, task_manager, calendar):
        self.physician_manager = physician_manager
        self.task_manager = task_manager
        self.calendar = calendar
        self.scheduling_period = None
        self.task_splits = {}
        self.schedule = defaultdict(list)
        self.off_days = {}
        self.assigned_calls = defaultdict(lambda: defaultdict(int))
        self.slack_vars = []
        self.revenue_per_physician = defaultdict(float)
        self.physician_assignments = defaultdict(list)
        self.physician_call_assignments = defaultdict(list)
        self.debug_info = {
            'math_tasks': {},
            'constraints': {
                'mandatory_task': {},
                'non_simultaneous': {},
                'linked_main_call': {}
            }
        }
        logging.debug("Schedule initialized")

    def set_scheduling_period(self, start_date: date, end_date: date):
        self.scheduling_period = (start_date, end_date)
        logging.debug(f"Scheduling period set to {self.scheduling_period}")

    def set_task_splits(self, task_splits: Dict[str, Dict[str, str]]):
        self.task_splits = task_splits
        logging.debug(f"Task splits set to {self.task_splits}")

    def set_off_days(self, off_days: Dict[str, List[date]]):
        self.off_days = off_days
        logging.debug(f"Off days set to {self.off_days}")

    def generate_schedule(self, use_initial_schedule=False):
        """
        Generate a schedule given all the instance information.
        """
        if not self.scheduling_period:
            raise ValueError("Scheduling period must be set before generating schedule")

        logging.info("Starting schedule generation...")
        extended_end_date = self._extend_scheduling_period()
        periods = self.calendar.determine_periods()
        relevant_periods = self._filter_relevant_periods(periods, self.scheduling_period[0], extended_end_date)

        self.math_model = cp_model.CpModel()

        self._math_create_variables(periods=relevant_periods)
        self._math_create_constraints(periods=relevant_periods)
        self._math_create_objective_function()

        self.save_debug_info("debug_info.json")

        if use_initial_schedule:
            self._math_load_initial_schedule()

        self.math_solver = cp_model.CpSolver()
        status = self.math_solver.Solve(self.math_model)

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logging.info(f"Solution found with status: {cp_model.CpSolver.status_name(self.math_solver)}")
            self._math_set_solution(periods=relevant_periods)
        else:
            logging.info("Schedule infeasible")
            self.math_model.ExportToFile("infeasible_model.pb.txt")

        logging.debug("Schedule generation completed")

    def _extend_scheduling_period(self) -> date:
        max_task_duration = max(task.number_of_weeks for task in self.task_manager.data['tasks'])
        return self.scheduling_period[1] + timedelta(weeks=max_task_duration)

    def _filter_relevant_periods(self, periods: Dict[str, List[Dict[str, Any]]], start_date: date, end_date: date) -> Dict[str, List[Dict[str, Any]]]:
        return {
            week_start: week_periods
            for week_start, week_periods in periods.items()
            if start_date <= date.fromisoformat(week_start) <= end_date
        }

    def _math_create_variables(self, periods):
        """
        Create the mathematical variables.
        """
        self.y = {}
        self.math_tasks = {}
        for task in self.task_manager.data['tasks']:
            self.math_tasks[task.name] = {}

        all_physicians = self._get_all_physicians()

        for week_start, week_periods in periods.items():
            main_periods_days, call_periods_days = self._get_periods_days(week_periods)

            for task in self.task_manager.data['tasks']:
                self.math_tasks[task.name][week_start] = []

                if task.type == TaskType.MAIN:
                    self._create_main_task_variables(task, week_start, main_periods_days, all_physicians)
                elif task.type == TaskType.CALL:
                    self._create_call_task_variables(task, week_start, call_periods_days, all_physicians)

    def _create_main_task_variables(self, task, week_start, main_periods_days, all_physicians):
        for index, main_period_days in enumerate(main_periods_days):
            available_physicians = self._get_available_physicians(main_period_days)
            random.shuffle(available_physicians)
            
            start_date = main_period_days[0]
            end_date = main_period_days[-1]

            self._create_math_task(task, week_start, index, main_period_days, start_date, end_date, available_physicians)
            self._create_assignment_variables(task, start_date, end_date, all_physicians)

    def _create_call_task_variables(self, task, week_start, call_periods_days, all_physicians):
        for index, call_period_days in enumerate(call_periods_days):
            available_physicians = self._get_available_physicians(call_period_days)
            random.shuffle(available_physicians)

            start_date = call_period_days[0]
            end_date = call_period_days[-1]

            self._create_math_task(task, week_start, index, call_period_days, start_date, end_date, available_physicians)
            self._create_assignment_variables(task, start_date, end_date, all_physicians)

    def _create_math_task(self, task, week_start, index, period_days, start_date, end_date, available_physicians):
        self.math_tasks[task.name][week_start].append(
            MathTask(
                name=task.name,
                task_type=task.type,
                y_vars=self.y,
                index=index,
                week_start=week_start,
                days=period_days,
                start_date=start_date,
                end_date=end_date,
                number_of_weeks=task.number_of_weeks,
                available_physicians=available_physicians,
                heaviness=task.heaviness,
                mandatory=task.mandatory
            )
        )

    def _create_assignment_variables(self, task, start_date, end_date, all_physicians):
        task_key = f"{task.name}_{start_date}_{end_date}"
        if task_key not in self.debug_info['math_tasks']:
            self.debug_info['math_tasks'][task_key] = {
                'initial_candidates': self._get_all_physicians(),
                'candidates_after_availability': [],
                'candidates_after_eligibility': [],
                'candidates_after_mandatory': [],
                'candidates_after_non_simultaneous': [],
                'candidates_after_linked_call_constraints': []
            }
        for physician in all_physicians:
            var_name = f"{task.name}_{start_date}_{end_date}_{physician}"
            self.y[(task.name, start_date, end_date, physician)] = self.math_model.NewBoolVar(var_name)

    def _math_create_constraints(self, periods):
        week_starts = sorted(periods.keys())
        self._math_create_physician_availability_constraints()
        self._math_create_physician_eligibility_constraints()
        self._math_create_mandatory_task_constraints(week_starts, periods)
        self._math_create_non_simultaneous_tasks(week_starts, periods)
        self._math_create_linked_main_call_tasks_constraints(week_starts, periods)

    def _math_create_physician_availability_constraints(self):
        """
        Add constraints to prevent assignment of tasks to physicians who are unavailable during the task period.
        """
        constraints_added = 0
        for task in self.task_manager.data['tasks']:
            for week_start in self.math_tasks[task.name]:
                for math_task in self.math_tasks[task.name][week_start]:
                    task_key = f"{task.name}_{math_task.start_date}_{math_task.end_date}"
                    available_physicians = []
                    for physician in self._get_all_physicians():
                        is_unavailable = any(
                            self.physician_manager.is_unavailable(physician, day)
                            for day in math_task.days
                        )
                        if is_unavailable:
                            self.math_model.Add(
                                self.y[(task.name, math_task.start_date, math_task.end_date, physician)] == 0
                            ).WithName(f"Unavailable_{physician}_{task.name}_{math_task.start_date}")
                            constraints_added += 1
                        else:
                            available_physicians.append(physician)
                    self.debug_info['math_tasks'][task_key]['candidates_after_availability'] = available_physicians.copy()
        logging.info(f"Added {constraints_added} physician availability constraints")

    def _math_create_physician_eligibility_constraints(self):
        """
        Forbid assigning tasks to physicians who are not eligible to perform them.
        """
        constraints_added = 0
        for task in self.task_manager.data['tasks']:
            for week_start in self.math_tasks[task.name]:
                for math_task in self.math_tasks[task.name][week_start]:
                    task_key = f"{task.name}_{math_task.start_date}_{math_task.end_date}"
                    eligible_physicians = []
                    for physician in self._get_all_physicians():
                        physician_obj = self.physician_manager.get_physician_by_name(physician)
                        if task.category.name in physician_obj.exclusion_tasks:
                            self.math_model.Add(
                                self.y[(task.name, math_task.start_date, math_task.end_date, physician)] == 0
                            ).WithName(f"Ineligible_{physician}_{task.name}_{math_task.start_date}")
                            constraints_added += 1
                        else:
                            eligible_physicians.append(physician)
                    self.debug_info['math_tasks'][task_key]['candidates_after_eligibility'] = eligible_physicians.copy()
        logging.info(f"Added {constraints_added} physician eligibility constraints")

    def _math_create_mandatory_task_constraints(self, week_starts, periods):
        for task in self.task_manager.data['tasks']:
            all_physicians = self._get_all_physicians()
            task_category = task.category
            week_offset = task.week_offset
            number_of_weeks = task_category.number_of_weeks
            period_has_started = False
            for week_nbr, week_start in enumerate(week_starts):
                if (week_nbr + week_offset) % number_of_weeks == 0:
                    period_has_started = True

                if period_has_started:
                    for index, math_task in enumerate(self.math_tasks[task.name][week_start]):
                        available_physicians = self._get_available_physicians(math_task.days)
                        eligible_physicians = self._get_eligible_physicians(available_physicians, task)
                        if eligible_physicians:
                            self.math_model.Add(
                                sum(self.y[(task.name, math_task.start_date, math_task.end_date, physician)]
                                    for physician in eligible_physicians) == 1
                            ).WithName(f"Assign_{task.name}_{math_task.start_date}")
                        else:
                            slack_var = self.math_model.NewBoolVar(f"Slack_{task.name}_{math_task.start_date}")
                            possible_physicians = [
                                physician for physician in self._get_all_physicians()
                                if not self._is_physician_unavailable(physician, math_task.days)
                            ]
                            self.math_model.Add(
                                sum(self.y[(task.name, math_task.start_date, math_task.end_date, physician)]
                                    for physician in possible_physicians) + slack_var == 1
                            ).WithName(f"AssignOrSlack_{task.name}_{math_task.start_date}")
                            self.slack_vars.append(slack_var)

    def _math_create_non_simultaneous_tasks(self, week_starts, periods):
        all_tasks_list = self.task_manager.data['tasks']
        nbr_of_tasks = len(all_tasks_list)
        all_physicians = self._get_all_physicians()

        for i in range(nbr_of_tasks):
            for j in range(i+1, nbr_of_tasks):
                self._create_mutually_exclusive_math_tasks_constraints(
                    self._get_all_math_tasks_per_task(week_starts)[all_tasks_list[i].name],
                    self._get_all_math_tasks_per_task(week_starts)[all_tasks_list[j].name]
                )

    def _create_mutually_exclusive_math_tasks_constraints(self, A, B):
        """
        Add mutually exclusive constraints between two ordered lists of `MathTask`s.
        """
        all_physicians = self._get_all_physicians()
        i = j = 0
        while i < len(A) and j < len(B):
            if A[i].end_date < B[j].start_date:
                i += 1
            elif B[j].end_date < A[i].start_date:
                j += 1
            else:
                for physician in all_physicians:
                    self.math_model.Add(
                        self.y[(A[i].name, A[i].start_date, A[i].end_date, physician)] +
                        self.y[(B[j].name, B[j].start_date, B[j].end_date, physician)] <= 1
                    ).WithName(f"NonOverlap_{physician}_{A[i].name}_{B[j].name}_{A[i].start_date}")
                if A[i].end_date <= B[j].end_date:
                    i += 1
                else:
                    j += 1

    def _math_create_linked_main_call_tasks_constraints(self, week_starts, periods):
        all_tasks_list = self.task_manager.data['tasks']
        all_tasks_dict = {task.name: task for task in all_tasks_list}
        linked_main_tasks = defaultdict(list)
        for main_task_name, call_task_name in self.task_manager.data['linkage_manager'].to_dict().items():
            linked_main_tasks[call_task_name].append(main_task_name)

        all_physicians = self._get_all_physicians()
        all_math_tasks = self._get_all_math_tasks_per_task(week_starts)

        for call_task_name, main_task_names in linked_main_tasks.items():
            all_call_math_tasks = all_math_tasks[call_task_name]

            for call_math_task in all_call_math_tasks:
                self.math_model.Add(
                    sum(call_math_task.y_var(physician) for physician in all_physicians) <= 1).WithName("tqtq")

                main_math_tasks = self._get_main_math_tasks(
                    call_math_task=call_math_task,
                    main_main_task_names=main_task_names,
                    tasks_dict=all_math_tasks
                )

                self._assign_physician_to_call_task(
                    main_math_tasks=main_math_tasks,
                    call_math_task=call_math_task,
                    physicians=all_physicians
                )

            for main_task_name in main_task_names:
                week_offset = all_tasks_dict[main_task_name].week_offset
                number_of_weeks = all_tasks_dict[main_task_name].category.number_of_weeks
                one_main_math_tasks_bundled_list = []
                period_started = False
                nbr_weeks_in_period = 0
                for week_nbr, week_start in enumerate(week_starts):
                    if (week_nbr + week_offset) % number_of_weeks == 0:
                        period_started = True
                        nbr_weeks_in_period = 0

                    if period_started:
                        one_main_math_tasks_bundled_list.extend(self.math_tasks[main_task_name][week_start])
                        nbr_weeks_in_period += 1

                        if nbr_weeks_in_period == number_of_weeks:
                            self._one_physician_for_main_task_period(
                                main_math_tasks=one_main_math_tasks_bundled_list,
                                physicians=all_physicians
                            )
                            one_main_math_tasks_bundled_list = []

    def _math_create_objective_function(self):
        total_score = 0

        for task in self.task_manager.data['tasks']:
            for week_start in self.math_tasks[task.name]:
                for math_task in self.math_tasks[task.name][week_start]:
                    for physician in self._get_all_physicians():
                        var = self.y[(task.name, math_task.start_date, math_task.end_date, physician)]
                        coeff = 0

                        if not self.math_model.Proto().variables[var.Index()].domain == [0]:
                            physician_obj = self.physician_manager.get_physician_by_name(physician)

                            # Task Preferences
                            if task.category.name in physician_obj.preferred_tasks:
                                preference_rank = physician_obj.preferred_tasks.index(task.category.name)
                                coeff += self.PREFERENCE_SCORE * (len(physician_obj.preferred_tasks) - preference_rank)

                            # Consecutive Category Avoidance
                            last_tasks = self.physician_assignments.get(physician, [])
                            if last_tasks:
                                last_task = last_tasks[-1]
                                if last_task.category.name == task.category.name and task.number_of_weeks <= 1:
                                    coeff += self.CONSECUTIVE_CATEGORY_PENALTY

                            # Call Distribution
                            if task.is_call_task:
                                last_calls = self.physician_call_assignments.get(physician, [])
                                if last_calls:
                                    last_call_date = last_calls[-1].start_date
                                    if (math_task.start_date - last_call_date).days <= 28:
                                        coeff += self.CALL_DISTRIBUTION_PENALTY

                            # Heavy Task Avoidance
                            if task.is_heavy and task.number_of_weeks <= 1:
                                if last_tasks and last_tasks[-1].is_heavy:
                                    coeff += self.HEAVY_TASK_PENALTY

                            # Add to total_score
                            total_score += coeff * var

        # Balance Desired Working Weeks
        for physician in self._get_all_physicians():
            physician_obj = self.physician_manager.get_physician_by_name(physician)
            assigned_weeks = sum(
                ((task['end_date'] - task['start_date']).days + 1) / 7
                for task in self.schedule.get(physician, [])
            )
            desired_weeks = physician_obj.desired_working_weeks * 52
            deviation = abs(assigned_weeks - desired_weeks)
            total_score += self.DESIRED_WEEKS_SCORE * -deviation

        # Balance Revenue Distribution
        total_revenue = sum(self.revenue_per_physician.values())
        num_physicians = len(self._get_all_physicians())
        average_revenue = total_revenue / num_physicians if num_physicians > 0 else 0

        for physician in self._get_all_physicians():
            revenue = self.revenue_per_physician[physician]
            deviation = abs(revenue - average_revenue)
            total_score += self.REVENUE_BALANCE_SCORE * -deviation

        # Penalty for slack variables
        total_slack_penalty = sum(self.slack_vars) * -100000

        # Set the objective
        self.math_model.Maximize(total_score + total_slack_penalty)

    def _math_set_solution(self, periods):
        """
        Translate the mathematical solution into a schedule.
        """
        solver = self.math_solver
        self.schedule = defaultdict(list)

        for week_start, week_periods in periods.items():
            for task in self.task_manager.data['tasks']:
                for math_task in self.math_tasks[task.name][week_start]:
                    available_physicians = self._get_available_physicians(math_task.days)
                    for physician in available_physicians:
                        if solver.Value(self.y[(task.name, math_task.start_date, math_task.end_date, physician)]) > 0:
                            self._add_to_schedule(
                                physician=physician,
                                task=task,
                                period={"days": math_task.days},
                                score=self._calculate_assignment_score(physician, task, math_task)
                            )
                            self.physician_assignments[physician].append(task)
                            if task.is_call_task:
                                self.physician_call_assignments[physician].append(math_task)
                            self.revenue_per_physician[physician] += task.revenue

    def _calculate_assignment_score(self, physician: str, task: Any, math_task: Any) -> float:
        """
        Calculate a comprehensive score for a task assignment.
        """
        physician_obj = self.physician_manager.get_physician_by_name(physician)
        score = 0

        # Task Preference Score
        if task.category.name in physician_obj.preferred_tasks:
            preference_rank = physician_obj.preferred_tasks.index(task.category.name)
            score += self.PREFERENCE_SCORE * (len(physician_obj.preferred_tasks) - preference_rank)

        # Desired Working Weeks Score
        total_assigned_days = sum(len(t['days']) for t in self.schedule[physician])
        assigned_weeks = total_assigned_days / 7
        desired_weeks = physician_obj.desired_working_weeks * 52
        weeks_deviation = abs(assigned_weeks - desired_weeks)
        score += self.DESIRED_WEEKS_SCORE * (1 / (weeks_deviation + 1))

        # Revenue Distribution Score
        avg_revenue = sum(self.revenue_per_physician.values()) / len(self.revenue_per_physician) if self.revenue_per_physician else 0
        revenue_deviation = abs(self.revenue_per_physician[physician] - avg_revenue)
        score += self.REVENUE_BALANCE_SCORE * (1 / (revenue_deviation + 1))

        # Consecutive Category Avoidance
        last_tasks = self.physician_assignments.get(physician, [])
        if last_tasks and last_tasks[-1].category.name == task.category.name and task.number_of_weeks <= 1:
            score += self.CONSECUTIVE_CATEGORY_PENALTY

        # Call Distribution
        if task.is_call_task:
            last_calls = self.physician_call_assignments.get(physician, [])
            if last_calls:
                last_call_date = last_calls[-1].start_date
                if (math_task.start_date - last_call_date).days <= 28:
                    score += self.CALL_DISTRIBUTION_PENALTY

        # Heavy Task Avoidance
        if task.is_heavy and task.number_of_weeks <= 1:
            if last_tasks and last_tasks[-1].is_heavy:
                score += self.HEAVY_TASK_PENALTY

        return score

    def _get_periods_days(self, week_periods):
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
        math_tasks_dict = {}
        for task in self.task_manager.data['tasks']:
            math_tasks_dict[task.name] = []
        for week_start in week_starts:
            for task in self.task_manager.data['tasks']:
                math_tasks_dict[task.name].extend(self.math_tasks[task.name][week_start])
        return math_tasks_dict

    def _get_main_math_tasks(self, call_math_task, main_main_task_names, tasks_dict):
        main_math_tasks_set = set()
        start_date = call_math_task.start_date
        end_date = call_math_task.end_date
        for main_math_task_name in main_main_task_names:
            main_math_tasks = tasks_dict[main_math_task_name]
            for main_math_task in main_math_tasks:
                if abs((main_math_task.start_date - end_date).days) <= 2 or abs((main_math_task.end_date - start_date).days) <= 2:
                    main_math_tasks_set.add(main_math_task)
        return list(main_math_tasks_set)

    def _assign_physician_to_call_task(self, main_math_tasks, call_math_task, physicians):
        for physician in physicians:
            self.math_model.Add(call_math_task.y_var(physician) <= sum(main_task.y_var(physician) for main_task in main_math_tasks)).WithName("musique")

    def _one_physician_for_main_task_period(self, main_math_tasks, physicians):
        number_of_math_tasks = len(main_math_tasks)
        M = main_math_tasks
        for physician in physicians:
            for i in range(number_of_math_tasks - 1):
                self.math_model.Add(M[i].y_var(physician) == M[i + 1].y_var(physician)).WithName("doudoune")

    def _get_available_physicians(self, days: List[date]) -> List[str]:
        return [
            physician.name
            for physician in self.physician_manager.data['physicians']
            if all(not self.physician_manager.is_unavailable(physician.name, day) for day in days)
        ]

    def _get_eligible_physicians(self, physicians: List[str], task) -> List[str]:
        return [
            physician for physician in physicians
            if task.category.name not in self.physician_manager.get_physician_by_name(physician).exclusion_tasks
        ]

    def _get_all_physicians(self):
        return [physician.name for physician in self.physician_manager.data['physicians']]

    def _is_physician_available(self, physician: str, days: List[date]) -> bool:
        return all(not self.physician_manager.is_unavailable(physician, day) for day in days)

    def _is_physician_unavailable(self, physician: str, days: List[date]) -> bool:
        return any(self.physician_manager.is_unavailable(physician, day) for day in days)

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
        with open(filename, 'r') as f:
            loaded_schedule = json.load(f)
        self.schedule = defaultdict(list, {
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

    def save_debug_info(self, filename: str):
        with open(filename, 'w') as f:
            json.dump(self.debug_info, f, indent=2, default=str)
        logging.info(f"Debug information saved to {filename}")

    def verify_physician_availability(self, task_name, start_date, end_date):
        task_key = f"{task_name}_{start_date}_{end_date}"
        if task_key in self.debug_info['math_tasks']:
            initial_candidates = self.debug_info['math_tasks'][task_key]['initial_candidates']
            available_candidates = self.debug_info['math_tasks'][task_key]['candidates_after_availability']
            
            print(f"Availability check for {task_name} from {start_date} to {end_date}:")
            for physician in initial_candidates:
                is_available = physician in available_candidates
                print(f"  {physician}: {'Available' if is_available else 'Unavailable'}")
                
                is_unavailable = any(
                    self.physician_manager.is_unavailable(physician, day)
                    for day in [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
                )
                if is_available != (not is_unavailable):
                    print(f"    WARNING: Discrepancy in availability for {physician}")
                    unavailability_info = self.physician_manager.get_unavailability_info(physician)
                    print(f"    Unavailability periods: {unavailability_info}")
        else:
            print(f"No debug info found for task {task_name} from {start_date} to {end_date}")

    def export_model(self, filename):
        self.math_model.ExportToFile(filename)