from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Any
from models.task import TaskDaysParameter

class Constraint(ABC):
    @abstractmethod
    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if assignment satisfies the constraint."""
        pass

class AvailabilityConstraint(Constraint):
    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if physician is available for all days in period."""
        physician = assignment['physician']
        period_days = assignment['period']['days']
        return all(not scheduler.physician_manager.is_unavailable(physician, day) 
                  for day in period_days)

class ExclusionConstraint(Constraint):
    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if task is not in physician's exclusion list."""
        physician = assignment['physician']
        task = assignment['task']
        physician_obj = scheduler.physician_manager.get_physician_by_name(physician)
        return task.category.name not in physician_obj.exclusion_tasks

class OverlapConstraint(Constraint):
    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if assignment doesn't overlap with existing assignments."""
        physician = assignment['physician']
        period = assignment['period']
        period_start = period['days'][0]
        period_end = period['days'][-1]
        
        for existing in scheduler.schedule[physician]:
            if not (existing['end_date'] < period_start or 
                    existing['start_date'] > period_end):
                return False
        return True

class CallSpacingConstraint(Constraint):
    def __init__(self, spacing_days: int = 21):
        self.spacing_days = spacing_days

    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if call assignment respects spacing requirement."""
        if not assignment['task'].is_call_task:
            return True
            
        physician = assignment['physician']
        period_start = assignment['period']['days'][0]
        period_end = assignment['period']['days'][-1]
        
        for call in scheduler.physician_calls[physician]:
            if ((period_start - call['end_date']).days <= self.spacing_days or
                (call['start_date'] - period_end).days <= self.spacing_days):
                return False
        return True

class MultiWeekContinuityConstraint(Constraint):
    def check(self, assignment: Dict[str, Any], scheduler: Any) -> bool:
        """Check if multi-week task maintains continuity."""
        task = assignment['task']
        if task.category.days_parameter != TaskDaysParameter.MULTI_WEEK:
            return True
            
        physician = assignment['physician']
        period_start = assignment['period']['days'][0]
        
        # Check if this is part of an existing multi-week assignment
        for existing in scheduler.schedule[physician]:
            if (existing['task'].name == task.name and 
                abs((existing['end_date'] - period_start).days) <= 7):
                return True
                
        return False 